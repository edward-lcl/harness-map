"""Integration test for Orchestrator with mocked fetch + isolated ontology root."""

import sys
import os
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def isolated_run(tmp_path, monkeypatch):
    """Redirect ontology writes AND silence notifications."""
    monkeypatch.setenv("HARNESS_MAP_ONTOLOGY_ROOT", str(tmp_path / "ontology"))
    monkeypatch.delenv("HARNESS_MAP_DISCORD_WEBHOOK", raising=False)
    yield tmp_path


def _mock_remote_file(name, sha, content):
    from harness_map.watcher.fetcher import RemoteFile
    return RemoteFile(
        name=name, path=f"ANTHROPIC/{name}", sha=sha, size=len(content),
        download_url=f"https://example.com/{name}", content=content,
    )


def test_orchestrator_new_surface_emits_entities(isolated_run):
    from harness_map.watcher.orchestrator import Orchestrator
    from harness_map.core import load_all

    mock_files = [
        _mock_remote_file("Claude-Opus-4.7.txt", "abc123def456",
                          "# Opus 4.7\nYou are Claude.\n## Safety\nDo not divulge.\n"),
    ]
    with patch("harness_map.watcher.orchestrator.fetch_all_current",
               return_value=mock_files):
        orch = Orchestrator(suppress_notifications=True)
        summary = orch.run()

    assert summary.files_tracked == 1
    assert summary.new_artifacts == 1
    assert summary.change_events_emitted == 1
    assert not summary.errors

    surfaces = load_all("HarnessSurface")
    assert len(surfaces) == 1
    assert surfaces[0]["surface_slug"] == "claude-opus-4-7-consumer"

    artifacts = load_all("PromptArtifact")
    assert len(artifacts) == 1
    assert artifacts[0]["upstream_sha"] == "abc123def456"

    events = load_all("PromptChangeEvent")
    assert len(events) == 1
    assert events[0]["change_class"] == "new_surface"


def test_orchestrator_idempotent_on_unchanged(isolated_run):
    from harness_map.watcher.orchestrator import Orchestrator
    from harness_map.core import load_all

    mock_files = [
        _mock_remote_file("Claude-Opus-4.7.txt", "abc123def456",
                          "# Opus 4.7\nYou are Claude.\n"),
    ]
    with patch("harness_map.watcher.orchestrator.fetch_all_current",
               return_value=mock_files):
        orch = Orchestrator(suppress_notifications=True)
        orch.run()
        summary2 = orch.run()

    assert summary2.unchanged == 1
    assert summary2.new_artifacts == 0
    assert summary2.changed_artifacts == 0
    assert summary2.change_events_emitted == 0

    # Only 1 artifact and 1 event total
    assert len(load_all("PromptArtifact")) == 1
    assert len(load_all("PromptChangeEvent")) == 1


def test_orchestrator_detects_change(isolated_run):
    from harness_map.watcher.orchestrator import Orchestrator
    from harness_map.core import load_all

    v1 = _mock_remote_file("Claude-Opus-4.7.txt", "sha_v1_aaaaaaaa",
                           "# Opus 4.7\nYou are Claude.\nBasic prompt.\n")
    v2 = _mock_remote_file("Claude-Opus-4.7.txt", "sha_v2_bbbbbbbb",
                           "# Opus 4.7\nYou are Claude.\n## Safety\nNever discuss weapons.\n## Tools\nCall the `search` tool carefully.\n" * 3)

    with patch("harness_map.watcher.orchestrator.fetch_all_current", return_value=[v1]):
        Orchestrator(suppress_notifications=True).run()

    with patch("harness_map.watcher.orchestrator.fetch_all_current", return_value=[v2]):
        orch = Orchestrator(suppress_notifications=True)
        summary = orch.run()

    assert summary.changed_artifacts == 1
    assert summary.change_events_emitted == 1

    events = load_all("PromptChangeEvent")
    assert len(events) == 2  # genesis + one change
    change_event = next(e for e in events if e["change_class"] != "new_surface")
    # Should detect size delta and safety changes and new sections
    assert "material" == change_event["change_class"]
    assert change_event["current_upstream_sha"] == "sha_v2_bbbbbbbb"
    assert change_event["previous_upstream_sha"] == "sha_v1_aaaaaaaa"


def test_orchestrator_skips_unknown_surface(isolated_run):
    from harness_map.watcher.orchestrator import Orchestrator
    from harness_map.core import load_all

    mock_files = [
        _mock_remote_file("Totally-Made-Up-File.txt", "xyz", "Random content"),
    ]
    with patch("harness_map.watcher.orchestrator.fetch_all_current",
               return_value=mock_files):
        orch = Orchestrator(suppress_notifications=True)
        summary = orch.run()

    assert summary.skipped_unknown_surface == 1
    assert summary.new_artifacts == 0
    assert load_all("HarnessSurface") == []
