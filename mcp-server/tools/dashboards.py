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
        followup_hint = ""
    else:
        panels = build_red_panels(topic_str, ds_uid)
        panel_kind = f"{len(panels)} RED template panels (no matching metrics found yet)"
        followup_hint = (
            "\n\nℹ️ No metrics matching '" + topic_str + "' were found in the "
            "selected datasource, so I used RED templates. Say "
            "\"fix this dashboard\" and I'll rewrite the queries to use "
            "metrics that actually exist."
        )
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
            f"for topic '{topic_str}'" + followup_hint
        ),
    }


# ══════════════════════════════════════════════════════════════════════
# Diagnose + fix — used by the follow-up intent ("no data, fix it")
# ══════════════════════════════════════════════════════════════════════

def _panel_query_info(panel: dict) -> list[tuple[int, str, str]]:
    """Extract (refId, expr, ds_uid) triples from a panel's targets."""
    out: list[tuple[int, str, str]] = []
    for t in panel.get("targets", []) or []:
        expr = (t.get("expr") or "").strip()
        ds = (t.get("datasource") or {})
        ds_uid = ds.get("uid") if isinstance(ds, dict) else ""
        if expr:
            out.append((t.get("refId", "A"), expr, ds_uid or ""))
    return out


async def _probe_query(role: str, ds_uid: str, expr: str) -> dict:
    """Run an instant query against the datasource. Returns a terse
    {ok, series, reason} record — never raises.

    A panel is considered *broken* when ``has_data`` is false, which covers
    both the "Prometheus errored" case (e.g. Mimir ring unhealthy,
    parse error) and the "query parsed but 0 series" case.
    """
    if not ds_uid or not expr:
        return {"ok": False, "has_data": False, "series": 0, "reason": "missing datasource or query"}
    c = client_for(role)
    try:
        raw = await c.get(
            f"/api/datasources/proxy/uid/{ds_uid}/api/v1/query",
            params={"query": expr},
        )
    except Exception as e:
        return {"ok": False, "has_data": False, "series": 0, "reason": f"query failed: {e}"}
    status = (raw or {}).get("status", "")
    if status == "error":
        return {
            "ok": False, "has_data": False, "series": 0,
            "reason": f"datasource error: {(raw or {}).get('error','unknown')[:200]}",
        }
    data = (raw or {}).get("data") or {}
    result = data.get("result") or []
    return {
        "ok": True, "has_data": bool(result), "series": len(result),
        "reason": "" if result else "no series returned",
    }


@tool()
async def diagnose_dashboard(uid: str, role: str = "viewer") -> dict:
    """Probe every panel's query; report which panels have no data and why.

    Read-only. Use before `fix_dashboard_queries` to understand the
    blast radius, or standalone to audit a dashboard.
    """
    detail = await get_dashboard(uid=uid, role=role)
    c = client_for(role)
    # get full panels (not slim) so we can read targets
    raw = await c.get(f"/api/dashboards/uid/{uid}")
    panels = ((raw or {}).get("dashboard", {}) or {}).get("panels", []) or []

    no_data: list[dict] = []
    has_data: list[dict] = []
    for p in panels:
        if p.get("type") == "row":
            continue
        qs = _panel_query_info(p)
        if not qs:
            continue
        pid = p.get("id")
        title = p.get("title", "") or f"panel {pid}"
        worst = None
        for refid, expr, ds_uid in qs:
            probe = await _probe_query(role, ds_uid, expr)
            if not probe.get("has_data"):
                worst = {
                    "id": pid, "title": title, "refId": refid, "expr": expr,
                    "ds_uid": ds_uid, "reason": probe.get("reason", "no data"),
                }
                break
        if worst:
            no_data.append(worst)
        else:
            has_data.append({"id": pid, "title": title})

    return {
        "ok": True,
        "uid": uid,
        "title": detail.get("title", ""),
        "url": detail.get("url", ""),
        "panels_total": len(has_data) + len(no_data),
        "panels_with_data": len(has_data),
        "panels_no_data": len(no_data),
        "no_data": no_data[:20],
        "message": (
            f"Diagnosed '{detail.get('title','')}': {len(has_data)}/"
            f"{len(has_data)+len(no_data)} panels have data; "
            f"{len(no_data)} empty."
        ),
    }


def _pick_replacement_metric(
    expr: str, available: list[str]
) -> str | None:
    """Best-effort mapping from a broken query to a real metric name.

    Strategy: extract a plausible metric name from the expression, then
    find a metric in `available` that shares a meaningful suffix or token.
    """
    import re as _re
    # Grab the first identifier that looks like a metric (not a function).
    m = _re.search(r"([a-zA-Z_:][a-zA-Z0-9_:]{2,})\s*(?:\{|\[|$|\))", expr)
    if not m:
        return None
    broken = m.group(1).lower()
    tokens = [t for t in _re.split(r"[_:]+", broken) if len(t) > 2]

    # Prefer exact suffix match on _total / _bucket / _seconds / _count
    for suffix in ("_bucket", "_total", "_count", "_sum", "_seconds", "_bytes"):
        if broken.endswith(suffix):
            same_suffix = [a for a in available if a.endswith(suffix)]
            if same_suffix and tokens:
                # Score by token overlap
                scored = sorted(
                    same_suffix,
                    key=lambda a: sum(1 for t in tokens if t in a.lower()),
                    reverse=True,
                )
                if scored and any(t in scored[0].lower() for t in tokens):
                    return scored[0]
                return same_suffix[0]

    # Token-overlap fallback across everything
    if tokens:
        scored = sorted(
            available,
            key=lambda a: sum(1 for t in tokens if t in a.lower()),
            reverse=True,
        )
        if scored and any(t in scored[0].lower() for t in tokens):
            return scored[0]
    return None


def _rewrite_expr(expr: str, replacement: str) -> str:
    """Substitute the outermost metric reference in an expr with `replacement`.

    Preserves label selectors and wrappers (sum(rate(<>)[5m]) etc.).
    """
    import re as _re
    return _re.sub(
        r"([a-zA-Z_:][a-zA-Z0-9_:]{2,})(\s*[\{\[\)\s])",
        replacement + r"\2",
        expr,
        count=1,
    )


@tool()
async def fix_dashboard_queries(uid: str, role: str = "editor") -> dict:
    """Diagnose + rewrite any no-data panels with real metric names from
    the dashboard's Prometheus datasource. Edits the dashboard in place.
    """
    c = client_for(role)
    current = await c.get(f"/api/dashboards/uid/{uid}")
    dash = ((current or {}).get("dashboard") or {}).copy()
    panels = list(dash.get("panels", []) or [])
    if not panels:
        return {"ok": False, "uid": uid, "message": "Dashboard has no panels."}

    # Probe every target. Collect the set of datasource UIDs we'll need to
    # pull `__name__` lists from.
    ds_uids: set[str] = set()
    broken: list[tuple[int, int, int, str, str]] = []  # (panel_idx, target_idx, pid, expr, ds_uid)
    for pi, p in enumerate(panels):
        if p.get("type") == "row":
            continue
        for ti, t in enumerate(p.get("targets", []) or []):
            expr = (t.get("expr") or "").strip()
            ds_uid = ((t.get("datasource") or {}).get("uid") or "") if isinstance(t.get("datasource"), dict) else ""
            if not expr or not ds_uid:
                continue
            ds_uids.add(ds_uid)
            probe = await _probe_query(role, ds_uid, expr)
            if not probe.get("has_data"):
                broken.append((pi, ti, p.get("id", pi), expr, ds_uid))

    if not broken:
        return {
            "ok": True, "uid": uid, "fixed": 0,
            "message": "All panels already return data — nothing to fix.",
        }

    # Pull available metric names per datasource (once)
    metrics_by_ds: dict[str, list[str]] = {}
    ds_errors: dict[str, str] = {}
    for ds in ds_uids:
        try:
            raw = await c.get(f"/api/datasources/proxy/uid/{ds}/api/v1/label/__name__/values")
            status = (raw or {}).get("status", "")
            if status == "error":
                ds_errors[ds] = (raw or {}).get("error", "unknown error")[:200]
                metrics_by_ds[ds] = []
            else:
                metrics_by_ds[ds] = list((raw or {}).get("data") or [])
                if not metrics_by_ds[ds]:
                    ds_errors[ds] = "datasource has 0 metrics"
        except Exception as e:
            ds_errors[ds] = str(e)[:200]
            metrics_by_ds[ds] = []

    # If every broken datasource is itself unhealthy, look for a *sibling*
    # Prometheus datasource that does have metrics so we can recommend a swap.
    sibling_ds: dict[str, str] = {}  # broken_uid → healthy sibling uid
    if ds_errors:
        try:
            all_ds = await c.get("/api/datasources") or []
        except Exception:
            all_ds = []
        prom_candidates = [d for d in (all_ds or []) if d.get("type") == "prometheus"]
        for broken_uid in list(ds_errors.keys()):
            for cand in prom_candidates:
                cand_uid = cand.get("uid")
                if not cand_uid or cand_uid == broken_uid:
                    continue
                try:
                    probe = await c.get(f"/api/datasources/proxy/uid/{cand_uid}/api/v1/label/__name__/values")
                    names = (probe or {}).get("data") or []
                    if names:
                        sibling_ds[broken_uid] = cand_uid
                        metrics_by_ds.setdefault(cand_uid, list(names))
                        break
                except Exception:
                    continue

    # Rewrite — prefer the broken datasource itself; fall back to a healthy
    # sibling when the original datasource is error-state.
    fixed_records: list[dict] = []
    unfixable: list[dict] = []
    for pi, ti, pid, expr, ds_uid in broken:
        target_ds = ds_uid
        # If ds is broken but a healthy sibling exists, use its metric list
        # and eventually retarget the panel to it.
        swap_to: str | None = None
        if ds_uid in ds_errors and ds_uid in sibling_ds:
            swap_to = sibling_ds[ds_uid]
            target_ds = swap_to

        replacement = _pick_replacement_metric(expr, metrics_by_ds.get(target_ds, []))
        if not replacement:
            unfixable.append({
                "panel_id": pid, "expr": expr,
                "reason": ds_errors.get(ds_uid) or "no comparable metric available",
            })
            continue
        new_expr = _rewrite_expr(expr, replacement)
        if new_expr == expr:
            unfixable.append({"panel_id": pid, "expr": expr, "reason": "rewrite produced no change"})
            continue
        verify = await _probe_query(role, target_ds, new_expr)
        if not verify.get("has_data"):
            unfixable.append({
                "panel_id": pid, "expr": expr, "candidate": new_expr,
                "reason": f"candidate returned no data ({verify.get('reason','')})",
            })
            continue
        panels[pi]["targets"][ti]["expr"] = new_expr
        if swap_to:
            panels[pi]["targets"][ti]["datasource"] = {"type": "prometheus", "uid": swap_to}
            if isinstance(panels[pi].get("datasource"), dict):
                panels[pi]["datasource"] = {"type": "prometheus", "uid": swap_to}
        fixed_records.append({
            "panel_id": pid, "before": expr, "after": new_expr,
            "series": verify["series"],
            "datasource_swapped": bool(swap_to),
        })

    if not fixed_records:
        ds_diag = "; ".join(f"{k}: {v}" for k, v in list(ds_errors.items())[:2]) if ds_errors else ""
        return {
            "ok": True, "uid": uid, "fixed": 0,
            "message": (
                f"Found {len(broken)} no-data panels. "
                + (
                    f"Couldn't fix them because the datasource is unhealthy — {ds_diag}. "
                    "Try once the datasource is healthy, or tell me which "
                    "datasource to retarget to."
                    if ds_errors else
                    "No matching replacement metrics exist in the datasource."
                )
            ).strip(),
            "datasource_errors": ds_errors,
            "unfixable": unfixable[:10],
        }

    # Save
    dash["panels"] = panels
    body: dict[str, Any] = {
        "dashboard": dash,
        "overwrite": True,
        "message": f"fixed {len(fixed_records)} no-data panels via O11yBot",
    }
    meta = (current or {}).get("meta", {}) or {}
    if meta.get("folderUid"):
        body["folderUid"] = meta["folderUid"]
    raw = await c.post("/api/dashboards/db", body)
    return {
        "ok": True,
        "uid": (raw or {}).get("uid", uid),
        "url": (raw or {}).get("url", meta.get("url", "")),
        "version": (raw or {}).get("version", 0),
        "fixed": len(fixed_records),
        "unfixable_count": len(unfixable),
        "changes": fixed_records[:10],
        "unfixable": unfixable[:10],
        "message": (
            f"Rewrote {len(fixed_records)} no-data panels with real metrics "
            f"from the datasource. "
            + (f"{len(unfixable)} panels still lack matching metrics." if unfixable else "")
        ).strip(),
    }
