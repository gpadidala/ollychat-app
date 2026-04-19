"""Folder tools — list + create."""
from __future__ import annotations

from grafana_client import client_for
from registry import tool


def _fmt(f: dict) -> dict:
    return {
        "uid": f.get("uid", ""),
        "title": f.get("title", ""),
        "url": f.get("url", ""),
        "parent_uid": f.get("parentUid", ""),
    }


@tool()
async def list_folders(role: str = "viewer") -> list[dict]:
    """List all Grafana folders (dashboard containers)."""
    c = client_for(role)
    raw = await c.get("/api/folders") or []
    return [_fmt(f) for f in raw]


@tool()
async def create_folder(
    title: str,
    parent_uid: str | None = None,
    role: str = "editor",
) -> dict:
    """Create a new Grafana folder."""
    c = client_for(role)
    body: dict = {"title": title}
    if parent_uid:
        body["parentUid"] = parent_uid
    raw = await c.post("/api/folders", body)
    out = _fmt(raw or {})
    out["ok"] = True
    out["status"] = "success"
    out["message"] = f"Folder '{title}' created"
    return out


@tool()
async def get_folder(uid: str, role: str = "viewer") -> dict:
    """Get folder metadata by UID."""
    c = client_for(role)
    raw = await c.get(f"/api/folders/{uid}") or {}
    out = _fmt(raw)
    out["description"] = raw.get("description", "")
    return out


@tool()
async def update_folder(
    uid: str,
    title: str | None = None,
    role: str = "editor",
) -> dict:
    """Rename or update a folder (title only for now)."""
    c = client_for(role)
    current = await c.get(f"/api/folders/{uid}") or {}
    body = {"title": title or current.get("title", ""), "version": current.get("version", 0), "overwrite": True}
    raw = await c.put(f"/api/folders/{uid}", body)
    out = _fmt(raw or {})
    out["ok"] = True
    out["status"] = "updated"
    out["message"] = f"Folder {uid} updated"
    return out


@tool()
async def delete_folder(uid: str, role: str = "admin") -> dict:
    """Delete a folder by UID. Requires admin — deletes all dashboards inside."""
    c = client_for(role)
    await c.delete(f"/api/folders/{uid}?forceDeleteRules=true")
    return {"ok": True, "uid": uid, "status": "deleted", "message": f"Folder {uid} deleted"}
