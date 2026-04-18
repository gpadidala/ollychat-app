"""Intent matcher — detects common observability queries and routes them to MCP tools directly.

This provides reliable tool calling even with small LLMs (qwen2.5:0.5b) that can't handle
function calling natively. Pattern: match user query → call MCP tool → format result.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Awaitable

from mcp.client import get_mcp_manager


# Each pattern is (regex, tool_name, args_builder, formatter)
# tool_name is "server__tool" format


def _m(pattern: str, server: str, tool: str, args_fn=None, fmt_fn=None, desc: str = ""):
    """Build a pattern descriptor."""
    return {
        "pattern": re.compile(pattern, re.IGNORECASE),
        "server": server,
        "tool": tool,
        "args": args_fn or (lambda m: {}),
        "fmt": fmt_fn,
        "desc": desc,
    }


# ─────────────────────────────────────────────────────────────
# Formatters — convert raw MCP results to human-readable markdown
# ─────────────────────────────────────────────────────────────

def fmt_dashboards(data: Any) -> str:
    """Format list_dashboards response."""
    if not isinstance(data, list) or len(data) == 0:
        return "No dashboards found in Grafana."

    lines = [f"**Found {len(data)} dashboard{'s' if len(data) != 1 else ''}:**\n"]
    for d in data:
        title = d.get("title", "(untitled)")
        uid = d.get("uid", "")
        folder = d.get("folder_title", "General")
        tags = d.get("tags", [])
        tags_str = f" `[{', '.join(tags)}]`" if tags else ""
        url = d.get("url", "")
        lines.append(f"- **{title}** — folder: _{folder}_{tags_str}")
        if url:
            lines.append(f"  UID: `{uid}` · [Open dashboard]({url})")
    return "\n".join(lines)


def fmt_datasources(data: Any) -> str:
    """Format list_datasources response."""
    if not isinstance(data, list) or len(data) == 0:
        return "No datasources configured."

    lines = [f"**Found {len(data)} datasource{'s' if len(data) != 1 else ''}:**\n"]
    for d in data:
        name = d.get("name", "?")
        dtype = d.get("type", "?")
        url = d.get("url", "")
        default = " ⭐ _default_" if d.get("is_default") else ""
        lines.append(f"- **{name}** (`{dtype}`){default}")
        if url:
            lines.append(f"  URL: `{url}`")
    return "\n".join(lines)


def fmt_alerts(data: Any) -> str:
    """Format list_alert_rules / list_alert_instances."""
    if not isinstance(data, list) or len(data) == 0:
        return "No alerts found."

    lines = [f"**Found {len(data)} alert{'s' if len(data) != 1 else ''}:**\n"]
    for a in data[:20]:  # cap at 20
        title = a.get("title") or a.get("labels", {}).get("alertname", "(unnamed)")
        state = a.get("state", "unknown")
        emoji = {"firing": "🔴", "pending": "🟡", "inactive": "✅", "normal": "✅", "ok": "✅"}.get(state.lower(), "⚪")
        lines.append(f"- {emoji} **{title}** — _{state}_")
    if len(data) > 20:
        lines.append(f"\n_... and {len(data) - 20} more_")
    return "\n".join(lines)


def fmt_folders(data: Any) -> str:
    """Format list_folders response."""
    if not isinstance(data, list) or len(data) == 0:
        return "No folders found."
    lines = [f"**Found {len(data)} folder{'s' if len(data) != 1 else ''}:**\n"]
    for f in data:
        title = f.get("title", "(untitled)")
        uid = f.get("uid", "")
        lines.append(f"- **{title}** (`{uid}`)")
    return "\n".join(lines)


def fmt_health(data: Any) -> str:
    """Format health_check response."""
    if not isinstance(data, dict):
        return str(data)
    version = data.get("version", "?")
    db = data.get("database", "?")
    db_icon = "✅" if db == "ok" else "❌"
    return f"**Grafana Health**\n- Version: `{version}`\n- Database: {db_icon} {db}\n- Enterprise: {data.get('enterprise', False)}"


def fmt_server_info(data: Any) -> str:
    """Format get_server_info response."""
    if not isinstance(data, dict):
        return str(data)
    lines = ["**Bifröst MCP Server**"]
    for k, v in data.items():
        lines.append(f"- {k}: `{v}`")
    return "\n".join(lines)


def fmt_users(data: Any) -> str:
    """Format list_users response."""
    if not isinstance(data, list) or len(data) == 0:
        return "No users found."
    lines = [f"**Found {len(data)} user{'s' if len(data) != 1 else ''}:**\n"]
    for u in data:
        name = u.get("name") or u.get("login", "?")
        email = u.get("email", "")
        role = u.get("role", "?")
        lines.append(f"- **{name}** ({email}) — _{role}_")
    return "\n".join(lines)


def fmt_generic(data: Any) -> str:
    """Generic JSON formatter."""
    import json
    if isinstance(data, (dict, list)):
        return "```json\n" + json.dumps(data, indent=2)[:2000] + "\n```"
    return str(data)


# ─────────────────────────────────────────────────────────────
# Intent patterns — ordered by specificity (most specific first)
# ─────────────────────────────────────────────────────────────

# Order matters: most specific patterns MUST come first, generic ones last
INTENTS = [
    # ─── MOST SPECIFIC: MCP server info (must come before "server status") ───
    _m(
        r"\b(mcp|bifrost|bifr[öo]st)\b.*(info|server|status|version|metadata)",
        "bifrost-grafana", "get_server_info",
        fmt_fn=fmt_server_info,
        desc="MCP server info",
    ),
    _m(
        r"^(mcp|bifrost|bifr[öo]st)\s*(info)?$",
        "bifrost-grafana", "get_server_info",
        fmt_fn=fmt_server_info,
        desc="MCP server info",
    ),

    # ─── Dashboards: search first (more specific), then list ───
    _m(
        r"search.*(dashboard|dash).*[\"']([^\"']+)[\"']",
        "bifrost-grafana", "search_dashboards",
        args_fn=lambda m: {"query": m.group(2)},
        fmt_fn=fmt_dashboards,
        desc="Search dashboards by title",
    ),
    _m(
        r"search.*(dashboard|dash).*\s+(\S+)$",
        "bifrost-grafana", "search_dashboards",
        args_fn=lambda m: {"query": m.group(2).strip('"\'')},
        fmt_fn=fmt_dashboards,
        desc="Search dashboards (no quotes)",
    ),
    _m(
        r"(list|show|get|all).*(dashboard|dash)s?",
        "bifrost-grafana", "list_dashboards",
        fmt_fn=fmt_dashboards,
        desc="List all dashboards",
    ),

    # ─── Alerts: firing/active must come before generic list ───
    _m(
        r"(firing|active|pending).*alerts?|alerts?.*(firing|active|pending)",
        "bifrost-grafana", "list_alert_instances",
        fmt_fn=fmt_alerts,
        desc="List firing alerts",
    ),
    _m(
        r"alert\s+instances?",
        "bifrost-grafana", "list_alert_instances",
        fmt_fn=fmt_alerts,
        desc="List alert instances",
    ),
    _m(
        r"(list|show|get|all).*(alert|alert rule)s?",
        "bifrost-grafana", "list_alert_rules",
        fmt_fn=fmt_alerts,
        desc="List all alert rules",
    ),

    # ─── Datasources ───
    _m(
        r"(check|test|health).*(datasource|data source).*",
        "bifrost-grafana", "list_datasources",
        fmt_fn=fmt_datasources,
        desc="Check datasource health",
    ),
    _m(
        r"(list|show|get|all).*(datasource|data source|ds)s?",
        "bifrost-grafana", "list_datasources",
        fmt_fn=fmt_datasources,
        desc="List all datasources",
    ),

    # ─── Folders ───
    _m(
        r"(list|show|get|all).*folders?",
        "bifrost-grafana", "list_folders",
        fmt_fn=fmt_folders,
        desc="List all folders",
    ),

    # ─── Users ───
    _m(
        r"(list|show|get|all).*users?",
        "bifrost-grafana", "list_users",
        fmt_fn=fmt_users,
        desc="List all users",
    ),

    # ─── Grafana Health / Status (LAST — very generic) ───
    _m(
        r"grafana.*(health|status|version|info)|(health|status|version|info).*grafana",
        "bifrost-grafana", "health_check",
        fmt_fn=fmt_health,
        desc="Grafana health status",
    ),
    _m(
        r"\b(health\s*check|ping)\b",
        "bifrost-grafana", "health_check",
        fmt_fn=fmt_health,
        desc="Health check",
    ),
]


async def match_intent(user_message: str) -> dict | None:
    """Try to match user message to an intent. Returns intent or None."""
    if not user_message:
        return None
    for intent in INTENTS:
        match = intent["pattern"].search(user_message)
        if match:
            try:
                args = intent["args"](match)
            except Exception:
                args = {}
            return {
                "server": intent["server"],
                "tool": intent["tool"],
                "arguments": args,
                "formatter": intent["fmt"] or fmt_generic,
                "desc": intent["desc"],
            }
    return None


async def execute_intent(intent: dict) -> dict:
    """Execute the MCP tool call and format the result.

    Returns:
        {ok: bool, content: str (formatted markdown), raw_data: Any (tool data),
         duration_ms: int, tool: str, server: str, arguments: dict, error?: str}
    """
    mgr = get_mcp_manager()
    result = await mgr.call_tool(intent["server"], intent["tool"], intent["arguments"])
    if result.get("ok"):
        data = result.get("data", result)
        formatted = intent["formatter"](data)
        return {
            "ok": True,
            "content": formatted,
            "raw_data": data,  # raw tool data for LLM post-processing
            "duration_ms": result.get("duration_ms", 0),
            "tool": intent["tool"],
            "server": intent["server"],
            "arguments": intent["arguments"],
        }
    return {
        "ok": False,
        "error": result.get("error", "Unknown error"),
        "tool": intent["tool"],
        "server": intent["server"],
    }
