#!/usr/bin/env python3
"""Entry point for cron: python3 bin/watch.py"""

from __future__ import annotations

import sys
from pathlib import Path

# Make harness_map importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from harness_map.watcher import main

if __name__ == "__main__":
    sys.exit(main())
