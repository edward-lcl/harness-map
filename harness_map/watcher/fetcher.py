"""GitHub API fetch — moved from flat script into the package."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

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
    content: str


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
    resp = requests.get(download_url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_all_current(owner_repo: str = REPO, folder: str = FOLDER) -> List[RemoteFile]:
    files = list_folder(owner_repo, folder)
    out = []
    for f in files:
        name = f.get("name", "")
        if not any(name.endswith(ext) for ext in (".txt", ".md", ".json")):
            continue
        try:
            content = fetch_content(f["download_url"])
        except Exception as e:
            print(f"[fetcher] Failed to fetch {name}: {e}")
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
