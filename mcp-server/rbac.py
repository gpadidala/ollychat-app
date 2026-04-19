"""Role-Based Access Control for O11yBot MCP tools.

Roles (ascending privilege): viewer < editor < admin.
Every registered tool has a minimum role; `enforce_role` raises PermissionError
on violation so FastAPI can return a clean 403.
"""
from __future__ import annotations

ROLE_HIERARCHY = ["viewer", "editor", "admin"]

TOOL_MINIMUM_ROLE: dict[str, str] = {
    # Dashboards (read)
    "list_dashboards": "viewer",
    "search_dashboards": "viewer",
    "get_dashboard": "viewer",
    "get_dashboard_panels": "viewer",
    # Dashboards (write)
    "create_dashboard": "editor",
    "create_smart_dashboard": "editor",
    "update_dashboard": "editor",
    "delete_dashboard": "admin",
    # Alerts
    "list_alert_rules": "viewer",
    "get_alert_rule": "viewer",
    "list_alert_instances": "viewer",
    "silence_alert": "editor",
    # Datasources
    "list_datasources": "viewer",
    "get_datasource": "viewer",
    "query_datasource": "viewer",
    # Folders
    "list_folders": "viewer",
    "create_folder": "editor",
    # Users / SAs (admin-only)
    "list_users": "admin",
    "list_service_accounts": "admin",
    # Utility
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
