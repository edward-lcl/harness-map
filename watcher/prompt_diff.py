"""Diff generation + material-change classification.

Given old_content and new_content, produces unified diff + classification
of whether the change is "material" (notify) or "log-only" (changelog only).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import List, Optional


MATERIAL_SIZE_DELTA_FRACTION = 0.20  # 20% size change is material


# Patterns that suggest safety-relevant text
SAFETY_KEYWORDS = [
    r"\brefuse\b", r"\bdecline\b", r"\bdisallow\b",
    r"\bsafety\b", r"\bharm\b", r"\bdanger\b",
    r"\bweapon\b", r"\bexploit\b", r"\billegal\b",
    r"\bCSAM\b", r"\bchild\b", r"\bminor\b",
    r"\bsuicide\b", r"\bself[- ]harm\b",
    r"\bshould (?:not|never)\b", r"\bdo not\b",
    r"\bnever\b(?= (?:divulge|reveal|share|discuss))",
]

# Section header patterns (markdown + prose)
SECTION_PATTERN = re.compile(r"^(#{1,4}\s+.+|[A-Z][A-Za-z ]{3,60}:)\s*$", re.MULTILINE)

# Tool/function mention — crude but catches most cases
TOOL_PATTERN = re.compile(
    r"\b(?:call|invoke|use|the)\s+`?([a-z_][a-zA-Z0-9_]{2,})`?\s+(?:tool|function|skill)\b"
    r"|`([a-z_][a-zA-Z0-9_]{2,})\(`"
    r"|\b([a-z_][a-z_0-9]{3,})_agent\b",
    re.IGNORECASE,
)


@dataclass
class DiffResult:
    unified_diff: str
    old_size: int
    new_size: int
    size_delta_fraction: float
    material: bool
    reasons: List[str]
    new_sections: List[str]
    removed_sections: List[str]
    new_tools: List[str]
    removed_tools: List[str]
    safety_changes: List[str]


def _extract_sections(text: str) -> set:
    return set(m.strip() for m in SECTION_PATTERN.findall(text))


def _extract_tools(text: str) -> set:
    out = set()
    for match in TOOL_PATTERN.finditer(text):
        for g in match.groups():
            if g and len(g) >= 3 and g.lower() not in {"the", "for", "and", "but", "use"}:
                out.add(g.lower())
    return out


def _safety_line_diff(old: str, new: str) -> List[str]:
    """Return safety-relevant lines that appear in new but not old, or vice versa."""
    old_lines = set(old.splitlines())
    new_lines = set(new.splitlines())
    added = new_lines - old_lines
    removed = old_lines - new_lines
    changes = []
    for line in list(added)[:20]:  # cap for readability
        if any(re.search(p, line, re.IGNORECASE) for p in SAFETY_KEYWORDS):
            changes.append(f"+ {line.strip()[:200]}")
    for line in list(removed)[:20]:
        if any(re.search(p, line, re.IGNORECASE) for p in SAFETY_KEYWORDS):
            changes.append(f"- {line.strip()[:200]}")
    return changes


def classify(old_content: Optional[str], new_content: str) -> DiffResult:
    """Classify a change as material or log-only."""
    if old_content is None:
        # New file
        return DiffResult(
            unified_diff="",
            old_size=0,
            new_size=len(new_content),
            size_delta_fraction=1.0,
            material=True,
            reasons=["new_file"],
            new_sections=sorted(_extract_sections(new_content))[:20],
            removed_sections=[],
            new_tools=sorted(_extract_tools(new_content))[:30],
            removed_tools=[],
            safety_changes=[],
        )

    reasons = []
    old_size = len(old_content)
    new_size = len(new_content)
    size_delta = abs(new_size - old_size) / max(old_size, 1)

    if size_delta >= MATERIAL_SIZE_DELTA_FRACTION:
        reasons.append(f"size_delta_{size_delta:.2%}")

    old_sections = _extract_sections(old_content)
    new_sections = _extract_sections(new_content)
    added_sections = sorted(new_sections - old_sections)
    removed_sections = sorted(old_sections - new_sections)
    if added_sections or removed_sections:
        reasons.append("sections_changed")

    old_tools = _extract_tools(old_content)
    new_tools = _extract_tools(new_content)
    added_tools = sorted(new_tools - old_tools)
    removed_tools = sorted(old_tools - new_tools)
    if added_tools:
        reasons.append("new_tools")
    if removed_tools:
        reasons.append("removed_tools")

    safety_changes = _safety_line_diff(old_content, new_content)
    if safety_changes:
        reasons.append("safety_rule_changed")

    unified = "\n".join(difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        lineterm="",
        n=2,
    ))

    material = bool(reasons)

    return DiffResult(
        unified_diff=unified,
        old_size=old_size,
        new_size=new_size,
        size_delta_fraction=size_delta,
        material=material,
        reasons=reasons,
        new_sections=added_sections[:20],
        removed_sections=removed_sections[:20],
        new_tools=added_tools[:30],
        removed_tools=removed_tools[:30],
        safety_changes=safety_changes,
    )
