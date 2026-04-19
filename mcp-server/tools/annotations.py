"""Annotation tools — list / create / delete."""
from __future__ import annotations

from grafana_client import client_for
from registry import tool


@tool()
async def list_annotations(
    dashboard_uid: str | None = None,
    time_from: int | None = None,
    time_to: int | None = None,
    tag: list[str] | None = None,
    limit: int = 100,
    role: str = "viewer",
) -> list[dict]:
    """List annotations, optionally scoped to a dashboard or time range (ms)."""
    c = client_for(role)
    params: dict = {"limit": limit}
    if dashboard_uid:
        params["dashboardUID"] = dashboard_uid
    if time_from is not None:
        params["from"] = time_from
    if time_to is not None:
        params["to"] = time_to
    if tag:
        params["tags"] = tag
    raw = await c.get("/api/annotations", params=params) or []
    return [{
        "id": a.get("id", 0),
        "alertId": a.get("alertId", 0),
        "dashboardUID": a.get("dashboardUID", ""),
        "panelId": a.get("panelId", 0),
        "time": a.get("time", 0),
        "timeEnd": a.get("timeEnd", 0),
        "text": a.get("text", ""),
        "tags": a.get("tags") or [],
        "userId": a.get("userId", 0),
    } for a in raw]


@tool()
async def create_annotation(
    text: str,
    dashboard_uid: str | None = None,
    panel_id: int | None = None,
    time_ms: int | None = None,
    time_end_ms: int | None = None,
    tags: list[str] | None = None,
    role: str = "editor",
) -> dict:
    """Create a dashboard / global annotation (deploy marker, incident, etc.)."""
    c = client_for(role)
    body: dict = {"text": text, "tags": tags or []}
    if dashboard_uid:
        body["dashboardUID"] = dashboard_uid
    if panel_id is not None:
        body["panelId"] = panel_id
    if time_ms is not None:
        body["time"] = time_ms
    if time_end_ms is not None:
        body["timeEnd"] = time_end_ms
    raw = await c.post("/api/annotations", body)
    return {
        "ok": True,
        "id": (raw or {}).get("id", 0),
        "message": (raw or {}).get("message", "") or f"Annotation created",
    }


@tool()
async def delete_annotation(annotation_id: int, role: str = "editor") -> dict:
    """Delete an annotation by numeric ID."""
    c = client_for(role)
    await c.delete(f"/api/annotations/{annotation_id}")
    return {"ok": True, "id": annotation_id, "status": "deleted",
            "message": f"Annotation {annotation_id} deleted"}
