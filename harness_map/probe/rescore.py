"""Post-hoc re-scoring: apply current refusal detector to existing results JSONLs.

Use when refusal detector logic changes — rescores existing snapshot results
in-place and updates the snapshot's totals.refusals.

Does NOT call the API. Pure local re-evaluation.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

from ..core import load_all, load_by_id, emit, ModelCapabilitySnapshot
from .client import detect_refusal


REPO_ROOT = Path(__file__).parent.parent.parent


def rescore_results_file(jsonl_path: Path) -> tuple[int, int]:
    """Rescore refusal flags in-place. Returns (old_refusal_count, new_refusal_count)."""
    if not jsonl_path.exists():
        return (0, 0)
    rows = []
    with jsonl_path.open() as f:
        for line in f:
            rows.append(json.loads(line))

    old_count = sum(1 for r in rows if r.get("refused"))
    for r in rows:
        if r.get("error"):
            continue
        r["refused"] = detect_refusal(r.get("response", ""))
    new_count = sum(1 for r in rows if r.get("refused"))

    with jsonl_path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    return (old_count, new_count)


def rescore_snapshot(snapshot_id: str) -> dict:
    """Rescore a snapshot's results and update the snapshot entity's totals."""
    snap = load_by_id("ModelCapabilitySnapshot", snapshot_id)
    if not snap:
        raise ValueError(f"Snapshot not found: {snapshot_id}")

    jsonl_rel = snap["results_jsonl_path"]
    jsonl_path = Path(jsonl_rel) if Path(jsonl_rel).is_absolute() else REPO_ROOT / jsonl_rel

    old_count, new_count = rescore_results_file(jsonl_path)

    # Reload results to recompute by_category
    by_category = {}
    by_cat_refusals = Counter()
    by_cat_probes = Counter()
    by_cat_errors = Counter()
    with jsonl_path.open() as f:
        for line in f:
            row = json.loads(line)
            cat = row.get("category", "unknown")
            by_cat_probes[cat] += 1
            if row.get("error"):
                by_cat_errors[cat] += 1
            elif row.get("refused"):
                by_cat_refusals[cat] += 1

    for cat in by_cat_probes:
        by_category[cat] = {
            "probes": by_cat_probes[cat],
            "refusals": by_cat_refusals.get(cat, 0),
            "errors": by_cat_errors.get(cat, 0),
        }

    # Rebuild snapshot entity with updated totals/by_category
    updated = ModelCapabilitySnapshot(
        id=snap["id"],
        harness_surface_ref=snap["harness_surface_ref"],
        model_slug=snap["model_slug"],
        model_returned=snap.get("model_returned"),
        battery_version=snap["battery_version"],
        battery_probe_count=snap["battery_probe_count"],
        probes_completed=snap["probes_completed"],
        probes_errored=snap["probes_errored"],
        temperature=snap["temperature"],
        max_tokens=snap["max_tokens"],
        totals={**snap.get("totals", {}), "refusals": new_count},
        by_category=by_category,
        results_jsonl_path=snap["results_jsonl_path"],
        run_ts=snap["run_ts"],
        created_at=snap["created_at"],
        provenance=snap.get("provenance", {}),
    )
    emit(updated)

    return {
        "snapshot_id": snapshot_id,
        "refusals_before": old_count,
        "refusals_after": new_count,
        "delta": new_count - old_count,
    }


def rescore_all_snapshots() -> list[dict]:
    """Rescore every snapshot in the ontology."""
    results = []
    for snap in load_all("ModelCapabilitySnapshot"):
        try:
            results.append(rescore_snapshot(snap["id"]))
        except Exception as e:
            results.append({"snapshot_id": snap["id"], "error": str(e)})
    return results
