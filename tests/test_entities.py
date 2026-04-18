"""Test entity construction, IDs, serialization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from harness_map.core import (
    HarnessSurface,
    PromptArtifact,
    PromptChangeEvent,
    ModelCapabilitySnapshot,
    BehavioralDriftEvent,
    surface_for_filename,
)


def test_harness_surface_id_deterministic():
    s1 = HarnessSurface(surface_slug="claude-design", vendor="anthropic",
                        display_name="Claude Design", surface_type="design-tool")
    s2 = HarnessSurface(surface_slug="claude-design", vendor="anthropic",
                        display_name="Claude Design", surface_type="design-tool")
    assert s1.id == s2.id == "harness-anthropic-claude-design"
    assert s1.type == "HarnessSurface"


def test_prompt_artifact_id_unique_per_sha():
    a1 = PromptArtifact(
        harness_surface_ref="harness-anthropic-claude-design",
        layer="L2",
        source_url="https://example.com/file.txt",
        upstream_sha="1a55b8aa1234567890",
        raw_path="data/anthropic-prompts/raw/file.txt",
        metadata={"raw_size_bytes": 1000},
        fetched_at="2026-04-18T18:00:00Z",
    )
    assert "1a55b8aa" in a1.id
    assert a1.id.startswith("prompt-claude-design-20260418-")


def test_prompt_change_event_genesis():
    e = PromptChangeEvent(
        harness_surface_ref="harness-anthropic-claude-design",
        current_artifact_ref="prompt-claude-design-20260418-1a55b8aa",
        current_upstream_sha="1a55b8aa12",
        change_class="new_surface",
        change_reasons=["new_file"],
    )
    assert "genesis" in e.id  # no previous_sha


def test_prompt_change_event_with_prev():
    e = PromptChangeEvent(
        harness_surface_ref="harness-anthropic-claude-design",
        previous_artifact_ref="prompt-claude-design-20260417-oldshaab",
        current_artifact_ref="prompt-claude-design-20260418-newshacd",
        previous_upstream_sha="oldshaab",
        current_upstream_sha="newshacd",
        change_class="material",
        change_reasons=["safety_rule_changed"],
    )
    assert "oldshaab" in e.id and "newshacd" in e.id


def test_surface_for_filename_known():
    match = surface_for_filename("Claude-Opus-4.7.txt")
    assert match is not None
    assert match[0] == "claude-opus-4-7-consumer"

    match = surface_for_filename("Claude-Design-Sys-Prompt.txt")
    assert match is not None
    assert match[0] == "claude-design"

    assert surface_for_filename("totally-unknown-file.txt") is None


def test_model_capability_snapshot_id():
    snap = ModelCapabilitySnapshot(
        harness_surface_ref="harness-anthropic-claude-haiku-4-5",
        model_slug="claude-haiku-4-5",
        battery_version="2026-04-18-abc123",
        battery_probe_count=44,
        probes_completed=43,
        probes_errored=0,
        run_ts="2026-04-18T18:39:05Z",
    )
    assert snap.id.startswith("capsnap-claude-haiku-4-5-")
    assert "2026-04-18-abc123" in snap.id


def test_to_dict_strips_none():
    s = HarnessSurface(surface_slug="test", vendor="anthropic",
                       display_name="Test", surface_type="consumer-assistant")
    d = s.to_dict()
    assert d["surface_slug"] == "test"
    assert "notes" not in d  # None should be stripped


def test_all_entities_have_provenance():
    entities = [
        HarnessSurface(surface_slug="t", vendor="anthropic", display_name="T", surface_type="consumer-assistant"),
        PromptArtifact(harness_surface_ref="harness-anthropic-t", upstream_sha="abc", raw_path="x", source_url="y"),
        PromptChangeEvent(harness_surface_ref="harness-anthropic-t", current_artifact_ref="p", current_upstream_sha="abc"),
        ModelCapabilitySnapshot(harness_surface_ref="harness-anthropic-t", model_slug="m", battery_version="v"),
        BehavioralDriftEvent(harness_surface_ref="harness-anthropic-t",
                             previous_snapshot_ref="capsnap-m-v-ts1",
                             current_snapshot_ref="capsnap-m-v-ts2"),
    ]
    for e in entities:
        assert e.provenance
        assert e.provenance["source_system"] == "harness-map"
        assert "captured_at" in e.provenance
        assert e.created_at
        assert e.updated_at
        assert e.boundary == "node-levi"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
