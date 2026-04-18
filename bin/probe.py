#!/usr/bin/env python3
"""CLI entry: python3 bin/probe.py --model claude-haiku-4-5 [--categories persona,identity] [--limit N]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness_map.probe import ProbeRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--categories", default=None,
                        help="Comma-separated list of category names")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--request-delay", type=float, default=0.5)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    cats = [c.strip() for c in args.categories.split(",")] if args.categories else None
    runner = ProbeRunner(
        model=args.model,
        categories_filter=cats,
        limit=args.limit,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        request_delay_sec=args.request_delay,
        verbose=not args.quiet,
    )
    report = runner.run()
    print(f"\nSnapshot: {report.snapshot_id}")
    print(f"Results:  {report.results_path}")
    print(f"Summary:  completed={report.probes_completed} errored={report.probes_errored} refusals={report.refusals}")
    print(f"Tokens:   {report.tokens_in} in / {report.tokens_out} out")
    print(f"Latency:  {report.latency_ms_avg:.0f}ms avg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
