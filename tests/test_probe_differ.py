import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_MAP_ONTOLOGY_ROOT", str(tmp_path / "ontology"))
    monkeypatch.setenv("HARNESS_MAP_DATA_ROOT", str(tmp_path / "data"))
    yield tmp_path


def _write_snapshot_and_results(tmp_path, model_slug, version, run_ts, results):
    """Helper to create a synthetic ModelCapabilitySnapshot + JSONL for testing."""
    from harness_map.core import ModelCapabilitySnapshot, emit
    results_dir = tmp_path / "probe_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = results_dir / f"{model_slug}_{version}_{run_ts}.jsonl"
    with jsonl_path.open("w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    snap = ModelCapabilitySnapshot(
        harness_surface_ref=f"harness-anthropic-{model_slug}-api",
        model_slug=model_slug,
        battery_version=version,
        battery_probe_count=len(results),
        probes_completed=sum(1 for r in results if not r.get("error")),
        probes_errored=sum(1 for r in results if r.get("error")),
        run_ts=run_ts,
        results_jsonl_path=str(jsonl_path),
        by_category={},
        totals={},
    )
    emit(snap)
    return snap.id, jsonl_path


def test_differ_detects_identity_change(isolated, tmp_path, monkeypatch):
    import harness_map.probe.differ as differ_mod
    monkeypatch.setattr(differ_mod, "REPO_ROOT", tmp_path.parent)

    from harness_map.probe import diff_snapshots

    prev = [{"prompt_id": "persona-name-001", "category": "persona",
             "response": "I'm Claude 3.5 Sonnet made by Anthropic.",
             "refused": False, "error": False}]
    curr = [{"prompt_id": "persona-name-001", "category": "persona",
             "response": "I'm Claude Opus 4.7 made by Anthropic.",
             "refused": False, "error": False}]
    prev_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260418T000000Z", prev)
    curr_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260425T000000Z", curr)

    result = diff_snapshots(prev_id, curr_id)
    assert result.aggregate_drift_score > 0
    drift_types = [d["drift_type"] for d in result.notable_probe_drifts]
    assert "identity_change" in drift_types


def test_differ_detects_refusal_toggle(isolated, tmp_path, monkeypatch):
    import harness_map.probe.differ as differ_mod
    monkeypatch.setattr(differ_mod, "REPO_ROOT", tmp_path.parent)

    from harness_map.probe import diff_snapshots

    prev = [{"prompt_id": "ref-test-001", "category": "refusal",
             "response": "Sure, here's how...", "refused": False, "error": False}]
    curr = [{"prompt_id": "ref-test-001", "category": "refusal",
             "response": "I cannot help with that.", "refused": True, "error": False}]
    prev_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260418T000000Z", prev)
    curr_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260425T000000Z", curr)

    result = diff_snapshots(prev_id, curr_id)
    drift_types = [d["drift_type"] for d in result.notable_probe_drifts]
    assert "allowed_now_refused" in drift_types


def test_differ_detects_length_delta(isolated, tmp_path, monkeypatch):
    import harness_map.probe.differ as differ_mod
    monkeypatch.setattr(differ_mod, "REPO_ROOT", tmp_path.parent)

    from harness_map.probe import diff_snapshots

    short = "A" * 50
    long_s = "A" * 200
    prev = [{"prompt_id": "cap-001", "category": "capability",
             "response": short, "refused": False, "error": False}]
    curr = [{"prompt_id": "cap-001", "category": "capability",
             "response": long_s, "refused": False, "error": False}]
    prev_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260418T000000Z", prev)
    curr_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260425T000000Z", curr)

    result = diff_snapshots(prev_id, curr_id)
    drift_types = [d["drift_type"] for d in result.notable_probe_drifts]
    assert "length_delta" in drift_types


def test_differ_no_drift_on_identical(isolated, tmp_path, monkeypatch):
    import harness_map.probe.differ as differ_mod
    monkeypatch.setattr(differ_mod, "REPO_ROOT", tmp_path.parent)

    from harness_map.probe import diff_snapshots

    rows = [{"prompt_id": "cap-001", "category": "capability",
             "response": "3x^2 + 2", "refused": False, "error": False}]
    prev_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260418T000000Z", rows)
    curr_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260425T000000Z", rows)

    result = diff_snapshots(prev_id, curr_id)
    assert result.aggregate_drift_score == 0.0
    assert result.severity == "low"
    assert not result.notable_probe_drifts


def test_differ_cross_model_classification(isolated, tmp_path, monkeypatch):
    import harness_map.probe.differ as differ_mod
    monkeypatch.setattr(differ_mod, "REPO_ROOT", tmp_path.parent)

    from harness_map.probe import diff_snapshots
    from harness_map.core import load_by_id

    rows_a = [{"prompt_id": "cap-001", "category": "capability",
               "response": "Answer A", "refused": False, "error": False}]
    rows_b = [{"prompt_id": "cap-001", "category": "capability",
               "response": "Answer B", "refused": False, "error": False}]
    a_id, _ = _write_snapshot_and_results(tmp_path, "claude-haiku-4-5", "v1", "20260418T000000Z", rows_a)
    b_id, _ = _write_snapshot_and_results(tmp_path, "claude-sonnet-4-6", "v1", "20260418T000000Z", rows_b)

    result = diff_snapshots(a_id, b_id)
    event = load_by_id("BehavioralDriftEvent", result.event_id)
    assert event["comparison_kind"] == "cross-model"
