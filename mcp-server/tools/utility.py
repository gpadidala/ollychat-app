"""Utility tools — health + server info."""
from __future__ import annotations

from config import get_settings
from grafana_client import client_for
from registry import tool, tool_count


@tool()
async def health_check(role: str = "viewer") -> dict:
    """Check Grafana health — returns version, database status, enterprise flag."""
    c = client_for(role)
    raw = await c.get("/api/health") or {}
    return {
        "database": raw.get("database", ""),
        "version": raw.get("version", ""),
        "commit": raw.get("commit", ""),
        "enterprise": bool(raw.get("enterpriseEdition") or raw.get("enterprise")),
    }


@tool()
async def get_server_info(role: str = "viewer") -> dict:
    """Return info about the O11yBot MCP server itself (not Grafana)."""
    s = get_settings()
    return {
        "server": "ollychat-mcp",
        "version": "1.0.0",
        "grafana_url": s.grafana_url,
        "tool_count": tool_count(),
        "transport": "rest",
        "rbac": "role-based tokens (viewer / editor / admin)",
    }
