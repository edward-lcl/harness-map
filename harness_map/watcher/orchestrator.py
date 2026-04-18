"""Watcher orchestrator — object-oriented, ontology-integrated.

Replaces the old flat `anthropic_prompt_watch.py`. Per run:
  1. Fetch all current files from CL4R1T4S/ANTHROPIC
  2. For each file:
     - Resolve to a HarnessSurface (emit if new)
     - Check if our ontology has a PromptArtifact with matching upstream_sha
       - If yes: unchanged, skip
       - If no: load previous artifact, classify diff, emit new artifact,
               emit PromptChangeEvent, notify if material
  3. Detect removed files (present in ontology but not upstream)
  4. Return run summary

All durable findings land in ~/.openclaw/workspace/ontology/entities/*.yaml
and become queryable alongside every other entity in the system.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..core import (
    PromptArtifact,
    PromptChangeEvent,
    ensure_surface,
    emit,
    find_latest_artifact_for_surface,
    load_dotenv,
    iso_now,
    short_sha,
    sha256_hex,
    make_provenance,
)
from .fetcher import fetch_all_current, FetchError, RemoteFile
from .differ import classify, severity_from_reasons
from .extractor import extract_metadata
from .notifier import notify, format_prompt_change


REPO_ROOT = Path(__file__).parent.parent.parent


def _data_dir() -> Path:
    """Respect HARNESS_MAP_DATA_ROOT for test isolation; default to repo data/."""
    import os
    override = os.environ.get("HARNESS_MAP_DATA_ROOT", "").strip()
    base = Path(override) if override else REPO_ROOT / "data"
    return base / "anthropic-prompts"


def _raw_dir() -> Path:
    return _data_dir() / "raw"


def _diff_dir() -> Path:
    return _data_dir() / "diffs"


@dataclass
class RunSummary:
    files_tracked: int = 0
    new_artifacts: int = 0
    changed_artifacts: int = 0
    unchanged: int = 0
    skipped_unknown_surface: int = 0
    change_events_emitted: int = 0
    notifications_sent: int = 0
    removed_surfaces: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"files={self.files_tracked} new={self.new_artifacts} "
            f"changed={self.changed_artifacts} unchanged={self.unchanged} "
            f"skipped={self.skipped_unknown_surface} "
            f"events={self.change_events_emitted} "
            f"notified={self.notifications_sent}"
        )


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _write_raw(filename: str, sha: str, content: str, fetched_at: str) -> Path:
    raw_dir = _raw_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)
    date_tag = fetched_at[:10]
    safe = _safe_filename(filename)
    path = raw_dir / f"{safe}__{date_tag}__{sha[:8]}"
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return path


def _write_diff(filename: str, prev_sha: str, new_sha: str, diff_text: str, fetched_at: str) -> Path:
    diff_dir = _diff_dir()
    diff_dir.mkdir(parents=True, exist_ok=True)
    date_tag = fetched_at[:10]
    safe = _safe_filename(filename)
    path = diff_dir / f"{safe}__{date_tag}__{prev_sha[:8]}__{new_sha[:8]}.diff"
    path.write_text(diff_text, encoding="utf-8")
    return path


def _interpret_change(reasons: list[str], added_tools: list[str], added_sections: list[str]) -> list[str]:
    """Generate human-readable interpretation lines for PromptChangeEvent."""
    out = []
    if "new_file" in reasons:
        out.append("First observation of this surface in our corpus.")
    if "safety_rule_changed" in reasons:
        out.append("Safety-relevant language was added or modified.")
    if "new_tools" in reasons and added_tools:
        preview = ", ".join(added_tools[:5])
        more = f" (+{len(added_tools)-5} more)" if len(added_tools) > 5 else ""
        out.append(f"New tools introduced: {preview}{more}.")
    if "sections_changed" in reasons and added_sections:
        preview = "; ".join(s[:50] for s in added_sections[:3])
        more = f" (+{len(added_sections)-3} more)" if len(added_sections) > 3 else ""
        out.append(f"New sections: {preview}{more}.")
    if any(r.startswith("size_delta") for r in reasons):
        delta_reason = next(r for r in reasons if r.startswith("size_delta"))
        out.append(f"Significant size change: {delta_reason.replace('size_delta_', '')}.")
    if not out:
        out.append("Minor edits without material impact.")
    return out


class Orchestrator:
    """Runs a single watch cycle. Idempotent across cycles."""

    def __init__(self, *, suppress_notifications: bool = False):
        load_dotenv()
        self.suppress_notifications = suppress_notifications

    def run(self) -> RunSummary:
        summary = RunSummary()
        fetched_at = iso_now()

        try:
            files = fetch_all_current()
        except FetchError as e:
            summary.errors.append(f"fetch_error: {e}")
            return summary
        except Exception as e:
            summary.errors.append(f"unexpected: {type(e).__name__}: {e}")
            return summary

        summary.files_tracked = len(files)
        observed_surface_refs = set()

        for rf in files:
            try:
                self._process_file(rf, fetched_at, summary, observed_surface_refs)
            except Exception as e:
                summary.errors.append(f"{rf.name}: {type(e).__name__}: {e}")

        # TODO (Stage 2): detect surfaces that disappeared — requires
        # scanning existing PromptArtifacts and flagging those whose
        # surface wasn't in observed_surface_refs. Deferred until we
        # have signal on false positives.

        return summary

    def _process_file(
        self,
        rf: RemoteFile,
        fetched_at: str,
        summary: RunSummary,
        observed_surfaces: set,
    ) -> None:
        # 1. Resolve surface (emit if new)
        surface = ensure_surface(rf.name)
        if not surface:
            print(f"[orchestrator] Skipping unknown surface for: {rf.name}")
            summary.skipped_unknown_surface += 1
            return
        observed_surfaces.add(surface.id)

        # 2. Check if we already have an artifact with this upstream_sha
        latest_artifact = find_latest_artifact_for_surface(surface.id)
        if latest_artifact and latest_artifact.get("upstream_sha") == rf.sha:
            summary.unchanged += 1
            return

        # 3. New or changed — extract metadata, write raw, build artifact
        metadata = extract_metadata(rf.content)
        raw_path = _write_raw(rf.name, rf.sha, rf.content, fetched_at)
        content_hash = sha256_hex(rf.content, length=16)

        # raw_path stored as relative to the data root (not REPO_ROOT) so
        # tests using HARNESS_MAP_DATA_ROOT override stay isolated.
        try:
            raw_path_ref = str(raw_path.relative_to(REPO_ROOT))
        except ValueError:
            raw_path_ref = str(raw_path)

        artifact = PromptArtifact(
            harness_surface_ref=surface.id,
            layer="L2",
            source_url=rf.download_url,
            upstream_sha=rf.sha,
            content_hash=content_hash,
            raw_path=raw_path_ref,
            metadata=metadata,
            fetched_at=fetched_at,
            supersedes_ref=latest_artifact["id"] if latest_artifact else None,
        )
        emit(artifact)

        # 4. Build and emit PromptChangeEvent
        if latest_artifact is None:
            # Genesis event for this surface
            diff_result = classify(None, rf.content)
            change_class = "new_surface"
            summary.new_artifacts += 1
            prev_content = ""
            prev_sha = ""
        else:
            # Changed — load prior raw content
            prev_raw_rel = latest_artifact["raw_path"]
            # Path may be absolute (test isolation) or relative (production)
            prev_raw_path = Path(prev_raw_rel) if Path(prev_raw_rel).is_absolute() else REPO_ROOT / prev_raw_rel
            prev_content = prev_raw_path.read_text(encoding="utf-8") if prev_raw_path.exists() else ""
            diff_result = classify(prev_content or None, rf.content)
            change_class = "material" if diff_result.material else "minor"
            summary.changed_artifacts += 1
            prev_sha = latest_artifact["upstream_sha"]

        unified_diff_path_rel = None
        if diff_result.unified_diff:
            unified_path = _write_diff(rf.name, prev_sha, rf.sha, diff_result.unified_diff, fetched_at)
            try:
                unified_diff_path_rel = str(unified_path.relative_to(REPO_ROOT))
            except ValueError:
                unified_diff_path_rel = str(unified_path)

        severity = severity_from_reasons(diff_result.reasons, diff_result.size_delta_fraction)
        interpretation = _interpret_change(
            diff_result.reasons, diff_result.new_tools, diff_result.new_sections
        )

        event = PromptChangeEvent(
            harness_surface_ref=surface.id,
            previous_artifact_ref=latest_artifact["id"] if latest_artifact else None,
            current_artifact_ref=artifact.id,
            previous_upstream_sha=prev_sha or None,
            current_upstream_sha=rf.sha,
            change_class=change_class,
            change_reasons=diff_result.reasons,
            deltas={
                "size_bytes": diff_result.new_size - diff_result.old_size,
                "size_fraction": diff_result.size_delta_fraction,
                "new_sections": diff_result.new_sections,
                "removed_sections": diff_result.removed_sections,
                "new_tools": diff_result.new_tools,
                "removed_tools": diff_result.removed_tools,
                "safety_rule_changes": diff_result.safety_changes,
            },
            unified_diff=diff_result.unified_diff[:8000] if diff_result.unified_diff else None,
            unified_diff_path=unified_diff_path_rel,
            interpretation=interpretation,
            severity=severity,
        )
        emit(event)
        summary.change_events_emitted += 1

        # 5. Notify if material (unless we're in bootstrap/silent mode)
        if diff_result.material and not self.suppress_notifications:
            payload = format_prompt_change(
                surface_display_name=surface.display_name,
                filename=rf.name,
                reasons=diff_result.reasons,
                new_tools=diff_result.new_tools,
                new_sections=diff_result.new_sections,
                safety_changes=diff_result.safety_changes,
                old_size=diff_result.old_size,
                new_size=diff_result.new_size,
                raw_url=rf.download_url,
                severity=severity,
                event_id=event.id,
            )
            if notify(**payload):
                summary.notifications_sent += 1


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--silent", action="store_true",
                        help="Suppress Discord notifications (use for bootstrap)")
    args = parser.parse_args()

    orch = Orchestrator(suppress_notifications=args.silent)
    summary = orch.run()
    print(f"[watcher] {iso_now()} — {summary}")
    if summary.errors:
        for err in summary.errors:
            print(f"[watcher] ERROR: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
