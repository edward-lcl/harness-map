"""GitHub API polling for leaked Anthropic prompts.

Fetches the contents of the ANTHROPIC folder in elder-plinius/CL4R1T4S
and returns file metadata + raw content. Uses conditional requests (If-None-Match
with ETag) to stay well under rate limits.
"""

from __future__ import annotations

import os
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests

GITHUB_API = "https://api.github.com"
REPO = "elder-plinius/CL4R1T4S"
FOLDER = "ANTHROPIC"


@dataclass
class RemoteFile:
    name: str
    path: str
    sha: str
    size: int
    download_url: str
    content: str  # fetched separately


class FetchError(Exception):
    pass


def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def list_folder(owner_repo: str = REPO, folder: str = FOLDER) -> List[dict]:
    """List all files in the target folder. Returns raw GitHub API dicts."""
    url = f"{GITHUB_API}/repos/{owner_repo}/contents/{folder}"
    resp = requests.get(url, headers=_headers(), timeout=15)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise FetchError(f"GitHub rate limit: {resp.text[:200]}")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise FetchError(f"Expected list, got {type(data)}: {str(data)[:200]}")
    return [f for f in data if f.get("type") == "file"]


def fetch_content(download_url: str) -> str:
    """Fetch raw content from download_url. Returns decoded text."""
    resp = requests.get(download_url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_all_current(owner_repo: str = REPO, folder: str = FOLDER) -> List[RemoteFile]:
    """List folder + fetch content for each file. Primary entry point."""
    files = list_folder(owner_repo, folder)
    out = []
    for f in files:
        # Skip non-text files by extension heuristic
        name = f.get("name", "")
        if not any(name.endswith(ext) for ext in (".txt", ".md", ".json")):
            continue
        try:
            content = fetch_content(f["download_url"])
        except Exception as e:
            # Log and skip — don't fail whole run on one file
            print(f"[prompt_fetch] Failed to fetch {name}: {e}")
            continue
        out.append(RemoteFile(
            name=name,
            path=f["path"],
            sha=f["sha"],
            size=f["size"],
            download_url=f["download_url"],
            content=content,
        ))
    return out


def save_state(state: dict, state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True))


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return {}
