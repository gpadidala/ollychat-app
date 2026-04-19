"""Enterprise workflow tools — compound operations that chain multiple
Grafana API calls into a single MCP tool.

These are the tools that make O11yBot feel like an assistant, not a
dumb dispatcher: they fetch related context, correlate signals, and
return a structured summary the orchestrator can render directly.
"""
from __future__ import annotations

from grafana_client import client_for
from registry import tool

from ._panel_templates import build_panels_from_metrics


@tool()
async def investigate_alert(uid: str, role: str = "viewer") -> dict:
    """Fetch an alert rule + related dashboards + recent firing instances and
    return a single investigation payload for the LLM to narrate over.

    Output:
      { rule: {...}, firing: [...], dashboards: [{uid, title, url}...],
        related_queries: [...], suggested_next_steps: [...] }
    """
    c = client_for(role)
    rule = await c.get(f"/api/v1/provisioning/alert-rules/{uid}") or {}

    # Pull any active firing instances matching this rule
    alerts_raw = await c.get("/api/prometheus/grafana/api/v1/alerts") or {}
    all_alerts = ((alerts_raw.get("data") or {}).get("alerts")) or []
    firing = [a for a in all_alerts
              if (a.get("labels") or {}).get("__alert_rule_uid__") == uid][:10]

    # Find dashboards tagged with the rule's labels
    labels = rule.get("labels") or {}
    service = labels.get("service") or labels.get("app")
    dashboards: list[dict] = []
    if service:
        search = await c.get("/api/search", params={"query": service, "type": "dash-db", "limit": 8}) or []
        dashboards = [{"uid": d.get("uid", ""), "title": d.get("title", ""), "url": d.get("url", "")}
                      for d in search]

    # Extract the primary PromQL expression for context
    expr = ""
    for d in (rule.get("data") or []):
        if d.get("refId") == "A":
            expr = ((d.get("model") or {}).get("expr")) or ""
            break

    next_steps = [
        f"Check firing instances: {len(firing)} currently active",
        f"Open dashboards: {len(dashboards)} related",
    ]
    if service:
        next_steps.append(f"Query logs: {{service=\"{service}\"}} |= \"ERROR\"")
        next_steps.append(f"Query traces: {{ resource.service.name = \"{service}\" && duration > 1s }}")

    return {
        "rule": {
            "uid": rule.get("uid", uid),
            "title": rule.get("title", ""),
            "group": rule.get("ruleGroup", ""),
            "folder": rule.get("folderUID", ""),
            "for": rule.get("for", ""),
            "condition": rule.get("condition", ""),
            "expr": expr,
            "labels": labels,
            "annotations": rule.get("annotations") or {},
        },
        "firing_count": len(firing),
        "firing": firing,
        "dashboards": dashboards,
        "suggested_next_steps": next_steps,
    }


async def _find_ds_uid(role: str, type_filter: str) -> str:
    c = client_for(role)
    for d in (await c.get("/api/datasources") or []):
        if (d.get("type") or "").lower() == type_filter.lower():
            return d.get("uid") or ""
    return ""


@tool()
async def correlate_signals(
    service: str,
    time_from: str = "now-30m",
    time_to: str = "now",
    role: str = "viewer",
) -> dict:
    """Pull metrics + logs + traces for one service in a single call.

    - Metrics: top 5 PromQL time series matching service=~".*<service>.*"
    - Logs:    last 50 error lines from Loki, if a Loki datasource exists
    - Traces:  top 10 slow traces from Tempo, if a Tempo datasource exists

    Intended to seed an LLM investigation prompt with real data.
    """
    c = client_for(role)
    prom_uid = await _find_ds_uid(role, "prometheus")
    loki_uid = await _find_ds_uid(role, "loki")
    tempo_uid = await _find_ds_uid(role, "tempo")

    result: dict = {"service": service, "time_from": time_from, "time_to": time_to}

    # Metrics
    if prom_uid:
        body = {
            "queries": [{
                "refId": "A",
                "datasource": {"uid": prom_uid, "type": "prometheus"},
                "expr": f'topk(5, sum by (__name__) ({{__name__=~".*{service}.*"}}))',
                "maxDataPoints": 100,
            }],
            "from": time_from, "to": time_to,
        }
        try:
            m = await c.post("/api/ds/query", body) or {}
            result["metrics_frames"] = len((((m.get("results") or {}).get("A") or {}).get("frames")) or [])
        except Exception as e:
            result["metrics_error"] = str(e)

    # Logs — last 50 error lines
    if loki_uid:
        body = {
            "queries": [{
                "refId": "A",
                "datasource": {"uid": loki_uid, "type": "loki"},
                "expr": f'{{service="{service}"}} |~ "(?i)error|fail|panic|timeout"',
                "queryType": "range", "maxLines": 50,
            }],
            "from": time_from, "to": time_to,
        }
        try:
            l = await c.post("/api/ds/query", body) or {}
            frames = (((l.get("results") or {}).get("A") or {}).get("frames")) or []
            log_lines = 0
            for f in frames:
                values = (f.get("data") or {}).get("values") or []
                if values:
                    log_lines += len(values[0])
            result["log_error_lines"] = log_lines
        except Exception as e:
            result["logs_error"] = str(e)

    # Traces — top 10 slow
    if tempo_uid:
        body = {
            "queries": [{
                "refId": "A",
                "datasource": {"uid": tempo_uid, "type": "tempo"},
                "query": f'{{ resource.service.name = "{service}" && duration > 500ms }}',
                "queryType": "traceql", "limit": 10,
            }],
            "from": time_from, "to": time_to,
        }
        try:
            t = await c.post("/api/ds/query", body) or {}
            frames = (((t.get("results") or {}).get("A") or {}).get("frames")) or []
            trace_count = 0
            for f in frames:
                values = (f.get("data") or {}).get("values") or []
                if values:
                    trace_count += len(values[0])
            result["slow_traces"] = trace_count
        except Exception as e:
            result["traces_error"] = str(e)

    result["summary"] = (
        f"Service {service}: "
        f"{result.get('metrics_frames', 0)} metric frames, "
        f"{result.get('log_error_lines', 0)} error log lines, "
        f"{result.get('slow_traces', 0)} slow traces"
    )
    return result


@tool()
async def create_slo_dashboard(
    service: str,
    sli_query: str | None = None,
    target: float = 99.9,
    window_days: int = 30,
    folder_uid: str | None = None,
    role: str = "editor",
) -> dict:
    """Create a standard SLO dashboard for a service.

    Panels:
      - SLI (last 5m)
      - Error budget consumed (rolling window)
      - Fast-burn alert-ready expression (2h, 14.4× budget rate)
      - Slow-burn alert-ready expression (24h, 1× budget rate)
      - Raw request rate + error rate

    ``sli_query`` is the "good requests / total requests" expression. If
    omitted, a sensible HTTP-5xx availability SLI is synthesised.
    """
    prom_uid = await _find_ds_uid(role, "prometheus")
    if not prom_uid:
        return {"ok": False, "status": "no_datasource",
                "message": "No Prometheus datasource available."}

    if not sli_query:
        sli_query = (
            f'sum(rate(http_requests_total{{service="{service}", status!~"5.."}}[5m])) / '
            f'clamp_min(sum(rate(http_requests_total{{service="{service}"}}[5m])), 0.001)'
        )
    budget = 1 - (target / 100.0)

    def _panel(pid, ptype, title, expr, x, y, w, h, unit="short", legend=""):
        return {
            "id": pid, "type": ptype, "title": title,
            "datasource": {"type": "prometheus", "uid": prom_uid},
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "targets": [{"refId": "A", "expr": expr, "legendFormat": legend,
                         "datasource": {"type": "prometheus", "uid": prom_uid}}],
            "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        }

    panels = [
        {"id": 1, "type": "row", "title": f"SLO — {service}  (target {target}%)",
         "gridPos": {"x": 0, "y": 0, "w": 24, "h": 1}, "collapsed": False, "panels": []},
        _panel(2, "stat", "Current SLI (5m)", sli_query, 0, 1, 6, 4, "percentunit"),
        _panel(3, "stat", f"Error budget consumed ({window_days}d)",
               f'1 - ({sli_query.replace("[5m]", f"[{window_days}d]")})',
               6, 1, 6, 4, "percentunit"),
        _panel(4, "stat", "Fast burn rate (2h)",
               f'(1 - ({sli_query.replace("[5m]", "[2h]")})) / {budget}',
               12, 1, 6, 4, "short"),
        _panel(5, "stat", "Slow burn rate (24h)",
               f'(1 - ({sli_query.replace("[5m]", "[24h]")})) / {budget}',
               18, 1, 6, 4, "short"),
        _panel(6, "timeseries", "SLI over time", sli_query,
               0, 5, 24, 8, "percentunit", "SLI"),
        _panel(7, "timeseries", "Request rate",
               f'sum(rate(http_requests_total{{service="{service}"}}[5m]))',
               0, 13, 12, 8, "reqps", "rps"),
        _panel(8, "timeseries", "Error rate (5xx)",
               f'sum(rate(http_requests_total{{service="{service}", status=~"5.."}}[5m]))',
               12, 13, 12, 8, "reqps", "errors/s"),
    ]

    title = f"SLO — {service}"
    body = {
        "dashboard": {
            "uid": None, "title": title,
            "tags": ["slo", "o11ybot", service, "auto-generated"],
            "schemaVersion": 38, "version": 0, "refresh": "1m",
            "description": f"SLO tracking for {service} · target {target}% over {window_days}d.",
            "panels": panels,
            "time": {"from": f"now-{window_days}d", "to": "now"},
            "templating": {"list": []},
        },
        "overwrite": False,
        "message": f"SLO dashboard for {service} via O11yBot",
    }
    if folder_uid:
        body["folderUid"] = folder_uid
    c = client_for(role)
    raw = await c.post("/api/dashboards/db", body) or {}
    return {
        "ok": True,
        "uid": raw.get("uid", ""),
        "url": raw.get("url", ""),
        "version": raw.get("version", 0),
        "status": raw.get("status", "success"),
        "message": (
            f"SLO dashboard for '{service}' created — target {target}%, {window_days}d window, "
            f"budget {budget:.4f}"
        ),
    }


@tool()
async def dashboard_wizard(
    topic: str = "",
    role: str = "viewer",
) -> dict:
    """Gather everything needed to author a dashboard — datasources, folders,
    and (if ``topic`` is given) matching metric names.

    Used when the user says "create dashboard" without picking a datasource
    or folder, so O11yBot can ask rather than guess.
    """
    c = client_for(role)

    datasources: list[dict] = []
    try:
        for d in (await c.get("/api/datasources") or []):
            datasources.append({
                "uid": d.get("uid", ""),
                "name": d.get("name", ""),
                "type": d.get("type", ""),
                "is_default": d.get("isDefault", False),
            })
    except Exception:
        pass

    folders: list[dict] = []
    try:
        for f in (await c.get("/api/folders") or []):
            folders.append({"uid": f.get("uid", ""), "title": f.get("title", "")})
    except Exception:
        pass

    metric_suggestions: list[str] = []
    if topic:
        prom_uid = ""
        for d in datasources:
            if (d.get("type") or "").lower() == "prometheus":
                prom_uid = d.get("uid") or ""
                break
        if prom_uid:
            try:
                raw = await c.get(
                    f"/api/datasources/proxy/uid/{prom_uid}/api/v1/label/__name__/values"
                )
                names = list((raw or {}).get("data") or [])
                toks = [
                    t for t in topic.lower().replace("-", " ").replace("_", " ").split()
                    if t and t not in {"dashboard", "dashboards", "a", "an", "the"}
                ]
                matched = [n for n in names if any(t in n.lower() for t in toks)]
                metric_suggestions = matched[:15]
            except Exception:
                pass

    return {
        "topic": topic,
        "datasources": datasources,
        "folders": folders,
        "metric_suggestions": metric_suggestions,
        "next_step_template": (
            "create dashboard \"<title>\" for \"<topic>\" on datasource <uid> in folder <uid>"
        ),
        "auto_hint": "Or say: `create <topic> dashboard now` to auto-pick defaults.",
    }


@tool()
async def alert_wizard(
    topic: str = "",
    role: str = "viewer",
) -> dict:
    """Gather everything needed to author an alert rule — datasources,
    folders, and (if ``topic`` is given) metric names + example PromQL.

    Used by the orchestrator when a user says "create alert" without
    enough info to call ``create_alert_rule`` directly. The response
    renders as an interactive form the user can fill in.
    """
    c = client_for(role)

    # Datasources (prefer Prometheus-shaped for alert targets)
    datasources: list[dict] = []
    try:
        for d in (await c.get("/api/datasources") or []):
            datasources.append({
                "uid": d.get("uid", ""),
                "name": d.get("name", ""),
                "type": d.get("type", ""),
                "is_default": d.get("isDefault", False),
            })
    except Exception:
        pass

    # Folders
    folders: list[dict] = []
    try:
        for f in (await c.get("/api/folders") or []):
            folders.append({"uid": f.get("uid", ""), "title": f.get("title", "")})
    except Exception:
        pass

    # If a topic is given, suggest matching metric names
    metric_suggestions: list[str] = []
    if topic:
        prom_uid = ""
        for d in datasources:
            if (d.get("type") or "").lower() == "prometheus":
                prom_uid = d.get("uid") or ""
                break
        if prom_uid:
            try:
                raw = await c.get(
                    f"/api/datasources/proxy/uid/{prom_uid}/api/v1/label/__name__/values"
                )
                names = list((raw or {}).get("data") or [])
                tl = topic.lower()
                toks = [t for t in tl.replace("-", " ").replace("_", " ").split() if t]
                matched = [
                    n for n in names
                    if any(t in n.lower() for t in toks)
                    and (n.endswith("_total") or n.endswith("_count") or n.endswith("_bucket") or n.endswith("_seconds"))
                ]
                metric_suggestions = matched[:8]
            except Exception:
                pass

    # Example expressions built from suggestions
    examples: list[str] = []
    for n in metric_suggestions[:4]:
        if n.endswith("_bucket"):
            base = n[: -len("_bucket")]
            examples.append(
                f"1000 * histogram_quantile(0.95, sum by (le) (rate({n}[5m]))) > 500"
            )
            examples.append(f"# p95 of {base} exceeding 500 ms")
        elif n.endswith("_total"):
            examples.append(f"sum(rate({n}[5m])) > 1")
            examples.append(f"# rate of {n} exceeds 1/s")

    return {
        "topic": topic,
        "datasources": datasources,
        "folders": folders,
        "metric_suggestions": metric_suggestions,
        "example_expressions": examples,
        "next_step_template": (
            "create alert \"<title>\" on datasource <uid> for \"<promql>\" "
            "threshold <number> for 5m in folder <uid>"
        ),
    }


@tool()
async def find_dashboards_using_metric(
    metric_name: str,
    limit: int = 20,
    role: str = "viewer",
) -> list[dict]:
    """Find every dashboard whose panel JSON references a given metric name.

    Useful for impact analysis before renaming/removing metrics.
    """
    c = client_for(role)
    all_dash = await c.get("/api/search", params={"type": "dash-db", "limit": 500}) or []
    hits: list[dict] = []
    for d in all_dash:
        uid = d.get("uid", "")
        if not uid:
            continue
        try:
            detail = await c.get(f"/api/dashboards/uid/{uid}") or {}
            panels = (detail.get("dashboard") or {}).get("panels") or []
            matched_panels: list[str] = []
            for p in panels:
                for tg in (p.get("targets") or []):
                    expr = str(tg.get("expr") or "")
                    if metric_name in expr:
                        matched_panels.append(p.get("title") or f"panel-{p.get('id', 0)}")
                        break
            if matched_panels:
                hits.append({
                    "uid": uid,
                    "title": d.get("title", ""),
                    "url": d.get("url", ""),
                    "matched_panels": matched_panels[:5],
                    "match_count": len(matched_panels),
                })
                if len(hits) >= limit:
                    break
        except Exception:
            continue
    return hits
