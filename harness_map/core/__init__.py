"""harness-map core — entities, ontology client, config, surface registry."""

from .entities import (
    BaseEntity,
    HarnessSurface,
    PromptArtifact,
    PromptChangeEvent,
    ModelCapabilitySnapshot,
    BehavioralDriftEvent,
    iso_now,
    slugify,
    sha256_hex,
    short_sha,
    make_provenance,
)
from .ontology_client import emit, load_by_id, load_all, find_latest_artifact_for_surface
from .config import load_dotenv, github_token, discord_webhook, billing_proxy_url
from .surfaces import ensure_surface, surface_for_filename, KNOWN_SURFACES

__all__ = [
    "BaseEntity",
    "HarnessSurface",
    "PromptArtifact",
    "PromptChangeEvent",
    "ModelCapabilitySnapshot",
    "BehavioralDriftEvent",
    "iso_now",
    "slugify",
    "sha256_hex",
    "short_sha",
    "make_provenance",
    "emit",
    "load_by_id",
    "load_all",
    "find_latest_artifact_for_surface",
    "load_dotenv",
    "github_token",
    "discord_webhook",
    "billing_proxy_url",
    "ensure_surface",
    "surface_for_filename",
    "KNOWN_SURFACES",
]
