"""Dashboard tools — list / search / get / panels / create (smart + plain) / update / delete."""
from __future__ import annotations

from typing import Any

from grafana_client import client_for
from registry import tool

from ._panel_templates import build_panels_from_metrics, build_red_panels


def _summary(raw: dict) -> dict:
    return {
        "uid": raw.get("uid", ""),
        "title": raw.get("title", ""),
        "url": raw.get("url", ""),
        "folder_title": raw.get("folderTitle", ""),
        "folder_uid": raw.get("folderUid", ""),
        "tags": raw.get("tags", []) or [],
        "type": raw.get("type", "dash-db"),
    }


@tool()
async def list_dashboards(
    folder_uid: str | None = None,
    tags: list[str] | None = None,
    limit: int = 100,
    role: str = "viewer",
) -> list[dict]:
    """List dashboards, optionally filtered by folder UID and tags."""
    params: dict[str, Any] = {"type": "dash-db", "limit": limit}
    if folder_uid:
        params["folderUIDs"] = folder_uid
    if tags:
        params["tag"] = tags  # httpx repeats the param for each value
    c = client_for(role)
    raw = await c.get("/api/search", params=params)
    return [_summary(x) for x in (raw or [])]


@tool()
async def search_dashboards(
    query: str,
    tags: list[str] | None = None,
    limit: int = 50,
    role: str = "viewer",
) -> list[dict]:
    """Full-text search for dashboards by title."""
    params: dict[str, Any] = {"query": query, "type": "dash-db", "limit": limit}
    if tags:
        params["tag"] = tags
    c = client_for(role)
    raw = await c.get("/api/search", params=params)
    return [_summary(x) for x in (raw or [])]


def _panel_slim(p: dict) -> dict:
    ds = p.get("datasource") or {}
    ds_uid = ds if isinstance(ds, str) else ds.get("uid", "")
    return {
        "id": p.get("id", 0),
        "title": p.get("title", ""),
        "type": p.get("type", ""),
        "datasource": ds_uid,
        "description": p.get("description", ""),
    }


@tool()
async def get_dashboard(uid: str, role: str = "viewer") -> dict:
    """Retrieve a complete dashboard by UID including all panels."""
    c = client_for(role)
    raw = await c.get(f"/api/dashboards/uid/{uid}")
    d = (raw or {}).get("dashboard", {}) or {}
    meta = (raw or {}).get("meta", {}) or {}
    return {
        "uid": d.get("uid", ""),
        "title": d.get("title", ""),
        "version": d.get("version", 0),
        "tags": d.get("tags", []) or [],
        "panels": [_panel_slim(p) for p in (d.get("panels", []) or [])],
        "folder_uid": meta.get("folderUid", ""),
        "folder_title": meta.get("folderTitle", ""),
        "url": meta.get("url", ""),
    }


@tool()
async def get_dashboard_panels(uid: str, role: str = "viewer") -> list[dict]:
    """List all panels in a specific dashboard."""
    detail = await get_dashboard(uid=uid, role=role)
    return detail.get("panels", [])


@tool()
async def create_dashboard(
    title: str,
    tags: list[str] | None = None,
    folder_uid: str | None = None,
    panels: list[dict] | None = None,
    description: str = "",
    role: str = "editor",
) -> dict:
    """Create a new dashboard. Minimal by default; pass `panels` for custom layouts."""
    c = client_for(role)
    dash: dict[str, Any] = {
        "uid": None,
        "title": title,
        "tags": tags or [],
        "timezone": "browser",
        "schemaVersion": 38,
        "version": 0,
        "refresh": "30s",
        "panels": panels or [],
    }
    if description:
        dash["description"] = description
    body: dict[str, Any] = {
        "dashboard": dash,
        "overwrite": False,
        "message": "Created via O11yBot",
    }
    if folder_uid:
        body["folderUid"] = folder_uid
    raw = await c.post("/api/dashboards/db", body)
    return {
        "ok": True,
        "uid": (raw or {}).get("uid", ""),
        "url": (raw or {}).get("url", ""),
        "version": (raw or {}).get("version", 0),
        "status": (raw or {}).get("status", "success"),
        "message": f"Dashboard '{title}' created",
    }


@tool()
async def update_dashboard(
    uid: str,
    title: str | None = None,
    tags: list[str] | None = None,
    panels: list[dict] | None = None,
    description: str | None = None,
    role: str = "editor",
) -> dict:
    """Update an existing dashboard in-place. Only provided fields change."""
    c = client_for(role)
    current = await c.get(f"/api/dashboards/uid/{uid}")
    dash = ((current or {}).get("dashboard") or {}).copy()
    if title is not None:
        dash["title"] = title
    if tags is not None:
        dash["tags"] = tags
    if panels is not None:
        dash["panels"] = panels
    if description is not None:
        dash["description"] = description
    body: dict[str, Any] = {
        "dashboard": dash,
        "overwrite": True,
        "message": "Updated via O11yBot",
    }
    meta = (current or {}).get("meta", {}) or {}
    if meta.get("folderUid"):
        body["folderUid"] = meta["folderUid"]
    raw = await c.post("/api/dashboards/db", body)
    return {
        "ok": True,
        "uid": (raw or {}).get("uid", uid),
        "url": (raw or {}).get("url", ""),
        "version": (raw or {}).get("version", 0),
        "status": (raw or {}).get("status", "success"),
        "message": f"Dashboard {uid} updated",
    }


@tool()
async def delete_dashboard(uid: str, role: str = "admin") -> dict:
    """Delete a dashboard by UID."""
    c = client_for(role)
    await c.delete(f"/api/dashboards/uid/{uid}")
    return {"ok": True, "uid": uid, "status": "deleted", "message": f"Dashboard {uid} deleted"}


async def _default_prometheus_uid(role: str) -> str:
    c = client_for(role)
    ds_list = await c.get("/api/datasources") or []
    for d in ds_list:
        if (d.get("type") or "").lower() in ("prometheus", "grafanacloud-prometheus"):
            return d.get("uid") or ""
    for d in ds_list:
        if d.get("isDefault"):
            return d.get("uid") or ""
    return ""


# Intent synonyms — map user-facing observability terms to the tokens that
# typically appear in Prometheus metric names. So "latency" / "slow" / "p95"
# all expand to match {duration, latency, seconds, time, ms}.
_SYNONYMS: dict[str, list[str]] = {
    "latency": ["latency", "duration", "seconds", "time", "ms"],
    "duration": ["duration", "latency", "seconds"],
    "slow": ["latency", "duration", "seconds"],
    "p95": ["bucket", "duration", "latency"],
    "p99": ["bucket", "duration", "latency"],
    "errors": ["error", "errors", "fail", "failed", "failure"],
    "failure": ["error", "fail", "failed", "failure"],
    "5xx": ["error", "status"],
    "4xx": ["error", "status"],
    "requests": ["requests", "request", "http", "rpc", "api"],
    "rate": ["total", "count", "rate", "requests"],
    "throughput": ["total", "count", "requests"],
    "qps": ["requests", "total", "count"],
    "cpu": ["cpu", "process_cpu"],
    "memory": ["memory", "mem", "heap", "rss", "bytes"],
    "mem": ["memory", "mem", "heap", "bytes"],
    "disk": ["disk", "fs", "filesystem", "io"],
    "network": ["network", "net", "bytes", "packets"],
    "connections": ["connections", "conn", "sockets"],
    "queue": ["queue", "queued", "pending", "backlog"],
    "cache": ["cache", "hit", "miss"],
    "db": ["db", "database", "sql", "pg", "postgres", "mysql", "redis"],
    "database": ["database", "db", "sql"],
    "goroutines": ["goroutines", "threads"],
    "saturation": ["inflight", "in_flight", "queue", "pending"],
    "availability": ["up", "healthy", "ready"],
    "uptime": ["uptime", "up", "start_time"],
}


def _expand_token(tok: str) -> set[str]:
    """Return the token plus any semantic synonyms."""
    variants = {tok}
    variants.update(_SYNONYMS.get(tok, []))
    # Also handle short forms: "mem" → cover "memory", etc.
    for key, expansions in _SYNONYMS.items():
        if tok == key or tok in expansions:
            variants.update(expansions)
    return {v.lower() for v in variants if v}


async def _discover_topic_metrics(role: str, ds_uid: str, topic: str) -> list[str]:
    """Query the datasource for metric names, then score each by how well it
    matches the user's topic (including semantic synonyms).

    Strategy — in order, stop as soon as we have ≥5 candidates:
      1. All topic tokens match (strongest)
      2. At least one "anchor" token (non-synonym-expanded) matches
      3. Any synonym matches (weakest fallback)

    This way "grafana latency" finds metrics with BOTH grafana AND
    duration/seconds/latency — not just anything with "grafana".
    """
    if not ds_uid or not topic:
        return []
    c = client_for(role)
    try:
        raw = await c.get(f"/api/datasources/proxy/uid/{ds_uid}/api/v1/label/__name__/values")
    except Exception:
        return []
    all_names: list[str] = list((raw or {}).get("data") or [])
    if not all_names:
        return []

    # Normalise topic → tokens, drop filler
    filler = {"a", "an", "the", "dashboard", "dashboards", "dash", "panel", "panels", "for", "of", "on"}
    raw_tokens = [
        t.lower()
        for t in topic.replace("-", " ").replace("_", " ").split()
        if t and t.lower() not in filler
    ]
    if not raw_tokens:
        raw_tokens = [topic.lower()]

    expanded_per_token: list[set[str]] = [_expand_token(t) for t in raw_tokens]

    # Strategy 1: every token (or its synonyms) must hit
    strict: list[str] = []
    for name in all_names:
        nlow = name.lower()
        if all(any(v in nlow for v in variants) for variants in expanded_per_token):
            strict.append(name)

    # Strategy 2: if too few, keep strict ∪ "at least 1 raw token matches"
    if len(strict) < 5:
        loose = [n for n in all_names if any(t in n.lower() for t in raw_tokens)]
        # Merge, strict first (highest relevance)
        merged: list[str] = []
        seen: set[str] = set()
        for n in strict + loose:
            if n not in seen:
                seen.add(n)
                merged.append(n)
        candidates = merged
    else:
        candidates = strict

    # Strategy 3: if still nothing, match any synonym
    if not candidates:
        all_synonyms: set[str] = set().union(*expanded_per_token) if expanded_per_token else set()
        candidates = [n for n in all_names if any(s in n.lower() for s in all_synonyms)]

    # Priority: histograms → durations → counters → gauges
    def _priority(n: str) -> int:
        low = n.lower()
        if n.endswith("_bucket"):
            return 0
        if "duration" in low or "latency" in low or "seconds" in low:
            return 1
        if n.endswith("_total") or n.endswith("_count"):
            return 2
        return 3

    candidates.sort(key=_priority)
    return candidates[:50]


@tool()
async def create_smart_dashboard(
    title: str,
    topic: str | None = None,
    tags: list[str] | None = None,
    folder_uid: str | None = None,
    datasource_uid: str | None = None,
    role: str = "editor",
) -> dict:
    """Create a dashboard pre-populated with RED + resource panels for a topic.

    Auto-discovers the Prometheus datasource and builds a 14-panel dashboard
    (rate / errors / duration / resources / saturation) filtered by a label
    regex derived from the topic. All panel construction happens inside
    this MCP server — callers pass only (title, topic).
    """
    ds_uid = datasource_uid or await _default_prometheus_uid(role)
    if not ds_uid:
        return {
            "ok": False,
            "status": "no_datasource",
            "message": "No Prometheus datasource found. Pass datasource_uid explicitly.",
        }
    topic_str = (topic or title).strip().lower()

    # Discover real metrics first so panels never render 'No data' when live
    # metrics exist. Falls back to the RED template when nothing matches.
    discovered = await _discover_topic_metrics(role, ds_uid, topic_str)
    if discovered:
        panels = build_panels_from_metrics(topic_str, ds_uid, discovered)
        panel_kind = f"{len(panels)} panels from {len(discovered)} live metrics"
    else:
        panels = build_red_panels(topic_str, ds_uid)
        panel_kind = f"{len(panels)} RED template panels (no matching metrics found yet)"
    all_tags = sorted({*(tags or []), topic_str.replace(" ", "-"), "o11ybot", "auto-generated"})

    body: dict[str, Any] = {
        "dashboard": {
            "uid": None,
            "title": title,
            "tags": all_tags,
            "timezone": "browser",
            "schemaVersion": 38,
            "version": 0,
            "refresh": "30s",
            "description": f"Auto-generated RED + resource dashboard for {topic_str}.",
            "panels": panels,
            "templating": {"list": []},
            "time": {"from": "now-1h", "to": "now"},
        },
        "overwrite": False,
        "message": f"Created via O11yBot (smart template for {topic_str})",
    }
    if folder_uid:
        body["folderUid"] = folder_uid

    c = client_for(role)
    raw = await c.post("/api/dashboards/db", body)
    return {
        "ok": True,
        "uid": (raw or {}).get("uid", ""),
        "url": (raw or {}).get("url", ""),
        "version": (raw or {}).get("version", 0),
        "status": (raw or {}).get("status", "success"),
        "message": (
            f"Smart dashboard '{title}' created with {panel_kind} "
            f"for topic '{topic_str}'"
        ),
    }
