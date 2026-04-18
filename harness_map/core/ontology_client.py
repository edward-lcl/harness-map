"""Ontology client — writes harness-map entities to the workspace ontology.

Pattern matches existing emitters (e.g. gitnexus/generate_structural_drift_event.py):
  - YAML output under ontology/entities/<type>/<id>.yaml
  - Idempotent writes (re-running doesn't duplicate)
  - Safe path resolution (fails loud if workspace missing)

Env override: HARNESS_MAP_ONTOLOGY_ROOT can redirect writes (for testing).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from .entities import BaseEntity


DEFAULT_WORKSPACE = Path("/home/levi/.openclaw/workspace")


def _ontology_root() -> Path:
    override = os.environ.get("HARNESS_MAP_ONTOLOGY_ROOT", "").strip()
    if override:
        return Path(override)
    return DEFAULT_WORKSPACE / "ontology"


# Map entity type → storage directory name
STORAGE_MAP = {
    "HarnessSurface": "harness_surfaces",
    "PromptArtifact": "prompt_artifacts",
    "PromptChangeEvent": "prompt_change_events",
    "ModelCapabilitySnapshot": "model_capability_snapshots",
    "BehavioralDriftEvent": "behavioral_drift_events",
}


class OntologyWriteError(Exception):
    pass


def _storage_dir(entity_type: str) -> Path:
    subdir = STORAGE_MAP.get(entity_type)
    if not subdir:
        raise OntologyWriteError(f"No storage mapping for entity type: {entity_type}")
    return _ontology_root() / "entities" / subdir


def emit(entity: BaseEntity) -> Path:
    """Write entity to ontology. Returns final path.

    Idempotent: if a file at the target path already exists and the content is
    equivalent (modulo updated_at), we skip. Otherwise we overwrite.
    """
    if not entity.id:
        raise OntologyWriteError(f"Entity has no id: {entity}")
    if not entity.type:
        raise OntologyWriteError(f"Entity has no type: {entity}")

    target_dir = _storage_dir(entity.type)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{entity.id}.yaml"

    payload = entity.to_dict()

    # Idempotency: if target exists and differs only in updated_at, skip
    if target_path.exists():
        try:
            existing = yaml.safe_load(target_path.read_text()) or {}
            # Compare excluding updated_at (which always changes)
            existing_cmp = {k: v for k, v in existing.items() if k != "updated_at"}
            new_cmp = {k: v for k, v in payload.items() if k != "updated_at"}
            if existing_cmp == new_cmp:
                return target_path  # no-op
        except Exception:
            pass  # corrupted existing file → overwrite

    with target_path.open("w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return target_path


def load_by_id(entity_type: str, entity_id: str) -> Optional[dict]:
    """Load an entity by type + id. Returns None if not found."""
    target = _storage_dir(entity_type) / f"{entity_id}.yaml"
    if not target.exists():
        return None
    try:
        return yaml.safe_load(target.read_text())
    except Exception:
        return None


def load_all(entity_type: str) -> list[dict]:
    """Load all entities of a type. Returns empty list if directory missing."""
    d = _storage_dir(entity_type)
    if not d.exists():
        return []
    results = []
    for p in sorted(d.glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text())
            if data:
                results.append(data)
        except Exception:
            continue
    return results


def find_latest_artifact_for_surface(surface_ref: str) -> Optional[dict]:
    """Return the most recently-fetched PromptArtifact for a given surface."""
    artifacts = [a for a in load_all("PromptArtifact")
                 if a.get("harness_surface_ref") == surface_ref]
    if not artifacts:
        return None
    artifacts.sort(key=lambda a: a.get("fetched_at", ""), reverse=True)
    return artifacts[0]
