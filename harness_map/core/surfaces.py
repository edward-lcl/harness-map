"""HarnessSurface registry — bootstraps known surfaces.

Rather than building this dynamically from leaked prompt filenames (which gives
us dirty slugs), we maintain a small canonical registry and map leaked files
onto it. Filenames are normalized to surface_slug via KNOWN_SURFACES.
"""

from __future__ import annotations

import re
from typing import Optional

from .entities import HarnessSurface
from .ontology_client import emit


# Canonical surface registry.
# Key: a matcher pattern (regex) against filename.
# Value: (surface_slug, display_name, surface_type, base_models)
KNOWN_SURFACES: list[tuple[str, tuple[str, str, str, list[str]]]] = [
    (
        r"^Claude[-_]Opus[-_]4\.7",
        ("claude-opus-4-7-consumer", "Claude Opus 4.7 (claude.ai consumer)",
         "consumer-assistant", ["claude-opus-4-7"]),
    ),
    (
        r"^Claude[-_]Opus[-_]4\.6",
        ("claude-opus-4-6-consumer", "Claude Opus 4.6 (claude.ai consumer)",
         "consumer-assistant", ["claude-opus-4-6"]),
    ),
    (
        r"^Claude[-_]?4\.5[-_]?Opus",
        ("claude-opus-4-5-consumer", "Claude Opus 4.5 (claude.ai consumer)",
         "consumer-assistant", ["claude-opus-4-5"]),
    ),
    (
        r"^Claude[-_]Sonnet[-_]?4\.5",
        ("claude-sonnet-4-5-consumer", "Claude Sonnet 4.5 (claude.ai consumer)",
         "consumer-assistant", ["claude-sonnet-4-5"]),
    ),
    (
        r"^Claude[-_]Sonnet[-_]3\.7",
        ("claude-sonnet-3-7-consumer", "Claude Sonnet 3.7 (claude.ai consumer)",
         "consumer-assistant", ["claude-sonnet-3-7"]),
    ),
    (
        r"^Claude[-_]Sonnet[-_]3\.5",
        ("claude-sonnet-3-5-consumer", "Claude Sonnet 3.5 (claude.ai consumer)",
         "consumer-assistant", ["claude-sonnet-3-5"]),
    ),
    (
        r"^Claude[-_]4\.1",
        ("claude-4-1-consumer", "Claude 4.1 (claude.ai consumer)",
         "consumer-assistant", ["claude-4-1"]),
    ),
    (
        r"^Claude[-_]4\b|^Claude_4\.txt",
        ("claude-4-consumer", "Claude 4 (claude.ai consumer)",
         "consumer-assistant", ["claude-4"]),
    ),
    (
        r"^Claude[-_]Design",
        ("claude-design", "Claude Design (design-artifact tool)",
         "design-tool", ["claude-opus-4-7"]),
    ),
    (
        r"^Claude[-__]Code",
        ("claude-code", "Claude Code (coding assistant CLI)",
         "code-agent", ["claude-sonnet-4-5", "claude-opus-4-7"]),
    ),
    (
        r"^UserStyle",
        ("claude-user-styles", "Claude.ai user style modes",
         "specialized-agent", []),
    ),
]


def surface_for_filename(filename: str) -> Optional[tuple[str, str, str, list[str]]]:
    """Map a leaked prompt filename to (surface_slug, display_name, surface_type, base_models)."""
    for pattern, surface_info in KNOWN_SURFACES:
        if re.match(pattern, filename, re.IGNORECASE):
            return surface_info
    return None


def ensure_surface(filename: str, vendor: str = "anthropic") -> Optional[HarnessSurface]:
    """Ensure a HarnessSurface entity exists for a given filename.
    Returns the entity. Idempotent — re-emitting updates last_observed_at only.
    """
    info = surface_for_filename(filename)
    if not info:
        return None
    surface_slug, display_name, surface_type, base_models = info

    surface = HarnessSurface(
        surface_slug=surface_slug,
        vendor=vendor,
        display_name=display_name,
        surface_type=surface_type,
        base_models=base_models,
    )
    emit(surface)
    return surface
