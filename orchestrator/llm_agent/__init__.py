"""LLM tool-calling agent — the "smart path" for natural-language chat.

Regex intent matching still runs first for unambiguous commands ("list
dashboards"). When it returns None, we fall through to this module: the
user's message, the conversation history from memory, and every MCP tool
as an Anthropic `tools` schema are sent to Claude, which picks a tool,
emits arguments, and we loop (call → feed result → repeat) until Claude
returns a text-only final answer.

Events are streamed back through the same SSE format the widget already
understands, so nothing on the client changes.

Safety rails:
  - Hard cap on loop iterations (MAX_AGENT_ITERATIONS)
  - Destructive tools (delete_*) require the user's role to be 'admin'
    even if Claude proposes them
  - Every tool call is logged with duration + outcome
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, AsyncIterator

import structlog

from mcp.client import get_mcp_manager
from memory import get_memory

logger = structlog.get_logger()

MAX_AGENT_ITERATIONS = int(os.environ.get("OLLYBOT_AGENT_MAX_ITERS", "8"))
# Tools that mutate state we refuse to call without an Admin role.
_DESTRUCTIVE = frozenset({
    "delete_dashboard", "delete_folder", "delete_alert_rule", "delete_silence",
    "delete_annotation", "delete_team",
})

SYSTEM_PROMPT = (
    "You are O11yBot, the live operator for a Grafana LGTM stack. The user "
    "is in the Grafana UI; the bot runs behind the scenes and calls tools "
    "on their behalf.\n\n"
    "Rules:\n"
    "1. Prefer ACTION over advice. If the user says 'create a dashboard for "
    "X', call create_smart_dashboard — don't describe what it would do.\n"
    "2. Chain tools when it helps: create, then diagnose, then fix; list "
    "to discover, then get_dashboard for detail.\n"
    "3. If a write fails because of RBAC, surface the error plainly. "
    "Don't retry destructive ops silently.\n"
    "4. When a tool returns a dashboard URL, mention it in your answer so "
    "the UI can auto-open it. Keep responses short — one or two sentences, "
    "plus any numbers/links the user needs.\n"
    "5. Respect the approval policy surfaced in tool descriptions. Never "
    "call delete_* on anything the user didn't explicitly name.\n"
)


def anthropic_tools_from_mcp() -> list[dict[str, Any]]:
    """Convert MCP tool list → Anthropic `tools` schema.

    Anthropic expects {name, description, input_schema}. MCP exposes
    `<server>__<tool>` fully-qualified names; we strip the server prefix
    so Claude sees canonical tool names ("list_dashboards" not
    "bifrost-grafana__list_dashboards"), and map back at call time.
    """
    mgr = get_mcp_manager()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for t in mgr.list_tools():
        qname = t["name"]
        # "bifrost-grafana__list_dashboards" → "list_dashboards"
        short = qname.split("__", 1)[-1]
        if short in seen:
            continue
        seen.add(short)
        schema = t.get("inputSchema") or {"type": "object", "properties": {}}
        if "type" not in schema:
            schema = {**schema, "type": "object"}
        out.append(
            {
                "name": short,
                "description": (t.get("description") or "")[:1024],
                "input_schema": schema,
            }
        )
    return out


def _resolve_qualified_tool(short_name: str) -> tuple[str, str] | None:
    """Map the short tool name Claude picked back to (server_name, qname)."""
    mgr = get_mcp_manager()
    for td in mgr.tools.values():
        if td.name.endswith(f"__{short_name}") or td.name == short_name:
            return td.server_name, td.name
    # Fallback: first tool with matching short name
    for td in mgr.tools.values():
        if td.name.split("__", 1)[-1] == short_name:
            return td.server_name, td.name
    return None


def _is_anthropic_available(settings) -> bool:
    return bool(getattr(settings, "anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY"))


def _pick_best_anthropic_model(requested: str) -> str:
    """Default to Sonnet 4.6 when the user didn't pick anything meaningful.

    The ollama 0.5b default is hardcoded in compose; upgrade it here rather
    than forcing the user to edit config when they do have an API key.
    """
    if not requested or requested.startswith("qwen") or ":" in requested:
        return "claude-sonnet-4-6"
    if requested.startswith("claude") or requested.startswith("sonnet"):
        return requested
    # Everything else (e.g. gpt-*) passes through; the caller already
    # validated that Anthropic is selected.
    return requested


async def run_agent(
    *,
    user_message: str,
    history: list[dict[str, str]],
    grafana_user: str,
    grafana_org: str,
    bifrost_role: str,
    model: str,
    settings,
) -> AsyncIterator[dict[str, Any]]:
    """Stream SSE events for a full agentic turn.

    Yields dicts shaped like the v1 SSE events so the existing widget
    keeps rendering without changes:
      {"type": "tool_start", "name": ..., "input": {...}}
      {"type": "tool_result", "result": {...}, "durationMs": ...}
      {"type": "text", "delta": "..."}
      {"type": "usage", "usage": {...}, "costUsd": 0}
      {"type": "done"}
      {"type": "error", "message": "..."}
    """
    if not _is_anthropic_available(settings):
        yield {
            "type": "error",
            "message": (
                "LLM agent requested but no ANTHROPIC_API_KEY is set. "
                "Add it to .env and restart the orchestrator, or disable "
                "OLLYBOT_LLM_AGENT to stay on the regex fast-path."
            ),
        }
        yield {"type": "done"}
        return

    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        yield {"type": "error", "message": "anthropic SDK not installed"}
        yield {"type": "done"}
        return

    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
    )
    chosen = _pick_best_anthropic_model(model)
    tools = anthropic_tools_from_mcp()

    # Build running message list. Prior memory turns become short system
    # context so Claude knows what the user was just doing.
    prior = await get_memory().get_history(grafana_user, grafana_org)
    memory_blurb = ""
    if prior:
        last = prior[-1]
        memory_blurb = (
            f"\n\nRecent context: the user last ran `{last.get('tool')}` "
            f"and it {'succeeded' if last.get('ok') else 'failed'}. "
            f"Result summary: {json.dumps((last.get('result') or {}))[:300]}"
        )

    messages: list[dict[str, Any]] = []
    for h in history[-12:]:  # keep last 12 turns
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    mgr = get_mcp_manager()
    total_in = 0
    total_out = 0

    for step in range(MAX_AGENT_ITERATIONS):
        try:
            resp = await client.messages.create(
                model=chosen,
                max_tokens=2048,
                system=SYSTEM_PROMPT + memory_blurb,
                tools=tools,
                messages=messages,
            )
        except Exception as e:
            logger.error("llm_agent.anthropic.call_failed", error=str(e), model=chosen)
            yield {"type": "error", "message": f"LLM call failed: {e}"}
            yield {"type": "done"}
            return

        usage = getattr(resp, "usage", None)
        if usage:
            total_in += getattr(usage, "input_tokens", 0) or 0
            total_out += getattr(usage, "output_tokens", 0) or 0

        tool_uses: list[dict[str, Any]] = []
        text_accum = ""
        for block in resp.content or []:
            btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
            if btype == "text":
                txt = getattr(block, "text", "") or (block.get("text", "") if isinstance(block, dict) else "")
                if txt:
                    # Stream tokens in chunks so the widget feels live
                    for i in range(0, len(txt), 40):
                        yield {"type": "text", "delta": txt[i:i + 40]}
                    text_accum += txt
            elif btype == "tool_use":
                tool_uses.append(
                    {
                        "id": getattr(block, "id", None) or block.get("id"),
                        "name": getattr(block, "name", None) or block.get("name"),
                        "input": getattr(block, "input", None) or block.get("input") or {},
                    }
                )

        stop_reason = getattr(resp, "stop_reason", None) or ""

        # No tools invoked this turn — the agent is done.
        if not tool_uses:
            break

        # Record the assistant's intent (tool_use blocks) so the next
        # Claude call knows what it already decided.
        messages.append({"role": "assistant", "content": resp.content})

        tool_results_blocks: list[dict[str, Any]] = []
        for tu in tool_uses:
            tname = tu["name"]
            targs = tu["input"] or {}

            # Safety: never call delete_* unless user is admin
            if tname in _DESTRUCTIVE and bifrost_role != "admin":
                err = f"refused: {tname} requires admin role (user is {bifrost_role})"
                yield {"type": "tool_result", "id": tu["id"], "error": err, "durationMs": 0}
                tool_results_blocks.append(
                    {"type": "tool_result", "tool_use_id": tu["id"], "content": err, "is_error": True}
                )
                continue

            resolved = _resolve_qualified_tool(tname)
            if not resolved:
                err = f"unknown tool: {tname}"
                yield {"type": "tool_result", "id": tu["id"], "error": err, "durationMs": 0}
                tool_results_blocks.append(
                    {"type": "tool_result", "tool_use_id": tu["id"], "content": err, "is_error": True}
                )
                continue
            server_name, qname = resolved

            yield {"type": "tool_start", "id": tu["id"], "name": tname, "input": targs}

            t0 = time.perf_counter()
            try:
                raw = await mgr.call_tool(server_name, qname, targs, role=bifrost_role)
                ok = bool(raw.get("ok"))
                data = raw.get("data") or raw
            except Exception as e:
                ok = False
                data = {"error": str(e)}
                raw = {"ok": False, "error": str(e)}
            ms = int((time.perf_counter() - t0) * 1000)

            try:
                await get_memory().record_turn(
                    grafana_user, grafana_org,
                    tool=tname, args=targs,
                    result=data if isinstance(data, dict) else {"value": data},
                    ok=ok,
                )
            except Exception as e:
                logger.warning("llm_agent.memory.write_failed", error=str(e))

            result_payload = {"ok": ok, **(data if isinstance(data, dict) else {"value": data})}
            yield {"type": "tool_result", "id": tu["id"], "result": result_payload, "durationMs": ms}

            tool_results_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": json.dumps(data)[:4000] if isinstance(data, (dict, list)) else str(data)[:4000],
                    "is_error": not ok,
                }
            )

        messages.append({"role": "user", "content": tool_results_blocks})

        if stop_reason != "tool_use":
            break
    else:
        yield {
            "type": "text",
            "delta": f"\n\n(stopped after {MAX_AGENT_ITERATIONS} tool calls — agent may be stuck in a loop)",
        }

    yield {
        "type": "usage",
        "usage": {
            "promptTokens": total_in,
            "completionTokens": total_out,
            "totalTokens": total_in + total_out,
        },
        "costUsd": 0,  # TODO: populate from cost table if/when we add one
    }
    yield {"type": "done"}


def agent_enabled() -> bool:
    return os.environ.get("OLLYBOT_LLM_AGENT", "").lower() in ("true", "1", "yes", "on")
