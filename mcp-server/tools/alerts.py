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
