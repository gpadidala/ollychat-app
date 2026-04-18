"""Prompt engineering for O11yBot.

Centralizes:
- System prompts by query type
- Temperature + token tuning by intent
- Context injection (user, time, Grafana state)
- Few-shot examples
- Tool-result → natural-language reformulation prompts
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

QueryType = Literal[
    "tool_result_formatting",  # LLM rephrases tool output
    "observability_qa",        # general Q&A about observability
    "promql_help",             # PromQL / LogQL / TraceQL help
    "incident_analysis",       # multi-step reasoning
    "chitchat",                # conversational fillers
]


@dataclass
class GenerationConfig:
    """LLM sampling config tuned per query type."""
    temperature: float
    top_p: float
    max_tokens: int
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


# ─────────────────────────────────────────────────────────────
# Temperature + max_tokens tuned per query type
# ─────────────────────────────────────────────────────────────
GENERATION_PROFILES: dict[QueryType, GenerationConfig] = {
    # Rephrasing structured data — be precise, no creativity
    "tool_result_formatting": GenerationConfig(
        temperature=0.1, top_p=0.8, max_tokens=800,
    ),
    # Factual observability answers — low temp for accuracy
    "observability_qa": GenerationConfig(
        temperature=0.2, top_p=0.85, max_tokens=500,
    ),
    # Query help — need correct syntax, low temp
    "promql_help": GenerationConfig(
        temperature=0.15, top_p=0.85, max_tokens=600,
    ),
    # Multi-step reasoning — slightly higher for exploration
    "incident_analysis": GenerationConfig(
        temperature=0.3, top_p=0.9, max_tokens=1500,
    ),
    # Small talk — a bit of warmth
    "chitchat": GenerationConfig(
        temperature=0.5, top_p=0.9, max_tokens=150,
    ),
}


# ─────────────────────────────────────────────────────────────
# System prompts (role, constraints, style)
# ─────────────────────────────────────────────────────────────

_BASE_SYSTEM = """You are O11yBot, an expert observability assistant embedded in Grafana.

Identity:
- You live inside Grafana as a floating chatbot
- You have access to 16 real MCP tools against a live Grafana instance
- The user is logged in as: {user_name} ({user_role})
- Current UTC time: {current_time}
- Grafana version: 11.6.4 · 113 dashboards · Datasources: Mimir (Prometheus), Loki, Tempo

Core rules — never violate:
1. Be concise. Prefer bullet points over paragraphs. No fluff.
2. Use code fences for queries (```promql / ```logql / ```traceql / ```sql).
3. If you don't know or haven't run a tool, SAY "I don't know" — don't fabricate.
4. Never invent dashboard names, UIDs, metric names, or values.
5. Always propose an *actionable next step* — a query to run, a dashboard to open, or a tool call.
6. Use observability terminology correctly: RED method (Rate/Errors/Duration), golden signals (latency/traffic/errors/saturation), SLO, SLI, error budget.
7. When referring to data you don't have, say "I can fetch that — try: list dashboards" so the user knows how to trigger the tool.

Style:
- Lead with the answer, not the preamble.
- No apologies ("I'm sorry…"). Just answer or redirect.
- No filler ("That's a great question!"). Just answer.
- Max 120 words unless the user explicitly asks for detail.

You have these MCP tools available (the user can invoke them by asking naturally):
{tool_list}
"""


_TOOL_RESULT_SYSTEM = """You are O11yBot formatting a tool call result for the user.

You just called the MCP tool `{tool_name}` and got back structured data.
Your job: present the data in a natural, concise way that directly answers the user's question.

Rules:
1. Start with a one-line summary ("Found N dashboards in M folders:")
2. Use markdown bullets · bold for names · italics for metadata · code fences for IDs/UIDs
3. Include clickable links where available: [Name](url)
4. Group by category when it aids scanning (e.g., by folder)
5. For lists > 5 items, show top 5 and mention "…and N more"
6. Never repeat the user's question back to them.
7. Never add preamble ("Here are the dashboards:"). Just show them.
8. DON'T make up data — only use what's in the tool result below.
9. Under 150 words. This is a reformatting task, not a report.

User asked: "{user_question}"
Tool result (JSON): {tool_result_json}
"""


_PROMQL_HELP_SYSTEM = """You are O11yBot helping write PromQL/LogQL/TraceQL queries.

Rules:
1. Answer with the query first, in a code fence with language tag.
2. One sentence of explanation MAX.
3. Show both basic and advanced versions if relevant.
4. For PromQL: use rate() for counters, histogram_quantile() for histograms, label_replace() sparingly.
5. For LogQL: use |= for text match, | json for structured, | logfmt for key=val, rate({...}[5m]) for metrics.
6. For TraceQL: {} selector syntax, duration filters, status=error.
7. Suggest the right datasource: Mimir for metrics, Loki for logs, Tempo for traces.
8. Never invent metric names — say "replace `my_metric` with your actual metric name".
"""


_INCIDENT_SYSTEM = """You are O11yBot investigating an incident.

Follow the RED + Golden Signals methodology. Think step-by-step:
1. Symptom: what is the user observing? (error rate, latency, specific alert)
2. Scope: which service/region/tenant is affected?
3. Timeframe: when did it start? correlate with deploys/config changes.
4. Golden Signals to check: latency (P50/P95/P99), traffic (RPS), errors (5xx), saturation (CPU/mem)
5. Likely causes (rank by probability)
6. Proposed next step (specific query or dashboard to open)

Output format:
- **Symptom:** <one line>
- **Scope:** <services + timeframe>
- **Hypothesis:** <ranked list with reasoning>
- **Next check:** <specific query in code fence>

Be concise. If you need more info, ask ONE specific question."""


# ─────────────────────────────────────────────────────────────
# Few-shot examples (prime the model)
# ─────────────────────────────────────────────────────────────
FEW_SHOT_EXAMPLES: dict[QueryType, list[dict[str, str]]] = {
    "observability_qa": [
        {
            "role": "user", "content": "what is the RED method?"
        },
        {
            "role": "assistant",
            "content": "**RED method** — for request-driven services:\n- **R**ate — requests per second\n- **E**rrors — failed requests per second\n- **D**uration — latency distribution (P50/P95/P99)\n\nComplements USE method (Utilization/Saturation/Errors) for resources. Use RED on every service dashboard."
        },
    ],
    "promql_help": [
        {
            "role": "user", "content": "promql for error rate by service"
        },
        {
            "role": "assistant",
            "content": "```promql\nsum(rate(http_requests_total{status=~\"5..\"}[5m])) by (service)\n/\nsum(rate(http_requests_total[5m])) by (service)\n```\n\nReplace `http_requests_total` with your actual counter metric."
        },
    ],
    "incident_analysis": [
        {
            "role": "user", "content": "payment service is slow"
        },
        {
            "role": "assistant",
            "content": "- **Symptom:** latency degradation, service=payment\n- **Scope:** need to confirm — what time range? all regions?\n- **Hypothesis (ranked):**\n  1. Recent deploy regression (check deploy timeline)\n  2. Upstream DB slow (check connection pool + slow queries)\n  3. Traffic spike → saturation (check RPS + CPU)\n- **Next check:** run this PromQL:\n```promql\nhistogram_quantile(0.95, sum(rate(http_duration_seconds_bucket{service=\"payment\"}[5m])) by (le))\n```"
        },
    ],
}


# ─────────────────────────────────────────────────────────────
# Query classifier
# ─────────────────────────────────────────────────────────────
def classify_query(user_message: str, has_tool_result: bool = False) -> QueryType:
    """Classify the user's query to pick the right prompt + sampling params."""
    if has_tool_result:
        return "tool_result_formatting"

    msg = user_message.lower().strip()

    # Short + greetings
    if len(msg) < 10 and any(w in msg for w in ["hi", "hello", "hey", "thanks", "thank you", "ok", "cool"]):
        return "chitchat"

    # PromQL / LogQL / TraceQL help
    if any(term in msg for term in [
        "promql", "logql", "traceql", "query", "metric", "syntax",
        "how to write", "how do i", "give me a", "show me a"
    ]):
        return "promql_help"

    # Incident analysis
    if any(term in msg for term in [
        "incident", "root cause", "rca", "debug", "why is", "why does",
        "slow", "error", "failing", "down", "broken", "investigate",
        "troubleshoot", "p99", "p95", "latency", "spike", "burn"
    ]):
        return "incident_analysis"

    # Default: general observability QA
    return "observability_qa"


# ─────────────────────────────────────────────────────────────
# Tool catalog for system prompt
# ─────────────────────────────────────────────────────────────
TOOL_CATALOG_SUMMARY = """- list_dashboards / search_dashboards / get_dashboard — browse dashboards
- list_datasources / query_datasource — explore datasources, run ad-hoc queries
- list_alert_rules / list_alert_instances / silence_alert — alerting
- list_folders — dashboard folders
- list_users (admin) — team members
- health_check / get_server_info — Grafana status"""


# ─────────────────────────────────────────────────────────────
# Main prompt builders
# ─────────────────────────────────────────────────────────────
def build_system_prompt(
    query_type: QueryType,
    user_name: str = "admin",
    user_role: str = "viewer",
    tool_name: str | None = None,
    tool_result: Any = None,
    user_question: str | None = None,
) -> str:
    """Build the system prompt for this query."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if query_type == "tool_result_formatting" and tool_name and user_question is not None:
        import json
        # Cap tool result JSON at 3K chars to avoid context bloat
        try:
            result_json = json.dumps(tool_result, indent=2, default=str)
        except Exception:
            result_json = str(tool_result)
        if len(result_json) > 3000:
            result_json = result_json[:3000] + "\n... (truncated)"
        return _TOOL_RESULT_SYSTEM.format(
            tool_name=tool_name,
            user_question=user_question,
            tool_result_json=result_json,
        )

    if query_type == "promql_help":
        return _PROMQL_HELP_SYSTEM

    if query_type == "incident_analysis":
        return _INCIDENT_SYSTEM

    # Default / observability_qa / chitchat
    return _BASE_SYSTEM.format(
        user_name=user_name,
        user_role=user_role,
        current_time=now,
        tool_list=TOOL_CATALOG_SUMMARY,
    )


def build_messages(
    query_type: QueryType,
    user_message: str,
    history: list[dict[str, str]] | None = None,
    user_name: str = "admin",
    user_role: str = "viewer",
    tool_name: str | None = None,
    tool_result: Any = None,
) -> list[dict[str, str]]:
    """Build the full messages array for the LLM."""
    system = build_system_prompt(
        query_type=query_type,
        user_name=user_name,
        user_role=user_role,
        tool_name=tool_name,
        tool_result=tool_result,
        user_question=user_message,
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    # Add few-shot examples (only for non-tool-result queries)
    if query_type != "tool_result_formatting":
        examples = FEW_SHOT_EXAMPLES.get(query_type, [])
        messages.extend(examples)

    # Recent history (keep last 6 turns max to stay in small-model context)
    if history:
        messages.extend(history[-6:])

    # Current user message
    messages.append({"role": "user", "content": user_message})

    return messages


def get_generation_config(query_type: QueryType) -> GenerationConfig:
    """Get tuned sampling params for this query type."""
    return GENERATION_PROFILES.get(query_type, GENERATION_PROFILES["observability_qa"])
