"""Role-Based Access Control for O11yBot MCP tools.

Roles (ascending privilege): viewer < editor < admin.
Every registered tool has a minimum role; `enforce_role` raises PermissionError
on violation so FastAPI can return a clean 403.
"""
from __future__ import annotations

ROLE_HIERARCHY = ["viewer", "editor", "admin"]

TOOL_MINIMUM_ROLE: dict[str, str] = {
    # ── Dashboards ──────────────────────────────────────────
    "list_dashboards": "viewer",
    "search_dashboards": "viewer",
    "get_dashboard": "viewer",
    "get_dashboard_panels": "viewer",
    "create_dashboard": "editor",
    "create_smart_dashboard": "editor",
    "update_dashboard": "editor",
    "delete_dashboard": "admin",
    # ── Alerts ──────────────────────────────────────────────
    "list_alert_rules": "viewer",
    "get_alert_rule": "viewer",
    "list_alert_instances": "viewer",
    "silence_alert": "editor",
    "list_silences": "viewer",
    "delete_silence": "editor",
    "create_alert_rule": "editor",
    "update_alert_rule": "editor",
    "delete_alert_rule": "admin",
    "list_contact_points": "viewer",
    "list_notification_policies": "viewer",
    "list_mute_timings": "viewer",
    # ── Annotations ─────────────────────────────────────────
    "list_annotations": "viewer",
    "create_annotation": "editor",
    "delete_annotation": "editor",
    # ── Datasources ─────────────────────────────────────────
    "list_datasources": "viewer",
    "get_datasource": "viewer",
    "query_datasource": "viewer",
    "list_metric_names": "viewer",
    "list_label_values": "viewer",
    "query_loki": "viewer",
    "query_tempo": "viewer",
    # ── Folders ─────────────────────────────────────────────
    "list_folders": "viewer",
    "get_folder": "viewer",
    "create_folder": "editor",
    "update_folder": "editor",
    "delete_folder": "admin",
    # ── Library panels ──────────────────────────────────────
    "list_library_panels": "viewer",
    "get_library_panel": "viewer",
    # ── Plugins ─────────────────────────────────────────────
    "list_plugins": "viewer",
    "get_plugin": "viewer",
    # ── Teams (admin-only mutations) ────────────────────────
    "list_teams": "viewer",
    "create_team": "admin",
    "list_team_members": "viewer",
    "add_team_member": "admin",
    # ── Users / SAs ─────────────────────────────────────────
    "list_users": "admin",
    "list_service_accounts": "admin",
    # ── Workflows (compound) ────────────────────────────────
    "investigate_alert": "viewer",
    "correlate_signals": "viewer",
    "create_slo_dashboard": "editor",
    "find_dashboards_using_metric": "viewer",
    # ── Utility ─────────────────────────────────────────────
    "health_check": "viewer",
    "get_server_info": "viewer",
}


def normalize_role(raw: str | None) -> str:
    r = (raw or "viewer").lower().strip()
    if r in ("admin", "grafana admin"):
        return "admin"
    if r == "editor":
        return "editor"
    return "viewer"


def enforce(tool_name: str, caller_role: str) -> None:
    required = TOOL_MINIMUM_ROLE.get(tool_name, "viewer")
    if ROLE_HIERARCHY.index(caller_role) < ROLE_HIERARCHY.index(required):
        raise PermissionError(
            f"Tool '{tool_name}' requires role '{required}', caller has '{caller_role}'."
        )
