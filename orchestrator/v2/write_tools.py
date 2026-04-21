"""Taxonomy: which MCP tools mutate Grafana state and therefore require approval.

Source: mcp-server/rbac.py — anything with min_role != 'viewer' is a mutation
and goes through the `awaiting_approval` handshake in v2 interactive mode.
"""
from __future__ import annotations

# The tool names that must be gated. Kept as a tight explicit set so that
# adding a new write tool at the MCP layer is a deliberate action, not a
# drift into "the LLM can now silently mutate things".
WRITE_TOOLS: frozenset[str] = frozenset({
    # Dashboards
    "create_dashboard",
    "create_smart_dashboard",
    "update_dashboard",
    "delete_dashboard",
    "fix_dashboard_queries",
    # Alerts
    "create_alert_rule",
    "update_alert_rule",
    "delete_alert_rule",
    "silence_alert",
    "delete_silence",
    # Folders
    "create_folder",
    "update_folder",
    "delete_folder",
    # Annotations
    "create_annotation",
    "delete_annotation",
    # Teams
    "create_team",
    "add_team_member",
    # Workflow (compound) — creates dashboards / silences
    "create_slo_dashboard",
})


def is_write_tool(tool_name: str) -> bool:
    return tool_name in WRITE_TOOLS
