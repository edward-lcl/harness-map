#!/usr/bin/env python3
"""Smoke test for Discord notification path. Fires a single test embed, exits."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Load .env same way the main watcher does
from anthropic_prompt_watch import _load_dotenv
_load_dotenv()

from prompt_notify import notify

ok = notify(
    title="✅ harness-map smoke test",
    description=(
        "Phase 1 MVP online. Webhook wired, GitHub token loaded.\n"
        "Next material change on CL4R1T4S/ANTHROPIC/ will land here."
    ),
    fields=[
        {"name": "Repo", "value": "`~/harness-map/` (local)", "inline": True},
        {"name": "Cadence", "value": "hourly (when cron registered)", "inline": True},
        {"name": "Baseline", "value": "11 prompts archived 2026-04-18", "inline": False},
    ],
    color=0x10b981,
)
print("notify result:", ok)
sys.exit(0 if ok else 1)
