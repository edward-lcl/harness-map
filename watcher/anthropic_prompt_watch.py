#!/usr/bin/env python3
"""Orchestrator for Anthropic prompt leak monitoring (L2).

Workflow per run:
  1. Load state (fetched files + upstream shas from last run)
  2. Fetch current folder contents from CL4R1T4S/ANTHROPIC
  3. For each file:
       - If new file: save raw, extract metadata, log + notify
       - If existing with same sha: skip
       - If existing with new sha: diff, classify, save new raw + diff + metadata, log, notify if material
  4. Save updated state
  5. Append CHANGELOG.md entries for any changes

Runs idempotently. Safe to cron hourly. Exits 0 on success, non-zero on error.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import traceback
from pathlib import Path

# Allow running as script: add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def _load_dotenv() -> None:
    """Tiny .env loader. Avoids python-dotenv dependency for MVP."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Don't clobber explicitly-set env vars (e.g. during cron)
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

from prompt_fetch import fetch_all_current, load_state, save_state, FetchError
from prompt_diff import classify
from prompt_metadata import extract
from prompt_notify import notify, format_material_change


REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data" / "anthropic-prompts"
RAW_DIR = DATA_DIR / "raw"
DIFF_DIR = DATA_DIR / "diffs"
META_DIR = DATA_DIR / "metadata"
STATE_FILE = DATA_DIR / "state.json"
CHANGELOG = DATA_DIR / "CHANGELOG.md"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _surface_from_name(name: str) -> str:
    """Best-effort surface label from filename (e.g. Claude-Opus-4.7.txt -> claude-opus-4.7)."""
    stem = name.rsplit(".", 1)[0]
    return stem.lower().replace("_", "-")


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _ensure_dirs():
    for d in (RAW_DIR, DIFF_DIR, META_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _append_changelog(entry: str) -> None:
    if not CHANGELOG.exists():
        CHANGELOG.write_text("# Anthropic Prompt Watch — Changelog\n\n")
    with CHANGELOG.open("a") as f:
        f.write(entry + "\n")


def _write_raw(filename: str, sha: str, content: str, fetched_at: str) -> Path:
    """Save raw content with sha-pinned filename for history."""
    date_tag = fetched_at[:10]
    safe = _safe_filename(filename)
    path = RAW_DIR / f"{safe}__{date_tag}__{sha[:8]}"
    # Don't clobber if exact file already exists
    if not path.exists():
        path.write_text(content)
    return path


def _write_diff(filename: str, prev_sha: str, new_sha: str, diff_text: str, fetched_at: str) -> Path:
    date_tag = fetched_at[:10]
    safe = _safe_filename(filename)
    path = DIFF_DIR / f"{safe}__{date_tag}__{prev_sha[:8]}__{new_sha[:8]}.diff"
    path.write_text(diff_text)
    return path


def _write_metadata(filename: str, sha: str, meta: dict, fetched_at: str) -> Path:
    date_tag = fetched_at[:10]
    safe = _safe_filename(filename)
    path = META_DIR / f"{safe}__{date_tag}__{sha[:8]}.json"
    path.write_text(json.dumps(meta, indent=2, sort_keys=True))
    return path


def run() -> int:
    _ensure_dirs()
    fetched_at = _now_iso()

    try:
        files = fetch_all_current()
    except FetchError as e:
        print(f"[watch] FETCH ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[watch] UNEXPECTED FETCH ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        return 3

    state = load_state(STATE_FILE)
    # state structure: {filename: {"sha": str, "last_seen": iso, "raw_path": str}}

    changes_for_changelog = []
    notifications_sent = 0

    for rf in files:
        surface = _surface_from_name(rf.name)
        prev = state.get(rf.name)

        if prev is None:
            # NEW FILE
            raw_path = _write_raw(rf.name, rf.sha, rf.content, fetched_at)
            meta = extract(
                content=rf.content,
                surface=surface,
                source_url=rf.download_url,
                upstream_sha=rf.sha,
                fetched_at=fetched_at,
            )
            _write_metadata(rf.name, rf.sha, meta, fetched_at)
            diff_result = classify(None, rf.content)

            state[rf.name] = {
                "sha": rf.sha,
                "last_seen": fetched_at,
                "raw_path": str(raw_path.relative_to(REPO_ROOT)),
            }

            payload = format_material_change(
                filename=rf.name,
                reasons=diff_result.reasons,
                new_tools=diff_result.new_tools,
                new_sections=diff_result.new_sections,
                safety_changes=diff_result.safety_changes,
                old_size=0,
                new_size=rf.size,
                raw_url=rf.download_url,
            )
            if notify(**payload):
                notifications_sent += 1

            changes_for_changelog.append(
                f"- **{fetched_at}** — NEW `{rf.name}` ({rf.size} bytes, {len(meta['tools_mentioned'])} tools, {len(meta['sections'])} sections)"
            )

        elif prev["sha"] != rf.sha:
            # CHANGED FILE
            prev_sha = prev["sha"]
            prev_raw_rel = prev.get("raw_path")
            old_content = ""
            if prev_raw_rel:
                prev_raw = REPO_ROOT / prev_raw_rel
                if prev_raw.exists():
                    old_content = prev_raw.read_text()
            diff_result = classify(old_content or None, rf.content)

            new_raw_path = _write_raw(rf.name, rf.sha, rf.content, fetched_at)
            if diff_result.unified_diff:
                _write_diff(rf.name, prev_sha, rf.sha, diff_result.unified_diff, fetched_at)
            meta = extract(
                content=rf.content,
                surface=surface,
                source_url=rf.download_url,
                upstream_sha=rf.sha,
                fetched_at=fetched_at,
            )
            _write_metadata(rf.name, rf.sha, meta, fetched_at)

            state[rf.name] = {
                "sha": rf.sha,
                "last_seen": fetched_at,
                "raw_path": str(new_raw_path.relative_to(REPO_ROOT)),
                "prev_sha": prev_sha,
            }

            if diff_result.material:
                payload = format_material_change(
                    filename=rf.name,
                    reasons=diff_result.reasons,
                    new_tools=diff_result.new_tools,
                    new_sections=diff_result.new_sections,
                    safety_changes=diff_result.safety_changes,
                    old_size=diff_result.old_size,
                    new_size=diff_result.new_size,
                    raw_url=rf.download_url,
                )
                if notify(**payload):
                    notifications_sent += 1

                changes_for_changelog.append(
                    f"- **{fetched_at}** — MATERIAL `{rf.name}` ({prev_sha[:8]} → {rf.sha[:8]}) — {', '.join(diff_result.reasons)}"
                )
            else:
                # Log-only: record it but no notification
                changes_for_changelog.append(
                    f"- **{fetched_at}** — minor `{rf.name}` ({prev_sha[:8]} → {rf.sha[:8]}) — {diff_result.size_delta_fraction:.1%} size delta"
                )

        else:
            # UNCHANGED — just update last_seen
            state[rf.name]["last_seen"] = fetched_at

    # Detect deletions (present in state but not in current fetch)
    current_names = {rf.name for rf in files}
    removed = [n for n in list(state.keys()) if n not in current_names]
    for r in removed:
        changes_for_changelog.append(f"- **{fetched_at}** — REMOVED `{r}` (no longer in upstream folder)")
        del state[r]

    save_state(state, STATE_FILE)

    for entry in changes_for_changelog:
        _append_changelog(entry)

    print(f"[watch] {_now_iso()} — {len(files)} files tracked, "
          f"{len(changes_for_changelog)} changelog entries, "
          f"{notifications_sent} notifications sent")
    return 0


if __name__ == "__main__":
    sys.exit(run())
