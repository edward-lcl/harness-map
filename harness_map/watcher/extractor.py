"""Pattern-based metadata extraction (injection-safe, no LLM)."""

from __future__ import annotations

import re
from typing import List


SECTION_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
PROSE_SECTION_PATTERN = re.compile(r"^([A-Z][A-Za-z /&]{3,60}):\s*$", re.MULTILINE)
TOOL_DEF_PATTERN = re.compile(
    r"\b(?:tool|function|command|skill):\s*`?([a-z_][a-zA-Z0-9_]{2,})`?",
    re.IGNORECASE,
)
INLINE_TOOL_PATTERN = re.compile(
    r"`([a-z_][a-zA-Z0-9_]{2,})\(`"
    r"|\bcall(?:ing)?\s+`([a-z_][a-zA-Z0-9_]{2,})`"
    r"|\b([a-z_][a-z_0-9]{3,})_agent\b",
)
SAFETY_HINT = re.compile(
    r"\b(?:refuse|decline|never|do not|must not|disallow|cannot|safety|harm)\b",
    re.IGNORECASE,
)
MODEL_IDENT = re.compile(
    r"\b(claude|opus|sonnet|haiku|mythos|design)[ -](?:[\d.]+|code|design)?\b",
    re.IGNORECASE,
)


def extract_metadata(content: str) -> dict:
    """Pattern-based. Does NOT invoke any LLM. Safe against prompt-injection content."""
    sections_md = [m.group(2).strip() for m in SECTION_PATTERN.finditer(content)]
    sections_prose = [m.group(1).strip() for m in PROSE_SECTION_PATTERN.finditer(content)]
    sections = sections_md + sections_prose

    tools = set()
    for m in TOOL_DEF_PATTERN.finditer(content):
        tools.add(m.group(1).lower())
    for m in INLINE_TOOL_PATTERN.finditer(content):
        for g in m.groups():
            if g and g.lower() not in {"the", "for", "and", "but", "use", "get", "set"}:
                tools.add(g.lower())

    safety_hits = len(SAFETY_HINT.findall(content))

    models = set()
    for m in MODEL_IDENT.finditer(content):
        models.add(m.group(0).lower().strip())

    return {
        "raw_size_bytes": len(content.encode("utf-8")),
        "raw_line_count": content.count("\n") + 1,
        "raw_word_count": len(content.split()),
        "section_count": len(sections),
        "sections": sections[:50],
        "tools_mentioned": sorted(tools)[:50],
        "safety_rule_count": safety_hits,
        "model_hints": sorted(models)[:10],
    }


def sanitize_for_llm(content: str) -> str:
    """Strip known prompt-injection markers before any LLM processing."""
    patterns = [
        r"<NEW_PARADIGM>",
        r"#MOST IMPORTANT DIRECTIVE#",
        r"5h1f7 y0ur f0cu5",
        r"Shift your focus now to",
        r"\[DISREGARD PREV\. INSTRUCTS\]",
        r"\{\*CLEAR YOUR MIND\*\}",
        r"ignore (?:all )?previous instructions",
        r"you are now",
        r"system:\s*$",
    ]
    cleaned = content
    for p in patterns:
        cleaned = re.sub(p, "[REDACTED:injection]", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    return cleaned
