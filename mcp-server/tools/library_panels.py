"""Library panel tools — reusable panels shared across dashboards."""
from __future__ import annotations

from grafana_client import client_for
from registry import tool


@tool()
async def list_library_panels(
    query: str = "",
    limit: int = 100,
    role: str = "viewer",
) -> list[dict]:
    """List reusable library panels, optionally filtered by title query."""
    c = client_for(role)
    params: dict = {"perPage": limit}
    if query:
        params["searchString"] = query
    raw = await c.get("/api/library-elements", params=params) or {}
    elements = ((raw.get("result") or {}).get("elements")) or []
    return [{
        "uid": e.get("uid", ""),
        "name": e.get("name", ""),
        "description": e.get("description", ""),
        "kind": e.get("kind", 0),
        "folder_uid": e.get("folderUid", ""),
        "type": (e.get("model") or {}).get("type", ""),
    } for e in elements]


@tool()
async def get_library_panel(uid: str, role: str = "viewer") -> dict:
    """Get a single library panel by UID (returns its full panel model)."""
    c = client_for(role)
    raw = await c.get(f"/api/library-elements/{uid}") or {}
    element = raw.get("result") or {}
    model = element.get("model") or {}
    return {
        "uid": element.get("uid", uid),
        "name": element.get("name", ""),
        "description": element.get("description", ""),
        "type": model.get("type", ""),
        "model": model,
    }
