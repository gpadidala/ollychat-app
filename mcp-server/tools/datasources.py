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


@tool()
async def list_metric_names(
    datasource_uid: str | None = None,
    match: str | None = None,
    role: str = "viewer",
) -> list[str]:
    """List every metric name exposed by a Prometheus datasource (optionally
    filtered by a regex ``match``). Auto-discovers the default Prometheus
    datasource if ``datasource_uid`` is omitted.
    """
    c = client_for(role)
    if not datasource_uid:
        for d in (await c.get("/api/datasources") or []):
            if (d.get("type") or "").lower() in ("prometheus", "grafanacloud-prometheus"):
                datasource_uid = d.get("uid")
                break
    if not datasource_uid:
        return []
    raw = await c.get(f"/api/datasources/proxy/uid/{datasource_uid}/api/v1/label/__name__/values")
    names = list((raw or {}).get("data") or [])
    if match:
        import re
        try:
            rx = re.compile(match, re.IGNORECASE)
            names = [n for n in names if rx.search(n)]
        except re.error:
            names = [n for n in names if match.lower() in n.lower()]
    return sorted(names)


@tool()
async def list_label_values(
    datasource_uid: str,
    label: str,
    match: str | None = None,
    role: str = "viewer",
) -> list[str]:
    """List all values for a given Prometheus label (e.g. 'service', 'pod')."""
    c = client_for(role)
    raw = await c.get(f"/api/datasources/proxy/uid/{datasource_uid}/api/v1/label/{label}/values")
    values = list((raw or {}).get("data") or [])
    if match:
        values = [v for v in values if match.lower() in str(v).lower()]
    return sorted(values)


@tool()
async def query_loki(
    datasource_uid: str,
    logql: str,
    time_from: str = "now-1h",
    time_to: str = "now",
    limit: int = 200,
    role: str = "viewer",
) -> dict:
    """Run a LogQL query against a Loki datasource. Returns streams + values."""
    c = client_for(role)
    body: dict = {
        "queries": [{
            "refId": "A",
            "datasource": {"uid": datasource_uid, "type": "loki"},
            "expr": logql,
            "queryType": "range",
            "maxLines": limit,
        }],
        "from": time_from,
        "to": time_to,
    }
    raw = await c.post("/api/ds/query", body) or {}
    frames = ((raw.get("results") or {}).get("A") or {}).get("frames") or []
    lines: list[dict] = []
    for f in frames:
        fields = (f.get("schema") or {}).get("fields") or []
        values = (f.get("data") or {}).get("values") or []
        if not fields or not values:
            continue
        field_names = [x.get("name", "") for x in fields]
        rows = min(len(v) for v in values) if values else 0
        for i in range(min(rows, limit)):
            row = {name: values[j][i] for j, name in enumerate(field_names)}
            lines.append(row)
    return {"lines": lines[:limit], "total": len(lines)}


@tool()
async def query_tempo(
    datasource_uid: str,
    traceql: str,
    time_from: str = "now-1h",
    time_to: str = "now",
    limit: int = 20,
    role: str = "viewer",
) -> dict:
    """Run a TraceQL query against a Tempo datasource. Returns trace summaries."""
    c = client_for(role)
    body: dict = {
        "queries": [{
            "refId": "A",
            "datasource": {"uid": datasource_uid, "type": "tempo"},
            "query": traceql,
            "queryType": "traceql",
            "limit": limit,
        }],
        "from": time_from,
        "to": time_to,
    }
    raw = await c.post("/api/ds/query", body) or {}
    frames = ((raw.get("results") or {}).get("A") or {}).get("frames") or []
    traces: list[dict] = []
    for f in frames:
        fields = (f.get("schema") or {}).get("fields") or []
        values = (f.get("data") or {}).get("values") or []
        if not fields or not values:
            continue
        field_names = [x.get("name", "") for x in fields]
        rows = min(len(v) for v in values) if values else 0
        for i in range(min(rows, limit)):
            traces.append({name: values[j][i] for j, name in enumerate(field_names)})
    return {"traces": traces[:limit], "total": len(traces)}
