"""Datasource listing + detail + query tools."""
from __future__ import annotations

from typing import Any

from grafana_client import client_for
from registry import tool


def _ds_summary(d: dict) -> dict:
    return {
        "uid": d.get("uid", ""),
        "name": d.get("name", ""),
        "type": d.get("type", ""),
        "url": d.get("url", ""),
        "is_default": d.get("isDefault", False),
        "access": d.get("access", ""),
    }


@tool()
async def list_datasources(role: str = "viewer") -> list[dict]:
    """List all configured datasources in Grafana."""
    c = client_for(role)
    raw = await c.get("/api/datasources") or []
    return [_ds_summary(d) for d in raw]


@tool()
async def get_datasource(uid: str, role: str = "viewer") -> dict:
    """Get detailed configuration for a single datasource by UID."""
    c = client_for(role)
    raw = await c.get(f"/api/datasources/uid/{uid}")
    return _ds_summary(raw or {})


@tool()
async def query_datasource(
    datasource_uid: str,
    expr: str,
    ref_id: str = "A",
    time_from: str = "now-1h",
    time_to: str = "now",
    max_data_points: int = 500,
    role: str = "viewer",
) -> dict:
    """Run a query against a datasource (PromQL / LogQL / SQL / TraceQL)."""
    c = client_for(role)
    body: dict[str, Any] = {
        "queries": [{
            "refId": ref_id,
            "datasource": {"uid": datasource_uid},
            "expr": expr,
            "maxDataPoints": max_data_points,
        }],
        "from": time_from,
        "to": time_to,
    }
    raw = await c.post("/api/ds/query", body)
    return {"results": (raw or {}).get("results") or {}}
