"""Typed entity objects for harness-map.

Each entity maps to a YAML schema under schemas/ and emits to
the workspace ontology under ontology/entities/<type>/<id>.yaml.

Design principles:
  - dataclass + to_dict() — simple, serializable, no ORM magic
  - deterministic IDs — collision-free, idempotent re-emission
  - provenance baked in — every entity knows where it came from
  - boundary/scope/base_type — integrates with existing ontology routing
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, Any


DEFAULT_BOUNDARY = "node-levi"
DEFAULT_SCOPE = "research"
DEFAULT_BASE_TYPE = "Entity"
SOURCE_SYSTEM = "harness-map"


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def sha256_hex(content: str, length: int = 12) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:length]


def short_sha(sha: str, length: int = 8) -> str:
    return sha[:length] if sha else ""


def make_provenance(source_kind: str, captured_by: str = "levi") -> dict:
    return {
        "source_system": SOURCE_SYSTEM,
        "source_kind": source_kind,
        "captured_at": iso_now(),
        "captured_by": captured_by,
    }


@dataclass
class BaseEntity:
    """Shared base. Don't emit directly."""
    id: str = ""
    type: str = ""
    provenance: dict = field(default_factory=dict)
    created_at: str = field(default_factory=iso_now)
    updated_at: str = field(default_factory=iso_now)
    boundary: str = DEFAULT_BOUNDARY
    scope: str = DEFAULT_SCOPE
    base_type: str = DEFAULT_BASE_TYPE

    def to_dict(self) -> dict:
        d = asdict(self)
        # Clean None values for cleaner YAML
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class HarnessSurface(BaseEntity):
    type: str = "HarnessSurface"
    surface_slug: str = ""
    vendor: str = "anthropic"
    display_name: str = ""
    surface_type: str = "consumer-assistant"
    base_models: list = field(default_factory=list)
    first_observed_at: str = field(default_factory=iso_now)
    last_observed_at: str = field(default_factory=iso_now)
    notes: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"harness-{self.vendor}-{self.surface_slug}"
        if not self.provenance:
            self.provenance = make_provenance("surface_registration")


@dataclass
class PromptArtifact(BaseEntity):
    type: str = "PromptArtifact"
    harness_surface_ref: str = ""
    layer: str = "L2"
    source_url: str = ""
    upstream_sha: str = ""
    content_hash: str = ""
    raw_path: str = ""
    metadata: dict = field(default_factory=dict)
    fetched_at: str = field(default_factory=iso_now)
    supersedes_ref: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            surface_slug = self.harness_surface_ref.replace("harness-anthropic-", "").replace("harness-", "")
            date_tag = self.fetched_at[:10].replace("-", "")
            self.id = f"prompt-{surface_slug}-{date_tag}-{short_sha(self.upstream_sha)}"
        if not self.provenance:
            self.provenance = make_provenance("prompt_artifact_capture")


@dataclass
class PromptChangeEvent(BaseEntity):
    type: str = "PromptChangeEvent"
    harness_surface_ref: str = ""
    previous_artifact_ref: Optional[str] = None
    current_artifact_ref: str = ""
    previous_upstream_sha: Optional[str] = None
    current_upstream_sha: str = ""
    change_class: str = "material"
    change_reasons: list = field(default_factory=list)
    deltas: dict = field(default_factory=dict)
    unified_diff: Optional[str] = None
    unified_diff_path: Optional[str] = None
    interpretation: list = field(default_factory=list)
    severity: str = "low"

    def __post_init__(self):
        if not self.id:
            surface_slug = self.harness_surface_ref.replace("harness-anthropic-", "").replace("harness-", "")
            prev = short_sha(self.previous_upstream_sha) if self.previous_upstream_sha else "genesis"
            self.id = f"prompt-change-{surface_slug}-{prev}-{short_sha(self.current_upstream_sha)}"
        if not self.provenance:
            self.provenance = make_provenance("prompt_change_detection")


@dataclass
class ModelCapabilitySnapshot(BaseEntity):
    type: str = "ModelCapabilitySnapshot"
    harness_surface_ref: str = ""
    model_slug: str = ""
    model_returned: Optional[str] = None
    battery_version: str = ""
    battery_probe_count: int = 0
    probes_completed: int = 0
    probes_errored: int = 0
    temperature: float = 0.0
    max_tokens: int = 512
    totals: dict = field(default_factory=dict)
    by_category: dict = field(default_factory=dict)
    results_jsonl_path: str = ""
    run_ts: str = field(default_factory=iso_now)

    def __post_init__(self):
        if not self.id:
            run_compact = self.run_ts.replace(":", "").replace("-", "")
            self.id = f"capsnap-{self.model_slug}-{self.battery_version}-{run_compact}"
        if not self.provenance:
            self.provenance = make_provenance("probe_battery_run")


@dataclass
class BehavioralDriftEvent(BaseEntity):
    type: str = "BehavioralDriftEvent"
    harness_surface_ref: str = ""
    previous_snapshot_ref: str = ""
    current_snapshot_ref: str = ""
    comparison_kind: str = "temporal"
    drift_by_category: dict = field(default_factory=dict)
    notable_probe_drifts: list = field(default_factory=list)
    aggregate_drift_score: float = 0.0
    severity: str = "low"
    interpretation: list = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            ps = short_sha(self.previous_snapshot_ref.split("-")[-1]) if "-" in self.previous_snapshot_ref else "unknown"
            cs = short_sha(self.current_snapshot_ref.split("-")[-1]) if "-" in self.current_snapshot_ref else "unknown"
            self.id = f"behavior-drift-{self.harness_surface_ref.replace('harness-', '')}-{ps}-{cs}"
        if not self.provenance:
            self.provenance = make_provenance("behavioral_differ_run")
