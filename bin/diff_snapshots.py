#!/usr/bin/env python3
"""CLI to diff two ModelCapabilitySnapshots.

Usage:
    # Auto: diff the latest two snapshots for a model (temporal)
    python3 bin/diff_snapshots.py --model claude-haiku-4-5

    # Explicit: diff two snapshot IDs
    python3 bin/diff_snapshots.py --prev <id> --curr <id>

    # Cross-model: diff two latest snapshots across models
    python3 bin/diff_snapshots.py --cross claude-haiku-4-5 claude-sonnet-4-6

    # Fan-out: diff all pairs of latest-per-model (cross-model matrix)
    python3 bin/diff_snapshots.py --matrix
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness_map.probe import (
    diff_snapshots,
    latest_snapshots_for_model,
    latest_snapshot_for_each_model,
)


def _print_result(result, verbose=True):
    print(f"\n▸ event: {result.event_id}")
    print(f"  severity: {result.severity}")
    print(f"  aggregate drift score: {result.aggregate_drift_score}")
    if result.drift_by_category:
        print(f"  by category:")
        for cat, info in sorted(result.drift_by_category.items(),
                                key=lambda x: x[1]["drift_score"], reverse=True):
            print(f"    {cat:20} probes={info['probes_compared']:3d}  "
                  f"drifted={info['drifts_observed']:3d}  score={info['drift_score']:.2f}")
    if verbose and result.notable_probe_drifts:
        print(f"  notable drifts (top {min(8, len(result.notable_probe_drifts))}):")
        for d in result.notable_probe_drifts[:8]:
            print(f"    • {d['prompt_id']:30} [{d['drift_type']}] {d['summary']}")
    if result.interpretation:
        print(f"  interpretation:")
        for line in result.interpretation:
            print(f"    - {line}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Temporal diff: latest two snapshots for this model")
    parser.add_argument("--prev", help="Explicit previous snapshot ID")
    parser.add_argument("--curr", help="Explicit current snapshot ID")
    parser.add_argument("--cross", nargs=2, metavar=("MODEL_A", "MODEL_B"),
                        help="Cross-model: latest snapshots for two different models")
    parser.add_argument("--matrix", action="store_true",
                        help="Fan-out: diff all pairs of latest-per-model snapshots")
    args = parser.parse_args()

    if args.prev and args.curr:
        result = diff_snapshots(args.prev, args.curr)
        _print_result(result)
        return 0

    if args.model:
        snaps = latest_snapshots_for_model(args.model, n=2)
        if len(snaps) < 2:
            print(f"Need ≥2 snapshots for {args.model}, found {len(snaps)}", file=sys.stderr)
            return 1
        result = diff_snapshots(snaps[1]["id"], snaps[0]["id"])  # older, newer
        _print_result(result)
        return 0

    if args.cross:
        model_a, model_b = args.cross
        a = latest_snapshots_for_model(model_a, n=1)
        b = latest_snapshots_for_model(model_b, n=1)
        if not a or not b:
            print(f"Missing snapshots. {model_a}: {len(a)}, {model_b}: {len(b)}", file=sys.stderr)
            return 1
        result = diff_snapshots(a[0]["id"], b[0]["id"])
        _print_result(result)
        return 0

    if args.matrix:
        latest = latest_snapshot_for_each_model()
        models = sorted(latest.keys())
        if len(models) < 2:
            print(f"Need ≥2 models for matrix, have {len(models)}", file=sys.stderr)
            return 1
        print(f"Matrix across {len(models)} models: {models}")
        for i, a in enumerate(models):
            for b in models[i+1:]:
                result = diff_snapshots(latest[a]["id"], latest[b]["id"])
                print(f"\n=== {a} vs {b} ===")
                _print_result(result, verbose=False)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
