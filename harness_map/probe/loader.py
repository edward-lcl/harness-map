"""Probe corpus loader — YAML-based, versioned by content hash."""

from __future__ import annotations

import hashlib
import json
import datetime as dt
from pathlib import Path
from typing import List, Optional

import yaml


REPO_ROOT = Path(__file__).parent.parent.parent
CATEGORIES_DIR = REPO_ROOT / "probe" / "categories"
BATTERY_VERSIONS_DIR = REPO_ROOT / "probe" / "battery_versions"


def load_battery(
    categories_filter: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> List[dict]:
    """Load all probes from categories/*.yaml, optionally filtered."""
    probes = []
    for yaml_path in sorted(CATEGORIES_DIR.glob("*.yaml")):
        category_name = yaml_path.stem
        if categories_filter and category_name not in categories_filter:
            continue
        with yaml_path.open() as f:
            docs = yaml.safe_load(f) or []
        for p in docs:
            if "id" not in p or "prompt" not in p:
                continue
            probes.append(p)
    if limit:
        probes = probes[:limit]
    return probes


def freeze_battery_version(probes: List[dict]) -> str:
    """Hash the probe corpus, save frozen snapshot, return version tag."""
    BATTERY_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(probes, sort_keys=True).encode("utf-8")
    sha = hashlib.sha256(canonical).hexdigest()[:12]
    date_tag = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    version_tag = f"{date_tag}-{sha}"
    snapshot_path = BATTERY_VERSIONS_DIR / f"{version_tag}.json"
    if not snapshot_path.exists():
        snapshot_path.write_text(json.dumps(probes, indent=2, sort_keys=True))
    return version_tag
