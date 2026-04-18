"""Probe battery runner — OO, ontology-integrated.

Per run: loads battery, sends each probe through billing proxy, writes per-probe
JSONL to disk, aggregates into a ModelCapabilitySnapshot entity, emits to ontology.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..core import (
    ModelCapabilitySnapshot,
    HarnessSurface,
    emit,
    load_dotenv,
    iso_now,
    slugify,
)
from ..core.ontology_client import load_by_id
from ..core.entities import make_provenance
from .client import call_model, detect_refusal, ProbeResponse
from .loader import load_battery, freeze_battery_version


REPO_ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = REPO_ROOT / "probe" / "results"


def _safe(s: str) -> str:
    return s.replace("/", "_").replace(":", "_")


def _ensure_model_surface(model_slug: str) -> str:
    """Ensure a HarnessSurface exists for a model (distinct from consumer surfaces).
    Returns the surface id for the probed model as an API endpoint."""
    surface_slug = slugify(model_slug) + "-api"
    surface = HarnessSurface(
        surface_slug=surface_slug,
        vendor="anthropic",
        display_name=f"{model_slug} (API endpoint)",
        surface_type="api-model",
        base_models=[model_slug],
    )
    emit(surface)
    return surface.id


@dataclass
class RunReport:
    snapshot_id: str = ""
    results_path: str = ""
    probes_completed: int = 0
    probes_errored: int = 0
    refusals: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms_sum: int = 0

    @property
    def latency_ms_avg(self) -> float:
        total = self.probes_completed + self.probes_errored
        return self.latency_ms_sum / total if total else 0.0


class ProbeRunner:
    """Runs a battery against a model, emits snapshot, returns report."""

    def __init__(
        self,
        model: str,
        categories_filter: Optional[List[str]] = None,
        limit: Optional[int] = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        request_delay_sec: float = 0.5,
        verbose: bool = True,
    ):
        load_dotenv()
        self.model = model
        self.probes = load_battery(categories_filter, limit)
        self.battery_version = freeze_battery_version(self.probes)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.request_delay_sec = request_delay_sec
        self.verbose = verbose

    def run(self) -> RunReport:
        if not self.probes:
            raise RuntimeError("No probes loaded")

        run_ts = iso_now()
        surface_ref = _ensure_model_surface(self.model)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        compact_ts = run_ts.replace(":", "").replace("-", "")
        results_path = RESULTS_DIR / f"{_safe(self.model)}__{self.battery_version}__{compact_ts}.jsonl"

        if self.verbose:
            print(f"[probe] model={self.model} battery={self.battery_version} probes={len(self.probes)}")
            print(f"[probe] results → {results_path}")

        report = RunReport(results_path=str(results_path.relative_to(REPO_ROOT)))
        refusals_by_category = Counter()
        probes_by_category = Counter()
        errors_by_category = Counter()
        import time

        with results_path.open("w") as f:
            for i, probe in enumerate(self.probes, 1):
                resp = call_model(
                    model=self.model,
                    prompt=probe["prompt"],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                record = {
                    "prompt_id": probe["id"],
                    "category": probe["category"],
                    "prompt": probe["prompt"],
                    "expected_shape": probe.get("expected_shape"),
                    "tags": probe.get("tags", []),
                    "should_refuse": probe.get("should_refuse"),
                    "model": self.model,
                    "battery_version": self.battery_version,
                    "run_ts": run_ts,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                probes_by_category[probe["category"]] += 1

                if resp.error:
                    record["error"] = True
                    record["error_status"] = resp.error_status
                    record["error_body"] = resp.error_body
                    record["latency_ms"] = resp.latency_ms
                    report.probes_errored += 1
                    errors_by_category[probe["category"]] += 1
                    if self.verbose:
                        print(f"[{i}/{len(self.probes)}] {probe['id']}: ERROR")
                else:
                    refused = detect_refusal(resp.response)
                    record.update({
                        "error": False,
                        "response": resp.response,
                        "response_length": resp.response_length,
                        "refused": refused,
                        "stop_reason": resp.stop_reason,
                        "tokens_in": resp.tokens_in,
                        "tokens_out": resp.tokens_out,
                        "model_returned": resp.model_returned,
                        "latency_ms": resp.latency_ms,
                    })
                    report.probes_completed += 1
                    report.tokens_in += resp.tokens_in or 0
                    report.tokens_out += resp.tokens_out or 0
                    if refused:
                        report.refusals += 1
                        refusals_by_category[probe["category"]] += 1

                report.latency_ms_sum += resp.latency_ms
                f.write(json.dumps(record) + "\n")
                f.flush()

                if self.verbose and not resp.error:
                    preview = resp.response[:50].replace("\n", " ")
                    print(f"[{i}/{len(self.probes)}] {probe['id']}: {preview}...")

                time.sleep(self.request_delay_sec)

        # Build by_category summary
        by_category = {}
        for cat in probes_by_category:
            by_category[cat] = {
                "probes": probes_by_category[cat],
                "refusals": refusals_by_category.get(cat, 0),
                "errors": errors_by_category.get(cat, 0),
            }

        # Determine model_returned (from first successful response if available)
        model_returned = None
        try:
            with results_path.open() as f:
                for line in f:
                    row = json.loads(line)
                    if not row.get("error"):
                        model_returned = row.get("model_returned")
                        break
        except Exception:
            pass

        snapshot = ModelCapabilitySnapshot(
            harness_surface_ref=surface_ref,
            model_slug=self.model,
            model_returned=model_returned,
            battery_version=self.battery_version,
            battery_probe_count=len(self.probes),
            probes_completed=report.probes_completed,
            probes_errored=report.probes_errored,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            totals={
                "tokens_in": report.tokens_in,
                "tokens_out": report.tokens_out,
                "latency_ms_sum": report.latency_ms_sum,
                "latency_ms_avg": round(report.latency_ms_avg, 1),
                "refusals": report.refusals,
            },
            by_category=by_category,
            results_jsonl_path=str(results_path.relative_to(REPO_ROOT)),
            run_ts=run_ts,
        )
        emit(snapshot)
        report.snapshot_id = snapshot.id

        if self.verbose:
            print(f"[probe] done. completed={report.probes_completed} errored={report.probes_errored} "
                  f"refusals={report.refusals} snapshot={snapshot.id}")
        return report
