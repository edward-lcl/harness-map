"""Discord webhook notification for material prompt changes (moved from flat script)."""

from __future__ import annotations

from typing import Optional

import requests

from ..core.config import discord_webhook


def notify(
    *,
    title: str,
    description: str,
    fields: list[dict] | None = None,
    color: int = 0x3b82f6,
) -> bool:
    url = discord_webhook()
    if not url:
        print(f"[notify] HARNESS_MAP_DISCORD_WEBHOOK not set; skipping: {title}")
        return False

    title = title[:256]
    description = description[:4000]

    embed = {"title": title, "description": description, "color": color}
    if fields:
        clamped = []
        for f in fields[:25]:
            clamped.append({
                "name": str(f.get("name", ""))[:256],
                "value": str(f.get("value", ""))[:1024],
                "inline": bool(f.get("inline", False)),
            })
        embed["fields"] = clamped

    try:
        resp = requests.post(url, json={"embeds": [embed]}, timeout=10)
        if resp.status_code >= 400:
            print(f"[notify] Discord returned {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"[notify] Error: {e}")
        return False


def format_prompt_change(
    *,
    surface_display_name: str,
    filename: str,
    reasons: list[str],
    new_tools: list[str],
    new_sections: list[str],
    safety_changes: list[str],
    old_size: int,
    new_size: int,
    raw_url: str,
    severity: str,
    event_id: str,
) -> dict:
    if "new_file" in reasons:
        title = f"🆕 New prompt observed: {surface_display_name}"
        color = 0x10b981
    elif "safety_rule_changed" in reasons:
        title = f"⚠️ Safety rules changed: {surface_display_name}"
        color = 0xef4444
    elif "new_tools" in reasons:
        title = f"🔧 New tools in: {surface_display_name}"
        color = 0xf59e0b
    else:
        title = f"📝 Updated: {surface_display_name}"
        color = 0x3b82f6

    description = (
        f"**Severity:** `{severity}` · **Reasons:** `{', '.join(reasons)}`\n"
        f"**Size:** {old_size:,} → {new_size:,} bytes\n"
        f"**Event:** `{event_id}`"
    )

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
            "name": f"Safety rule changes ({min(6, len(safety_changes))} shown)",
            "value": "\n".join(safety_changes[:6])[:1024] or "none",
            "inline": False,
        })
    fields.append({
        "name": "Source",
        "value": f"[`{filename}`]({raw_url})",
        "inline": False,
    })

    return {"title": title, "description": description, "fields": fields, "color": color}
