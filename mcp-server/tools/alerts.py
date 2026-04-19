"""Alert rule + instance + silence tools."""
from __future__ import annotations

from typing import Any

from grafana_client import client_for
from registry import tool


def _flatten_rules(raw: Any) -> list[dict]:
    """Normalise /api/v1/provisioning/alert-rules OR /api/ruler/.../rules output."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # /api/ruler shape: {ns: {groups: [{rules: [...]}, ...]}}
        out: list[dict] = []
        for ns, groups in raw.items():
            if not isinstance(groups, list):
                continue
            for g in groups:
                for rule in g.get("rules", []):
                    out.append({
                        "uid": (rule.get("grafana_alert") or {}).get("uid") or rule.get("uid", ""),
                        "title": (rule.get("grafana_alert") or {}).get("title") or rule.get("alert", ""),
                        "group": g.get("name", ""),
                        "namespace": ns,
                        "state": (rule.get("grafana_alert") or {}).get("state", ""),
                        "condition": (rule.get("grafana_alert") or {}).get("condition", ""),
                        "annotations": rule.get("annotations") or {},
                        "labels": rule.get("labels") or {},
                    })
        return out
    return []


@tool()
async def list_alert_rules(role: str = "viewer") -> list[dict]:
    """List all unified alerting rules configured in Grafana."""
    c = client_for(role)
    raw = await c.get("/api/v1/provisioning/alert-rules")
    if isinstance(raw, list):
        return [{
            "uid": r.get("uid", ""),
            "title": r.get("title", ""),
            "group": r.get("ruleGroup", ""),
            "folder_uid": r.get("folderUID", ""),
            "state": r.get("execErrState", ""),
            "condition": r.get("condition", ""),
            "no_data_state": r.get("noDataState", ""),
            "exec_err_state": r.get("execErrState", ""),
            "annotations": r.get("annotations") or {},
            "labels": r.get("labels") or {},
        } for r in raw]
    return []


@tool()
async def get_alert_rule(uid: str, role: str = "viewer") -> dict:
    """Get a single alert rule by UID with its full configuration."""
    c = client_for(role)
    r = await c.get(f"/api/v1/provisioning/alert-rules/{uid}")
    r = r or {}
    return {
        "uid": r.get("uid", uid),
        "title": r.get("title", ""),
        "group": r.get("ruleGroup", ""),
        "folder_uid": r.get("folderUID", ""),
        "state": r.get("execErrState", ""),
        "condition": r.get("condition", ""),
        "no_data_state": r.get("noDataState", ""),
        "exec_err_state": r.get("execErrState", ""),
        "annotations": r.get("annotations") or {},
        "labels": r.get("labels") or {},
        "interval": r.get("interval", ""),
    }


@tool()
async def list_alert_instances(role: str = "viewer") -> list[dict]:
    """List currently active / firing alert instances."""
    c = client_for(role)
    raw = await c.get("/api/prometheus/grafana/api/v1/alerts")
    alerts = ((raw or {}).get("data") or {}).get("alerts") or []
    out: list[dict] = []
    for a in alerts:
        labels = a.get("labels") or {}
        out.append({
            "title": labels.get("alertname") or "(unnamed)",
            "state": a.get("state", ""),
            "activeAt": a.get("activeAt", ""),
            "labels": labels,
            "annotations": a.get("annotations") or {},
            "value": a.get("value", ""),
        })
    return out


@tool()
async def silence_alert(
    alert_uid: str,
    duration_minutes: int = 60,
    comment: str = "Silenced via O11yBot",
    role: str = "editor",
) -> dict:
    """Silence an alert by UID for the specified duration in minutes."""
    import datetime as dt
    c = client_for(role)
    now = dt.datetime.now(dt.timezone.utc)
    body = {
        "comment": comment,
        "createdBy": "o11ybot",
        "startsAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endsAt": (now + dt.timedelta(minutes=duration_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matchers": [{"name": "__alert_rule_uid__", "value": alert_uid, "isEqual": True, "isRegex": False}],
    }
    raw = await c.post("/api/alertmanager/grafana/api/v2/silences", body)
    return {
        "ok": True,
        "silence_id": (raw or {}).get("silenceID") or (raw or {}).get("id", ""),
        "alert_uid": alert_uid,
        "duration_minutes": duration_minutes,
        "message": f"Silenced alert {alert_uid} for {duration_minutes}m",
    }


@tool()
async def list_silences(role: str = "viewer") -> list[dict]:
    """List all active alert silences."""
    c = client_for(role)
    raw = await c.get("/api/alertmanager/grafana/api/v2/silences") or []
    out: list[dict] = []
    for s in raw:
        out.append({
            "id": s.get("id", ""),
            "status": (s.get("status") or {}).get("state", ""),
            "comment": s.get("comment", ""),
            "createdBy": s.get("createdBy", ""),
            "startsAt": s.get("startsAt", ""),
            "endsAt": s.get("endsAt", ""),
            "matchers": s.get("matchers", []) or [],
        })
    return out


@tool()
async def delete_silence(silence_id: str, role: str = "editor") -> dict:
    """Delete (unmute) an active silence by its ID."""
    c = client_for(role)
    await c.delete(f"/api/alertmanager/grafana/api/v2/silence/{silence_id}")
    return {"ok": True, "silence_id": silence_id, "status": "deleted",
            "message": f"Silence {silence_id} removed"}


@tool()
async def create_alert_rule(
    title: str,
    folder_uid: str,
    datasource_uid: str,
    expr: str,
    condition_threshold: float = 0.0,
    for_duration: str = "5m",
    rule_group: str = "o11ybot",
    rule_group_interval: str = "1m",
    summary: str = "",
    description: str = "",
    severity: str = "warning",
    no_data_state: str = "NoData",
    exec_err_state: str = "Error",
    role: str = "editor",
) -> dict:
    """Create a Grafana-managed alert rule.

    The rule evaluates ``expr`` against ``datasource_uid`` (typically Prometheus),
    then reduces the result and fires when the last value exceeds
    ``condition_threshold`` for ``for_duration``. Folder + rule group must exist.
    """
    c = client_for(role)
    body = {
        "title": title,
        "condition": "C",
        "data": [
            {
                "refId": "A",
                "datasourceUid": datasource_uid,
                "queryType": "",
                "model": {
                    "expr": expr,
                    "intervalMs": 1000,
                    "maxDataPoints": 43200,
                    "refId": "A",
                },
                "relativeTimeRange": {"from": 600, "to": 0},
            },
            {
                "refId": "B",
                "datasourceUid": "__expr__",
                "queryType": "",
                "model": {
                    "type": "reduce",
                    "expression": "A",
                    "reducer": "last",
                    "refId": "B",
                },
                "relativeTimeRange": {"from": 0, "to": 0},
            },
            {
                "refId": "C",
                "datasourceUid": "__expr__",
                "queryType": "",
                "model": {
                    "type": "threshold",
                    "expression": "B",
                    "conditions": [{
                        "evaluator": {"type": "gt", "params": [condition_threshold]},
                        "operator": {"type": "and"},
                        "query": {"params": ["B"]},
                        "reducer": {"type": "last"},
                        "type": "query",
                    }],
                    "refId": "C",
                },
                "relativeTimeRange": {"from": 0, "to": 0},
            },
        ],
        "folderUID": folder_uid,
        "ruleGroup": rule_group,
        "for": for_duration,
        "noDataState": no_data_state,
        "execErrState": exec_err_state,
        "annotations": {"summary": summary or title, "description": description or title},
        "labels": {"severity": severity},
    }
    raw = await c.post("/api/v1/provisioning/alert-rules", body)
    return {
        "ok": True,
        "uid": (raw or {}).get("uid", ""),
        "title": title,
        "group": rule_group,
        "folder_uid": folder_uid,
        "status": "created",
        "message": f"Alert rule '{title}' created in group {rule_group}",
    }


@tool()
async def update_alert_rule(
    uid: str,
    title: str | None = None,
    expr: str | None = None,
    condition_threshold: float | None = None,
    for_duration: str | None = None,
    severity: str | None = None,
    role: str = "editor",
) -> dict:
    """Patch selected fields on an existing alert rule (only provided ones change)."""
    c = client_for(role)
    current = await c.get(f"/api/v1/provisioning/alert-rules/{uid}") or {}
    if title is not None:
        current["title"] = title
    if for_duration is not None:
        current["for"] = for_duration
    if severity is not None:
        labels = current.get("labels") or {}
        labels["severity"] = severity
        current["labels"] = labels
    data = current.get("data") or []
    if expr is not None and data:
        for d in data:
            if d.get("refId") == "A":
                model = d.get("model") or {}
                model["expr"] = expr
                d["model"] = model
                break
    if condition_threshold is not None and data:
        for d in data:
            if d.get("refId") == "C":
                model = d.get("model") or {}
                conds = model.get("conditions") or []
                if conds:
                    conds[0]["evaluator"] = {"type": "gt", "params": [condition_threshold]}
                    model["conditions"] = conds
                    d["model"] = model
                break
    raw = await c.put(f"/api/v1/provisioning/alert-rules/{uid}", current)
    return {
        "ok": True,
        "uid": uid,
        "title": current.get("title", ""),
        "status": "updated",
        "message": f"Alert rule {uid} updated",
    }


@tool()
async def delete_alert_rule(uid: str, role: str = "admin") -> dict:
    """Delete an alert rule by UID."""
    c = client_for(role)
    await c.delete(f"/api/v1/provisioning/alert-rules/{uid}")
    return {"ok": True, "uid": uid, "status": "deleted",
            "message": f"Alert rule {uid} deleted"}


@tool()
async def list_contact_points(role: str = "viewer") -> list[dict]:
    """List all alert notification contact points."""
    c = client_for(role)
    raw = await c.get("/api/v1/provisioning/contact-points") or []
    return [{
        "uid": cp.get("uid", ""),
        "name": cp.get("name", ""),
        "type": cp.get("type", ""),
        "disable_resolve_message": cp.get("disableResolveMessage", False),
    } for cp in raw]


@tool()
async def list_notification_policies(role: str = "viewer") -> dict:
    """Return the notification policy tree (routing rules for alerts)."""
    c = client_for(role)
    raw = await c.get("/api/v1/provisioning/policies") or {}
    return {
        "receiver": raw.get("receiver", ""),
        "group_by": raw.get("group_by") or [],
        "group_wait": raw.get("group_wait", ""),
        "group_interval": raw.get("group_interval", ""),
        "repeat_interval": raw.get("repeat_interval", ""),
        "routes": raw.get("routes") or [],
    }


@tool()
async def list_mute_timings(role: str = "viewer") -> list[dict]:
    """List all mute timings used by the alerting notification router."""
    c = client_for(role)
    raw = await c.get("/api/v1/provisioning/mute-timings") or []
    return [{
        "name": m.get("name", ""),
        "time_intervals": m.get("time_intervals") or [],
    } for m in raw]
