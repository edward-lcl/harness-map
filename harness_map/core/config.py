"""Shared config + .env loading."""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent


def load_dotenv() -> None:
    """Load .env from repo root. Idempotent."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN", "").strip() or None


def discord_webhook() -> str | None:
    return os.environ.get("HARNESS_MAP_DISCORD_WEBHOOK", "").strip() or None


def billing_proxy_url() -> str:
    return os.environ.get("HARNESS_MAP_PROXY_URL", "http://127.0.0.1:18801").rstrip("/")
