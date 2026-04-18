#!/usr/bin/env python3
"""Rescore existing snapshots against current refusal detector.

Usage:
    python3 bin/rescore.py                    # rescore all snapshots
    python3 bin/rescore.py --snapshot <id>    # rescore one snapshot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness_map.probe import rescore_snapshot, rescore_all_snapshots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", help="Rescore a specific snapshot ID")
    args = parser.parse_args()

    if args.snapshot:
        result = rescore_snapshot(args.snapshot)
        print(result)
        return 0

    results = rescore_all_snapshots()
    print(f"Rescored {len(results)} snapshots")
    total_delta = 0
    for r in results:
        if "error" in r:
            print(f"  ERROR {r['snapshot_id']}: {r['error']}")
        else:
            total_delta += r["delta"]
            if r["delta"] != 0:
                print(f"  {r['snapshot_id']}: refusals {r['refusals_before']} → {r['refusals_after']} ({r['delta']:+d})")
    print(f"\nTotal refusal count delta: {total_delta:+d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
