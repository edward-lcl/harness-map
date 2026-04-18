"""Discord webhook notification for material prompt changes."""

from __future__ import annotations

import os
import json
from typing import Optional

import requests


def _webhook_url() -> Optional[str]:
    return os.environ.get("HARNESS_MAP_DISCORD_WEBHOOK", "").strip() or None


def notify(
    *,
    title: str,
    description: str,
    fields: list[dict] | None = None,
    color: int = 0x3b82f6,  # blue
) -> bool:
    """Post a material-change notification. Returns True on success.

    Silent no-op if webhook env var not set (keeps dev/test from spamming).
    """
    url = _webhook_url()
    if not url:
        print(f"[notify] HARNESS_MAP_DISCORD_WEBHOOK not set; skipping: {title}")
        return False

    # Discord limits: title 256, description 4096, field.value 1024, total 6000
    title = title[:256]
    description = description[:4000]

    embed = {
        "title": title,
        "description": description,
        "color": color,
    }
    if fields:
        # Clamp field values
        clamped = []
        for f in fields[:25]:
            clamped.append({
                "name": str(f.get("name", ""))[:256],
                "value": str(f.get("value", ""))[:1024],
                "inline": bool(f.get("inline", False)),
            })
        embed["fields"] = clamped

    payload = {"embeds": [embed]}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code >= 400:
            print(f"[notify] Discord returned {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"[notify] Error: {e}")
        return False


def format_material_change(
    *,
    filename: str,
    reasons: list[str],
    new_tools: list[str],
    new_sections: list[str],
    safety_changes: list[str],
    old_size: int,
    new_size: int,
    raw_url: str,
) -> dict:
    """Build title/description/fields for a material change notification."""
    if "new_file" in reasons:
        title = f"🆕 New Anthropic prompt leaked: {filename}"
        color = 0x10b981  # green
    elif "safety_rule_changed" in reasons:
        title = f"⚠️ Safety rules changed in {filename}"
        color = 0xef4444  # red
    elif "new_tools" in reasons:
        title = f"🔧 New tools in {filename}"
        color = 0xf59e0b  # amber
    else:
        title = f"📝 {filename} updated"
        color = 0x3b82f6  # blue

    description = f"Material change detected. Reasons: `{', '.join(reasons)}`\nSize: {old_size} → {new_size} bytes"

    fields = []
    if new_tools:
        fields.append({
            "name": f"New tools ({len(new_tools)})",
            "value": ", ".join(f"`{t}`" for t in new_tools[:15]) or "none",
            "inline": False,
        })
    if new_sections:
        fields.append({
            "name": f"New sections ({len(new_sections)})",
            "value": "\n".join(f"• {s[:80]}" for s in new_sections[:8]) or "none",
            "inline": False,
        })
    if safety_changes:
        fields.append({
            "name": f"Safety rule changes (top {min(6, len(safety_changes))})",
            "value": "\n".join(safety_changes[:6])[:1024] or "none",
            "inline": False,
        })
    fields.append({
        "name": "Source",
        "value": raw_url,
        "inline": False,
    })

    return {"title": title, "description": description, "fields": fields, "color": color}
