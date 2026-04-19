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
