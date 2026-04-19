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

I can help you with real Grafana data via MCP tools. Try asking:

**📊 Dashboards**
- `list all dashboards` → see all 113 dashboards
- `list AKS dashboards` · `Azure dashboards` · `Loki dashboards`
- `search dashboards postgres` → text search
- `payment-service dashboards` → find service-specific

**🗂️ Folders & Organization**
- `list folders` → all 15 folders with direct links
- `list all alerts` · `show firing alerts`

**📡 Datasources**
- `list datasources` → Mimir, Loki, Tempo

**💓 Grafana Health**
- `check grafana health` → version + DB status
- `grafana info` / `mcp server info`

**🏷️ Categories I know (35+)**
- **Cloud**: AKS, Azure, OCI, GCP, AWS, GKE
- **Databases**: PostgreSQL, MySQL, Redis, Cosmos, Cassandra
- **Observability**: Loki, Mimir, Tempo, Pyroscope
- **SRE**: SLO, RED metrics, performance, errors
- **Compliance**: PCI, HIPAA, SOC2, GDPR, security
- **Levels**: L0–L3 (executive → deep-dive)

**📝 PromQL / LogQL / TraceQL help**
- `promql for error rate by service`
- `logql to find errors`

**⚠️ Remember:** Only I can fetch LIVE Grafana data. For generic knowledge questions without a tool match, I'll give general answers — if they sound vague, try a specific command from the list above.

**Keyboard shortcuts:** press `⌘/` (Mac) or `Ctrl/` (Windows/Linux)"""


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
