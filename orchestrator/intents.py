"""Intent matcher — detects common observability queries and routes them to MCP tools directly.

This provides reliable tool calling even with small LLMs (qwen2.5:0.5b) that can't handle
function calling natively. Pattern: match user query → call MCP tool → format result.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Awaitable

from mcp.client import get_mcp_manager
from categories import CATEGORIES, extract_service_name, find_category


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


def _slugify(text: str) -> str:
    """Grafana-compatible slug from a folder title."""
    import re
    s = text.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "folder"


def fmt_folders(data: Any) -> str:
    """Format list_folders response with names as clickable links to Grafana folder pages."""
    if not isinstance(data, list) or len(data) == 0:
        return "No folders found."
    lines = [f"**Found {len(data)} folder{'s' if len(data) != 1 else ''}:**\n"]
    for f in data:
        title = f.get("title", "(untitled)")
        uid = f.get("uid", "")
        url = f.get("url") or f"/dashboards/f/{uid}/{_slugify(title)}"
        # Show prominent name with link, UID as small hint
        lines.append(f"- 📁 [**{title}**]({url})")
        if uid:
            lines.append(f"  <sup>`uid: {uid}`</sup>")
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


def fmt_capabilities(data: Any) -> str:
    """Static capabilities response — shows the bot's REAL abilities.

    Used when user asks 'what can you do?', 'help', etc.
    Avoids LLM hallucinating made-up abilities.
    """
    return """**I'm O11yBot — your Grafana observability assistant.**

Everything I do is a real MCP call against Grafana — no fabricated answers.

**📊 Dashboards — read**
- `list all dashboards` · `list AKS / Azure / Loki dashboards`
- `search dashboards postgres` · `payment-service dashboards`
- `show dashboard <uid>` · `panels in <uid>` · `summarize dashboard <uid>`

**✏️ Dashboards — write (editor+)**
- `create a dashboard called "Payment SLOs"`
- `create dashboard for checkout-service`
- `delete dashboard <uid>` *(admin)*

**🚨 Alerts**
- `list alert rules` · `show firing alerts`
- `explain alert <uid>` · `why is <uid> firing?`
- `silence alert <uid>` *(editor+)*

**📡 Datasources & queries**
- `list datasources` · `get datasource prometheus`
- `run promql sum(rate(http_requests_total[5m]))`

**🗂️ Folders & Organization**
- `list folders` · `create folder "My team"` *(editor+)*
- `list users` · `list service accounts` *(admin)*

**💓 Grafana Health & Introspection**
- `check grafana health` · `grafana info` · `mcp server info`

**📝 Query authoring help**
- `promql cookbook` · `logql examples` · `traceql templates`
- `slo cheat sheet`

**🧭 Navigation & errors**
- `where do I find alert rules?` · `navigate`
- `decode error: context deadline exceeded`

**🏷️ Categories I know (35+)**
- **Cloud**: AKS, Azure, OCI, GCP, AWS, GKE
- **Databases**: PostgreSQL, MySQL, Redis, Cosmos, Cassandra
- **Observability**: Loki, Mimir, Tempo, Pyroscope
- **SRE**: SLO, RED metrics, performance, errors
- **Compliance**: PCI, HIPAA, SOC2, GDPR, security
- **Levels**: L0–L3 (executive → deep-dive)

**⚠️ Anything I can't match to a tool falls through to my LLM reasoning.** Prefer the commands above for live data.

**Keyboard shortcuts:** `⌘/` (Mac) or `Ctrl/` (Windows/Linux)"""


def fmt_dashboards_filtered(data: Any, category_label: str | None = None,
                             service_name: str | None = None) -> str:
    """Format filtered dashboards with category context header."""
    if not isinstance(data, list) or len(data) == 0:
        if category_label:
            return f"No dashboards found for **{category_label}**."
        if service_name:
            return f"No dashboards found for service **{service_name}**."
        return "No dashboards found."

    header_parts = [f"**Found {len(data)} dashboard{'s' if len(data) != 1 else ''}"]
    if category_label:
        header_parts.append(f"in category _{category_label}_")
    if service_name:
        header_parts.append(f"matching service _{service_name}_")
    header_parts.append(":**\n")
    lines = [" ".join(header_parts)]

    # Group by folder for scannability
    from collections import defaultdict
    by_folder = defaultdict(list)
    for d in data:
        by_folder[d.get("folder_title", "General")].append(d)

    for folder, items in sorted(by_folder.items()):
        if len(by_folder) > 1:
            lines.append(f"\n### 📁 {folder}")
        for d in items:
            title = d.get("title", "(untitled)")
            uid = d.get("uid", "")
            tags = d.get("tags", [])
            tags_str = f" `[{', '.join(tags[:4])}]`" if tags else ""
            url = d.get("url", "")
            lines.append(f"- **{title}**{tags_str}")
            if url:
                lines.append(f"  UID: `{uid}` · [Open dashboard]({url})")

    return "\n".join(lines)


def fmt_dashboard_detail(data: Any) -> str:
    """Format a get_dashboard response with panel list + metadata."""
    if not isinstance(data, dict):
        return "Dashboard not found."
    title = data.get("title", "(untitled)")
    uid = data.get("uid", "")
    version = data.get("version", 0)
    tags = data.get("tags", []) or []
    folder = data.get("folder_title", "General")
    url = data.get("url", "") or (f"/d/{uid}" if uid else "")
    panels = data.get("panels", []) or []

    lines = [f"**📊 Dashboard: {title}**\n"]
    lines.append(f"- UID: `{uid}` · version: `{version}` · folder: _{folder}_")
    if tags:
        lines.append(f"- Tags: `{', '.join(tags[:8])}`")
    if url:
        lines.append(f"- [Open dashboard]({url})")
    lines.append(f"\n**Panels ({len(panels)}):**")
    for p in panels[:30]:
        ptype = p.get("type") or "?"
        ptitle = p.get("title") or "(untitled)"
        ds = p.get("datasource") or ""
        ds_bit = f" · ds: `{ds}`" if ds else ""
        lines.append(f"- [{ptype}] **{ptitle}**{ds_bit}")
    if len(panels) > 30:
        lines.append(f"\n_... and {len(panels) - 30} more panels_")
    return "\n".join(lines)


def fmt_dashboard_panels(data: Any) -> str:
    """Format get_dashboard_panels (list of DashboardPanel)."""
    if not isinstance(data, list) or not data:
        return "No panels in this dashboard."
    lines = [f"**Found {len(data)} panel{'s' if len(data) != 1 else ''}:**\n"]
    for p in data:
        ptype = p.get("type") or "?"
        ptitle = p.get("title") or "(untitled)"
        ds = p.get("datasource") or ""
        desc = p.get("description") or ""
        ds_bit = f" · ds: `{ds}`" if ds else ""
        lines.append(f"- [{ptype}] **{ptitle}**{ds_bit}")
        if desc:
            lines.append(f"  _{desc[:120]}_")
    return "\n".join(lines)


def fmt_alert_detail(data: Any) -> str:
    """Format get_alert_rule response."""
    if not isinstance(data, dict):
        return "Alert rule not found."
    title = data.get("title") or data.get("name") or "(unnamed)"
    uid = data.get("uid", "")
    group = data.get("group") or data.get("ruleGroup") or "?"
    folder = data.get("folder_uid") or data.get("folderUid") or "?"
    state = (data.get("state") or "").lower()
    condition = data.get("condition", "")
    no_data = data.get("no_data_state") or data.get("noDataState") or "?"
    exec_err = data.get("exec_err_state") or data.get("execErrState") or "?"
    lines = [f"**🚨 Alert rule: {title}**\n"]
    lines.append(f"- UID: `{uid}` · group: _{group}_ · folder: `{folder}`")
    if state:
        emoji = {"firing": "🔴", "pending": "🟡", "inactive": "✅", "normal": "✅"}.get(state, "⚪")
        lines.append(f"- State: {emoji} **{state}**")
    if condition:
        lines.append(f"- Condition: `{condition}`")
    lines.append(f"- On no-data: `{no_data}` · on exec error: `{exec_err}`")
    annot = data.get("annotations") or {}
    if annot:
        lines.append("\n**Annotations:**")
        for k, v in list(annot.items())[:6]:
            lines.append(f"- `{k}`: {str(v)[:160]}")
    labels = data.get("labels") or {}
    if labels:
        lines.append("\n**Labels:**")
        for k, v in list(labels.items())[:8]:
            lines.append(f"- `{k}` = `{v}`")
    return "\n".join(lines)


def fmt_datasource_detail(data: Any) -> str:
    """Format get_datasource response."""
    if not isinstance(data, dict):
        return "Datasource not found."
    name = data.get("name", "?")
    dtype = data.get("type", "?")
    uid = data.get("uid", "")
    url = data.get("url", "")
    is_default = data.get("is_default") or data.get("isDefault")
    access = data.get("access", "")
    lines = [f"**📡 Datasource: {name}**\n"]
    lines.append(f"- Type: `{dtype}` · UID: `{uid}`")
    if url:
        lines.append(f"- URL: `{url}`")
    if access:
        lines.append(f"- Access mode: `{access}`")
    if is_default:
        lines.append("- ⭐ Default datasource")
    return "\n".join(lines)


def fmt_query_result(data: Any) -> str:
    """Format query_datasource response — compact tabular preview."""
    if not isinstance(data, dict):
        return "```\n" + str(data)[:1500] + "\n```"
    results = data.get("results") or {}
    if not results:
        return "**Query returned no results.**"
    lines = ["**🔍 Query results:**\n"]
    for ref_id, r in list(results.items())[:5]:
        frames = r.get("frames") or []
        total_rows = 0
        for f in frames:
            d = f.get("data") or {}
            values = d.get("values") or []
            if values:
                total_rows += len(values[0])
        lines.append(f"- `{ref_id}` — {len(frames)} frame(s), ~{total_rows} row(s)")
        for f in frames[:2]:
            schema = f.get("schema") or {}
            fields = [x.get("name", "?") for x in (schema.get("fields") or [])]
            if fields:
                lines.append(f"  fields: `{', '.join(fields[:6])}`")
    return "\n".join(lines)


def fmt_service_accounts(data: Any) -> str:
    """Format list_service_accounts."""
    if not isinstance(data, list) or not data:
        return "No service accounts found."
    lines = [f"**Found {len(data)} service account{'s' if len(data) != 1 else ''}:**\n"]
    for sa in data[:30]:
        name = sa.get("name", "?")
        role = sa.get("role", "?")
        disabled = sa.get("is_disabled") or sa.get("isDisabled")
        status = "🚫 disabled" if disabled else "✅ enabled"
        lines.append(f"- **{name}** — role: `{role}` · {status}")
    return "\n".join(lines)


def fmt_mutation(data: Any) -> str:
    """Format a create/update/delete DashboardMutationResult."""
    if not isinstance(data, dict):
        return "Operation complete."
    status = data.get("status", "success")
    uid = data.get("uid", "")
    url = data.get("url", "")
    msg = data.get("message") or f"Status: {status}"
    version = data.get("version", 0)
    ok_emoji = "✅" if data.get("ok", True) else "⚠️"
    lines = [f"{ok_emoji} **{msg}**\n"]
    if uid:
        lines.append(f"- UID: `{uid}`")
    if version:
        lines.append(f"- Version: `{version}`")
    if url:
        lines.append(f"- [Open in Grafana]({url})")
    return "\n".join(lines)


def fmt_navigation(_data: Any) -> str:
    """Static navigation map — where to find things in Grafana."""
    return """**🧭 Finding things in Grafana**

| What you want | Where it lives |
|---|---|
| Dashboards | `/dashboards` — top nav → Dashboards |
| Create dashboard | `/dashboard/new` or click `+ → New dashboard` |
| Explore metrics/logs/traces | `/explore` — compass icon in left rail |
| Alert rules | `/alerting/list` — bell icon in left rail |
| Silences | `/alerting/silences` — under Alerting |
| Contact points | `/alerting/notifications` |
| Data sources | `/connections/datasources` or `/datasources` |
| Users & teams | `/admin/users`, `/admin/teams` (admin) |
| Service accounts | `/org/serviceaccounts` (admin) |
| API keys | Rotate in service-account page |
| Plugins | `/plugins` |
| Preferences / theme | `/profile/preferences` |
| Keyboard shortcuts | `?` key in Grafana, or `⌘/` here in O11yBot |

Ask me: `where do I find alert rules?` · `how do I create a dashboard?` · `how do I silence an alert?`
"""


def fmt_error_decode(_data: Any) -> str:
    """Help text when user asks to decode a Grafana error without providing one."""
    return """**🩺 Error decoder**

Paste the error message after `decode error:` and I'll explain what it means. Common ones:

| Error | Meaning |
|---|---|
| `Data source not found` | UID in panel JSON doesn't match any configured datasource. Update the datasource UID. |
| `bad_data: invalid parameter "query"` | PromQL syntax error — check for unbalanced brackets or missing `by()` labels. |
| `context deadline exceeded` | Query took longer than the datasource timeout. Narrow the time range or add more specific labels. |
| `too many samples` | Query returns > `--max-samples`. Add label filters or increase step in range queries. |
| `429 Too Many Requests` | Rate limited — slow down queries or check your cloud plan limits. |
| `Panel plugin not found` | Missing panel plugin — install via `/plugins` or switch to a built-in type. |

Try: `decode error: context deadline exceeded`
"""


def fmt_promql_helper(_data: Any) -> str:
    """Static PromQL examples with scenarios."""
    return """**📝 PromQL cookbook**

**Rate of errors per service (last 5m)**
```promql
sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
```

**p95 request latency per endpoint**
```promql
histogram_quantile(0.95, sum by (le, endpoint) (rate(http_request_duration_seconds_bucket[5m])))
```

**Error rate % over time**
```promql
100 * sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
```

**CPU usage per pod**
```promql
sum by (pod) (rate(container_cpu_usage_seconds_total[5m]))
```

**Memory usage — top 10 pods**
```promql
topk(10, sum by (pod) (container_memory_working_set_bytes))
```

**Alerting: burn-rate SLO (2h fast burn)**
```promql
(sum(rate(http_requests_total{status=~"5.."}[2h])) / sum(rate(http_requests_total[2h]))) > (14.4 * (1 - 0.999))
```
"""


def fmt_logql_helper(_data: Any) -> str:
    """Static LogQL examples."""
    return """**📜 LogQL cookbook**

**Find errors in service logs**
```logql
{service="payment-service"} |= "ERROR"
```

**Count errors per level, last 5m**
```logql
sum by (level) (count_over_time({service="payment-service"} |= "ERROR" [5m]))
```

**Parse JSON logs and filter by status**
```logql
{app="api"} | json | status >= 500
```

**Rate of log lines per pod**
```logql
sum by (pod) (rate({app="api"} [1m]))
```

**Logs containing user_id, extracted**
```logql
{app="api"} |= "user_id" | regexp `user_id=(?P<uid>\\d+)`
```
"""


def fmt_traceql_helper(_data: Any) -> str:
    """Static TraceQL examples."""
    return """**🔎 TraceQL cookbook**

**Find slow traces > 1s**
```traceql
{ duration > 1s }
```

**Slow payment-service traces**
```traceql
{ resource.service.name = "payment-service" && duration > 500ms }
```

**HTTP 5xx errors**
```traceql
{ span.http.status_code >= 500 }
```

**Database span slower than 100ms**
```traceql
{ span.db.system = "postgresql" && span.duration > 100ms }
```

**Root span that called a specific service**
```traceql
{ resource.service.name = "gateway" } >> { resource.service.name = "inventory" }
```
"""


def fmt_slo_helper(_data: Any) -> str:
    """Static SLO authoring guide."""
    return """**🎯 SLO authoring cheat sheet**

**1. Define the SLI** — a raw measure of good behaviour.
```promql
# Availability SLI: fraction of good requests
sum(rate(http_requests_total{status!~"5.."}[5m])) /
sum(rate(http_requests_total[5m]))
```

**2. Pick the SLO target** — e.g. 99.9% over 30 days.

**3. Error budget consumed (30d)**
```promql
1 - (sum(increase(http_requests_total{status!~"5.."}[30d])) /
     sum(increase(http_requests_total[30d])))
```
Alert when consumed > `1 - 0.999` (= 0.001).

**4. Fast-burn alert (2h window, 14.4× budget spend rate)**
```promql
(
  1 - sum(rate(http_requests_total{status!~"5.."}[2h])) /
      sum(rate(http_requests_total[2h]))
) > (14.4 * 0.001)
```

**5. Slow-burn alert (24h window, 1× rate)** — catches chronic degradation.

Record the SLI + error-budget as recording rules for reuse in dashboards.
"""


# ─────────────────────────────────────────────────────────────
# Intent patterns — ordered by specificity (most specific first)
# ─────────────────────────────────────────────────────────────

# Order matters: most specific patterns MUST come first, generic ones last
INTENTS = [
    # ─── HELP / CAPABILITIES — highest priority, static response (no LLM, no MCP) ───
    # Matches: "help", "what can you do", "how can you help me", "capabilities",
    #          "what do you do", "what are your tools", "/help", "commands"
    _m(
        r"^\s*(/help|/commands|help|capabilities)\s*\??\s*$",
        "_internal", "help",
        fmt_fn=fmt_capabilities,
        desc="Show capabilities",
    ),
    _m(
        r"\b(what\s+(can|do|are|is)|how\s+(can|do)).*\b(help|you\s+do|your\s+tools|your\s+capabilit|commands|available)",
        "_internal", "help",
        fmt_fn=fmt_capabilities,
        desc="Show capabilities",
    ),
    _m(
        r"\b(what\s+tools|list\s+(all\s+)?(tools|commands|capabilities))\b",
        "_internal", "help",
        fmt_fn=fmt_capabilities,
        desc="Show capabilities",
    ),

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

    # ─── Service accounts (admin) ───
    _m(
        r"(list|show|get|all).*(service\s*accounts?|sa)s?\b",
        "bifrost-grafana", "list_service_accounts",
        fmt_fn=fmt_service_accounts,
        desc="List service accounts",
    ),

    # ─── Dashboard detail by UID ───
    _m(
        r"(get|show|open|describe|summari[sz]e).*(dashboard|dash).*\b(uid[:\s]+)?([a-zA-Z0-9_-]{6,})\b",
        "bifrost-grafana", "get_dashboard",
        args_fn=lambda m: {"uid": m.group(4)},
        fmt_fn=fmt_dashboard_detail,
        desc="Get dashboard detail by UID",
    ),
    _m(
        r"(what\s+panels?|list\s+panels?|panels?\s+in).*([a-zA-Z0-9_-]{6,})\b",
        "bifrost-grafana", "get_dashboard_panels",
        args_fn=lambda m: {"uid": m.group(2)},
        fmt_fn=fmt_dashboard_panels,
        desc="List panels in a dashboard",
    ),

    # ─── Alert detail / explanation by UID ───
    _m(
        r"(get|show|describe|explain|why.*firing).*alert.*\b([a-zA-Z0-9_-]{6,})\b",
        "bifrost-grafana", "get_alert_rule",
        args_fn=lambda m: {"uid": m.group(2)},
        fmt_fn=fmt_alert_detail,
        desc="Get alert rule detail",
    ),

    # ─── Datasource detail / query ───
    _m(
        r"(get|show|describe).*(datasource|data source)\s+([a-zA-Z0-9_-]{3,})\b",
        "bifrost-grafana", "get_datasource",
        args_fn=lambda m: {"uid": m.group(3)},
        fmt_fn=fmt_datasource_detail,
        desc="Get datasource detail",
    ),
    _m(
        r"(run|execute|query).*promql\s+(.+)",
        "bifrost-grafana", "query_datasource",
        args_fn=lambda m: {"uid": "prometheus", "query": m.group(2).strip()},
        fmt_fn=fmt_query_result,
        desc="Run a PromQL query",
    ),

    # ─── Silence an alert (editor+) ───
    _m(
        r"silence.*alert\s+([a-zA-Z0-9_-]{6,})",
        "bifrost-grafana", "silence_alert",
        args_fn=lambda m: {"alert_uid": m.group(1)},
        fmt_fn=fmt_generic,
        desc="Silence an alert",
    ),

    # ─── Create / mutate dashboards + folders (editor+) ───
    _m(
        r"create.*dashboard.*(?:called|named|titled)\s+[\"']?([^\"']+?)[\"']?\s*(?:$|for|with|in)",
        "bifrost-grafana", "create_dashboard",
        args_fn=lambda m: {"title": m.group(1).strip(), "tags": []},
        fmt_fn=fmt_mutation,
        desc="Create a new dashboard",
    ),
    _m(
        r"(create|new)\s+dashboard\s+for\s+(.+)$",
        "bifrost-grafana", "create_dashboard",
        args_fn=lambda m: {"title": m.group(2).strip().title(), "tags": [m.group(2).strip().lower().replace(" ", "-")]},
        fmt_fn=fmt_mutation,
        desc="Create dashboard for topic/service",
    ),
    _m(
        r"delete.*dashboard\s+([a-zA-Z0-9_-]{6,})",
        "bifrost-grafana", "delete_dashboard",
        args_fn=lambda m: {"uid": m.group(1)},
        fmt_fn=fmt_mutation,
        desc="Delete a dashboard",
    ),
    _m(
        r"(create|new|add)\s+folder\s+[\"']?([^\"']+?)[\"']?$",
        "bifrost-grafana", "create_folder",
        args_fn=lambda m: {"title": m.group(2).strip()},
        fmt_fn=fmt_mutation,
        desc="Create a folder",
    ),

    # ─── Authoring helpers (static — no tool call) ───
    _m(
        r"\b(promql|prom\s*ql)\b.*(cheat|example|help|cookbook|how|template)",
        "_internal", "promql_help",
        fmt_fn=fmt_promql_helper,
        desc="PromQL cookbook",
    ),
    _m(
        r"\b(logql|log\s*ql)\b.*(cheat|example|help|cookbook|how|template)",
        "_internal", "logql_help",
        fmt_fn=fmt_logql_helper,
        desc="LogQL cookbook",
    ),
    _m(
        r"\b(traceql|trace\s*ql)\b.*(cheat|example|help|cookbook|how|template)",
        "_internal", "traceql_help",
        fmt_fn=fmt_traceql_helper,
        desc="TraceQL cookbook",
    ),
    _m(
        r"\bslo\b.*(help|cheat|how|author|create|example|guide|cookbook)",
        "_internal", "slo_help",
        fmt_fn=fmt_slo_helper,
        desc="SLO authoring guide",
    ),

    # ─── Navigation / find things in Grafana ───
    _m(
        r"(where\s+(?:is|do|can)|how\s+(?:do|to)\s+(?:find|get|open|reach|navigate))",
        "_internal", "navigation",
        fmt_fn=fmt_navigation,
        desc="Grafana navigation help",
    ),
    _m(
        r"\bnav(igat\w*)?\b",
        "_internal", "navigation",
        fmt_fn=fmt_navigation,
        desc="Grafana navigation help",
    ),

    # ─── Error decoder (static list — specific errors pipe through LLM) ───
    _m(
        r"\b(decode|explain|what.*mean|what.*error)\s+error[:\s]*$",
        "_internal", "error_decode",
        fmt_fn=fmt_error_decode,
        desc="Error decoder help",
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
    """Try to match user message to an intent. Returns intent or None.

    Priority (FIRST match wins):
      1. Service-specific dashboard search (e.g., "payment-service dashboards")
      2. Category-filtered dashboards (e.g., "list AKS dashboards")
      3. Exact intent patterns (e.g., "list datasources")
      4. Category-only fallback (e.g., "show me AKS stuff")
    """
    if not user_message:
        return None

    msg_lower = user_message.lower()
    # Typo-tolerant dashboard keyword matcher
    # Accepts: dashboard, dashboards, dashbord, dashbords, dashbaord, dashbaords,
    #          dashboad, dashborad, dash, dashes, panels, boards
    has_dashboard_keyword = bool(re.search(
        r"\b(dash\w{0,8}|boards?|panels?)\b",
        msg_lower,
    ))
    starts_with_search = re.match(r"^\s*(search|find)\b", msg_lower) is not None

    # ── 0. Explicit "search" — check INTENTS first for search_dashboards ──
    # This ensures "search dashboards aks" uses search_dashboards, not category list
    if starts_with_search:
        for intent in INTENTS:
            match = intent["pattern"].search(user_message)
            if match and intent["tool"] == "search_dashboards":
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

    # ── 0.5. Mutation intents (create/delete) — HIGHEST priority ──
    # Route "create X dashboard(s)" / "delete dashboard <uid>" BEFORE fuzzy search
    # so we never list when the user wants to create.
    mutation_intent = _match_mutation_intent(user_message, has_dashboard_keyword)
    if mutation_intent:
        return mutation_intent

    # ── 1. Service-specific search — HIGH priority ──
    svc = extract_service_name(user_message)
    if svc and has_dashboard_keyword:
        return {
            "server": "bifrost-grafana",
            "tool": "search_dashboards",
            "arguments": {"query": svc},
            "formatter": lambda data: fmt_dashboards_filtered(data, service_name=svc),
            "desc": f"Search dashboards for service: {svc}",
            "service": svc,
            "judge": True,  # fuzzy service match → rerank by relevance
        }

    # ── 2. Category-filtered dashboards (single-keyword queries only) ──
    # For multi-keyword queries like "oracle kpi dashboards", skip this
    # and go to Phase 5 local fuzzy search so ALL keywords must hit.
    if has_dashboard_keyword:
        keyword_count = len(_extract_keyword_list(user_message))
        if keyword_count <= 1:
            cat = find_category(user_message)
            if cat:
                return {
                    "server": "bifrost-grafana",
                    "tool": "list_dashboards",
                    "arguments": {"tags": [cat["tags"][0]]},
                    "formatter": lambda data: fmt_dashboards_filtered(data, category_label=cat["label"]),
                    "desc": f"List dashboards filtered by: {cat['label']}",
                    "category": cat["key"],
                }

    # ── 3. All other exact intent patterns ──
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

    # ── 4. Category-only query (no explicit "dashboard" word) ──
    # e.g. "show me AKS stuff", "view kubernetes", "Oracle", "what's in AKS"
    # Skip when 2+ meaningful keywords — prefer Phase 5 local fuzzy (all must hit).
    if len(_extract_keyword_list(user_message)) <= 1 and (cat := find_category(user_message)):
        # Be generous: if message is short OR has an action word, treat as category query
        word_count = len(msg_lower.split())
        has_trigger = any(trigger in msg_lower for trigger in [
            "show", "list", "get", "see", "view", "find", "whats", "what's",
            "have", "give", "tell", "in ", "all ", "any",
        ])
        # Single-word or short query (≤3 words) that matches a category → list it
        if has_trigger or word_count <= 3:
            return {
                "server": "bifrost-grafana",
                "tool": "list_dashboards",
                "arguments": {"tags": [cat["tags"][0]]},
                "formatter": lambda data: fmt_dashboards_filtered(data, category_label=cat["label"]),
                "desc": f"List {cat['label']} dashboards",
                "category": cat["key"],
            }

    # ── 5. Dashboard fallthrough — local fuzzy search over every dashboard ──
    # We fetch the full dashboard list and score by how many user keywords
    # appear in (title + tags + folder). This catches typos and random
    # keyword combos that Bifrost's literal search would miss.
    if has_dashboard_keyword:
        keywords = _extract_keyword_list(user_message)
        if keywords:
            query_label = " ".join(keywords[:4])
            return {
                "server": "bifrost-grafana",
                "tool": "list_dashboards",
                "arguments": {},  # no tag filter — pull everything, filter locally
                "formatter": lambda data: fmt_dashboards_filtered(
                    _local_fuzzy_match(data, keywords), service_name=query_label
                ),
                "raw_transform": lambda data: _local_fuzzy_match(data, keywords),
                "desc": f"Local fuzzy search: {query_label}",
                "judge": True,  # rerank the pre-filtered candidates
            }

    return None


def _local_fuzzy_match(data: Any, keywords: list[str]) -> list[dict]:
    """Score each dashboard by how many of the user's keywords appear in
    its title, tags, or folder name. Returns dashboards with ≥1 hit,
    highest-scoring first, up to 20.

    Handles any random word combination without requiring exact Bifrost
    substring matches — so typos in filler words don't zero out results.
    """
    if not isinstance(data, list) or not keywords:
        return data if isinstance(data, list) else []
    scored: list[tuple[int, dict]] = []
    kws = [k.lower() for k in keywords]
    for d in data:
        if not isinstance(d, dict):
            continue
        haystack = " ".join([
            (d.get("title") or "").lower(),
            " ".join(d.get("tags") or []).lower(),
            (d.get("folder_title") or "").lower(),
        ])
        hits = sum(1 for k in kws if k in haystack)
        if hits > 0:
            scored.append((hits, d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:20]]


_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should",
    "can", "could", "may", "might", "must", "shall", "to", "of", "in", "on",
    "at", "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "from", "up", "down", "out",
    "off", "over", "under", "again", "further", "then", "once",
    "and", "but", "or", "nor", "so", "if", "whether",
    "what", "which", "who", "whom", "whose", "this", "that", "these", "those",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their", "mine", "yours", "ours", "theirs",
    "show", "list", "get", "find", "give", "tell", "see", "view",
    "dashboard", "dashboards", "dash", "dashes", "panels",
    "grafana", "please", "me", "for", "all", "any",
    "any", "some", "every", "each", "few", "more", "most", "other",
    "create", "make", "build", "help", "about", "here",
}


def _extract_search_keywords(text: str) -> str:
    """Return a space-joined list of up to 4 meaningful tokens."""
    return " ".join(_extract_keyword_list(text)[:4])


def _extract_keyword_list(text: str) -> list[str]:
    """Extract meaningful keyword tokens — stopwords + dashboard-indicator
    typos removed so Bifrost/local search doesn't dilute on "dashbords" etc.

    E.g. "show me oracle kpi dashbords"  → ["oracle", "kpi"]
    """
    import re
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", text.lower())
    out: list[str] = []
    for w in words:
        if len(w) < 2:
            continue
        if w in _STOP_WORDS:
            continue
        # Drop dashboard-indicator variants and their typos (dash*, board*, panel*)
        if re.match(r"^(dash\w*|boards?|panels?)$", w):
            continue
        out.append(w)
    # Dedupe preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for w in out:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq


def _extract_dashboard_title(body: str) -> str:
    """Clean the body of a 'create ... dashboard' request down to a usable title.

    Strips articles, dashboard-indicator words, typos, and quote chars.
    Returns a Title-Cased string or '' if nothing meaningful remains.
    """
    # Drop surrounding quotes
    cleaned = re.sub(r"[\"']", "", body).strip()
    # Drop dashboard indicators + common glue words
    cleaned = re.sub(
        r"\b(dash\w*|boards?|panels?|a|an|the|some|any|new|called|named|titled|for|me|please)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -·—:,")
    if not cleaned:
        return ""
    # Preserve existing uppercase tokens (acronyms like "AKS", "KPI", "SLO")
    parts = cleaned.split()
    title_parts = [p if p.isupper() else p.capitalize() for p in parts]
    return " ".join(title_parts)


def _match_mutation_intent(user_message: str, has_dashboard_keyword: bool) -> dict | None:
    """Detect create/delete/update dashboard requests.

    Runs before fuzzy search so `create the grafana admin dashboard` doesn't
    accidentally list dashboards.
    """
    msg = user_message.strip()

    # Delete: "delete dashboard <uid>"
    dm = re.match(r"^\s*(delete|remove|drop)\s+(?:the\s+)?dash\w*\s+([a-zA-Z0-9_-]{6,})", msg, re.IGNORECASE)
    if dm:
        return {
            "server": "bifrost-grafana",
            "tool": "delete_dashboard",
            "arguments": {"uid": dm.group(2)},
            "formatter": fmt_mutation,
            "desc": f"Delete dashboard {dm.group(2)}",
        }

    # Create folder: "create folder <name>" or "new folder <name>"
    fm = re.match(r"^\s*(create|make|build|new|add)\s+folder\s+[\"']?([^\"']+?)[\"']?\s*$", msg, re.IGNORECASE)
    if fm:
        return {
            "server": "bifrost-grafana",
            "tool": "create_folder",
            "arguments": {"title": fm.group(2).strip()},
            "formatter": fmt_mutation,
            "desc": f"Create folder: {fm.group(2).strip()}",
        }

    # Create dashboard — broad: any "create/new/make/build/add … dashboard …"
    cm = re.match(r"^\s*(create|make|build|new|add)\s+(.*?)\s*$", msg, re.IGNORECASE)
    if cm and has_dashboard_keyword:
        title = _extract_dashboard_title(cm.group(2))
        if title:
            tag = title.lower().replace(" ", "-")[:40]
            return {
                "server": "bifrost-grafana",
                "tool": "create_dashboard",
                "arguments": {"title": title, "tags": [tag]},
                "formatter": fmt_mutation,
                "desc": f"Create dashboard: {title}",
            }
    return None


async def execute_intent(intent: dict, role: str | None = None) -> dict:
    """Execute the MCP tool call and format the result.

    Args:
        intent: the intent dict from match_intent()
        role: Grafana role (viewer|editor|admin) for RBAC enforcement.
              When provided, Bifrost uses the role-specific token.

    Returns:
        {ok: bool, content: str (formatted markdown), raw_data: Any (tool data),
         duration_ms: int, tool: str, server: str, arguments: dict, error?: str}
    """
    # Internal tools — respond without calling MCP (e.g., help/capabilities)
    if intent.get("server") == "_internal":
        formatted = intent["formatter"](None)
        return {
            "ok": True,
            "content": formatted,
            "raw_data": None,
            "duration_ms": 0,
            "tool": intent["tool"],
            "server": intent["server"],
            "arguments": intent.get("arguments", {}),
        }

    mgr = get_mcp_manager()
    result = await mgr.call_tool(intent["server"], intent["tool"], intent["arguments"], role=role)
    if result.get("ok"):
        data = result.get("data", result)
        formatted = intent["formatter"](data)
        # Expose the post-transformed data (e.g. locally-fuzzy-matched list)
        # so downstream consumers (judge, LLM formatter) see the filtered view.
        raw_for_downstream = data
        if "raw_transform" in intent:
            try:
                raw_for_downstream = intent["raw_transform"](data)
            except Exception:
                pass
        return {
            "ok": True,
            "content": formatted,
            "raw_data": raw_for_downstream,  # filtered tool data for LLM post-processing
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
