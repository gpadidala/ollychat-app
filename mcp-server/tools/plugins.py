"""Plugin tools — list / detail / settings."""
from __future__ import annotations

from grafana_client import client_for
from registry import tool


@tool()
async def list_plugins(
    type_filter: str | None = None,
    enabled_only: bool = False,
    role: str = "viewer",
) -> list[dict]:
    """List all Grafana plugins. type_filter: datasource | panel | app | renderer."""
    c = client_for(role)
    params: dict = {}
    if type_filter:
        params["type"] = type_filter
    if enabled_only:
        params["enabled"] = "true"
    raw = await c.get("/api/plugins", params=params) or []
    return [{
        "id": p.get("id", ""),
        "name": p.get("name", ""),
        "type": p.get("type", ""),
        "category": p.get("category", ""),
        "enabled": p.get("enabled", False),
        "pinned": p.get("pinned", False),
        "version": (p.get("info") or {}).get("version", ""),
        "hasUpdate": p.get("hasUpdate", False),
        "signature": p.get("signature", ""),
    } for p in raw]


@tool()
async def get_plugin(plugin_id: str, role: str = "viewer") -> dict:
    """Get full metadata for a single plugin by id (e.g. 'grafana-piechart-panel')."""
    c = client_for(role)
    raw = await c.get(f"/api/plugins/{plugin_id}/settings") or {}
    return {
        "id": raw.get("id", plugin_id),
        "name": raw.get("name", ""),
        "type": raw.get("type", ""),
        "enabled": raw.get("enabled", False),
        "pinned": raw.get("pinned", False),
        "version": (raw.get("info") or {}).get("version", ""),
        "description": (raw.get("info") or {}).get("description", ""),
        "author": (raw.get("info") or {}).get("author", {}),
        "signature": raw.get("signature", ""),
        "json_data": raw.get("jsonData", {}),
    }
