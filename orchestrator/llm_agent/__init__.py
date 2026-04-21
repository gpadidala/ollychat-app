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


def openai_tools_from_mcp() -> list[dict[str, Any]]:
    """OpenAI-compatible schema (also what Ollama's /v1 expects)."""
    anth = anthropic_tools_from_mcp()
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in anth
    ]


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


def _is_openai_available(settings) -> bool:
    return bool(getattr(settings, "openai_api_key", "") or os.environ.get("OPENAI_API_KEY"))


def _ollama_base(settings) -> str:
    return (
        os.environ.get("OLLYCHAT_OLLAMA_BASE_URL")
        or getattr(settings, "ollama_base_url", "")
        or "http://ollama:11434"
    ).rstrip("/")


def _pick_provider(settings) -> str:
    """anthropic | openai | ollama — priority order reflects quality.

    Users who dropped in a cloud key get cloud Sonnet/GPT-4 automatically.
    Everyone else stays local via Ollama's OpenAI-compatible /v1 endpoint
    with whichever tool-capable model they have pulled.
    """
    if _is_anthropic_available(settings):
        return "anthropic"
    if _is_openai_available(settings):
        return "openai"
    return "ollama"


# Ollama model families that support tool calling (per Ollama's own
# support matrix). Everything else — notably Gemma, Phi, and the 0.5b
# Qwen — will 400 when you hand it a `tools` array, so we steer around
# them and tell the user clearly.
_OLLAMA_TOOL_FAMILIES = (
    "llama3.1", "llama3.2", "llama3.3",
    "qwen2.5", "qwen2.5-coder",
    "mistral", "mistral-nemo", "mistral-small",
    "command-r", "command-r-plus",
    "hermes3", "firefunction",
)

# Preferred tool-capable models in (size-adjusted) quality order. For
# typical Docker-Desktop dev stacks (3-4 GB VM), the 1-2 GB models are
# the only ones that actually load without OOM — so they go first even
# though a bigger model would answer better. Override by explicitly
# setting OLLYCHAT_DEFAULT_MODEL on a host with more RAM.
_OLLAMA_TOOL_PREFERRED = [
    "qwen2.5:1.5b",   # ~1 GB — current baseline, verified working
    "qwen2.5:3b",     # ~2 GB — upgrade if RAM allows
    "llama3.2:3b",    # ~2 GB — alt
    "llama3.2",       # ~2 GB — older label, alt
    "qwen2.5:7b",     # ~5 GB — best quality, needs headroom
    "llama3.1:8b",    # ~5 GB
    "mistral-nemo",   # ~7 GB
]


def _model_supports_tools(name: str) -> bool:
    low = (name or "").lower()
    # Reject the 0.5b qwen — tiny, unreliable at structured output.
    if low.startswith("qwen2.5:0.5b"):
        return False
    return any(low.startswith(f) for f in _OLLAMA_TOOL_FAMILIES)


async def _first_pulled_tool_model(base_url: str) -> str | None:
    """Ask Ollama what's pulled, return the best tool-capable match."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{base_url}/api/tags")
            if r.status_code != 200:
                return None
            pulled = [m.get("name", "") for m in (r.json().get("models") or [])]
    except Exception:
        return None
    # First any preferred model that's present
    for want in _OLLAMA_TOOL_PREFERRED:
        for have in pulled:
            if have == want or have.startswith(want + ":"):
                return have
    # Otherwise any pulled model whose family supports tools
    for have in pulled:
        if _model_supports_tools(have):
            return have
    return None


def _pick_model(provider: str, requested: str) -> str:
    """Auto-upgrade the sad demo default to a real model for whichever
    provider we're using. Respects any explicit model the user picked.
    """
    if provider == "anthropic":
        if not requested or requested.startswith("qwen") or requested.startswith("llama") or ":" in requested:
            return "claude-sonnet-4-6"
        if requested.startswith(("claude", "sonnet")):
            return requested
        return "claude-sonnet-4-6"
    if provider == "openai":
        if not requested or requested.startswith(("qwen", "llama", "claude")) or ":" in requested:
            return "gpt-4o"
        return requested
    # ollama
    if requested and requested != "qwen2.5:0.5b":
        return requested
    return "llama3.2"  # verified present on the demo stack; swap in compose


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

    Dispatches to the best available provider:
      - Anthropic Claude when ANTHROPIC_API_KEY is set
      - OpenAI GPT when OPENAI_API_KEY is set
      - Local Ollama otherwise (OpenAI-compatible /v1 endpoint)

    All three paths emit the same widget-rendered events:
      {"type": "tool_start"|"tool_result"|"text"|"usage"|"done"|"error", ...}
    """
    provider = _pick_provider(settings)
    chosen = _pick_model(provider, model)

    if provider == "ollama":
        # Gemma / Phi / tiny-qwen don't support tool calling — swap for
        # the best pulled tool-capable model so the agent still works.
        base = _ollama_base(settings)
        if not _model_supports_tools(chosen):
            alt = await _first_pulled_tool_model(base)
            if alt:
                yield {
                    "type": "text",
                    "delta": (
                        f"_Note: `{chosen}` doesn't support tool calling in "
                        f"Ollama, so I'm using `{alt}` instead. Set "
                        f"OLLYCHAT_DEFAULT_MODEL to a tool-capable model "
                        f"(llama3.1 / llama3.2 / qwen2.5 / mistral-nemo) to "
                        f"silence this notice._\n\n"
                    ),
                }
                chosen = alt
            else:
                yield {
                    "type": "error",
                    "message": (
                        f"{chosen} doesn't support tool calling and no "
                        f"tool-capable model is pulled locally. Run: "
                        f"`docker exec ollychat-ollama ollama pull "
                        f"llama3.2` (or qwen2.5:7b) and try again."
                    ),
                }
                yield {"type": "done"}
                return
        async for ev in _run_openai_compat(
            base_url=f"{base}/v1",
            api_key="ollama",  # Ollama ignores the key but the SDK requires a non-empty string
            model=chosen,
            user_message=user_message,
            history=history,
            grafana_user=grafana_user,
            grafana_org=grafana_org,
            bifrost_role=bifrost_role,
            label="ollama",
        ):
            yield ev
        return

    if provider == "openai":
        async for ev in _run_openai_compat(
            base_url="https://api.openai.com/v1",
            api_key=settings.openai_api_key or os.environ.get("OPENAI_API_KEY", ""),
            model=chosen,
            user_message=user_message,
            history=history,
            grafana_user=grafana_user,
            grafana_org=grafana_org,
            bifrost_role=bifrost_role,
            label="openai",
        ):
            yield ev
        return

    # provider == "anthropic"
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        yield {"type": "error", "message": "anthropic SDK not installed"}
        yield {"type": "done"}
        return

    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
    )
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


async def _run_openai_compat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    user_message: str,
    history: list[dict[str, str]],
    grafana_user: str,
    grafana_org: str,
    bifrost_role: str,
    label: str,
) -> AsyncIterator[dict[str, Any]]:
    """OpenAI-shaped tool-calling loop. Works with:
      - OpenAI (api.openai.com/v1)
      - Ollama (http://ollama:11434/v1) — tool calling requires a capable
        model (llama3.1:8b / llama3.2 / qwen2.5:7b / mistral-nemo …).
        Small models like qwen2.5:0.5b will return text-only.
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        yield {"type": "error", "message": "openai SDK not installed"}
        yield {"type": "done"}
        return

    client = AsyncOpenAI(api_key=api_key or "local", base_url=base_url)
    tools = openai_tools_from_mcp()

    prior = await get_memory().get_history(grafana_user, grafana_org)
    memory_blurb = ""
    if prior:
        last = prior[-1]
        memory_blurb = (
            f"\n\nRecent context: the user last ran `{last.get('tool')}` "
            f"and it {'succeeded' if last.get('ok') else 'failed'}. "
            f"Result summary: {json.dumps((last.get('result') or {}))[:300]}"
        )

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT + memory_blurb}]
    for h in history[-12:]:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    mgr = get_mcp_manager()
    total_in = total_out = 0

    for step in range(MAX_AGENT_ITERATIONS):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=2048,
                temperature=0.1,
            )
        except Exception as e:
            logger.error("llm_agent.call_failed", error=str(e), model=model, provider=label)
            hint = ""
            if label == "ollama":
                hint = (
                    f" — is the model pulled? Try: "
                    f"`docker exec ollychat-ollama ollama pull {model}`"
                )
            yield {"type": "error", "message": f"LLM call failed via {label}: {e}{hint}"}
            yield {"type": "done"}
            return

        usage = getattr(resp, "usage", None)
        if usage:
            total_in += getattr(usage, "prompt_tokens", 0) or 0
            total_out += getattr(usage, "completion_tokens", 0) or 0

        choice = resp.choices[0] if resp.choices else None
        if not choice:
            break
        msg = choice.message
        text = msg.content or ""
        tool_calls = msg.tool_calls or []

        if text:
            for i in range(0, len(text), 40):
                yield {"type": "text", "delta": text[i:i + 40]}

        if not tool_calls:
            break

        # Record assistant turn with tool_calls
        messages.append(
            {
                "role": "assistant",
                "content": text or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            tname = tc.function.name
            try:
                targs = json.loads(tc.function.arguments or "{}")
            except Exception:
                targs = {}

            if tname in _DESTRUCTIVE and bifrost_role != "admin":
                err = f"refused: {tname} requires admin role (user is {bifrost_role})"
                yield {"type": "tool_result", "id": tc.id, "error": err, "durationMs": 0}
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": err})
                continue

            resolved = _resolve_qualified_tool(tname)
            if not resolved:
                err = f"unknown tool: {tname}"
                yield {"type": "tool_result", "id": tc.id, "error": err, "durationMs": 0}
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": err})
                continue
            server_name, qname = resolved

            yield {"type": "tool_start", "id": tc.id, "name": tname, "input": targs}

            t0 = time.perf_counter()
            try:
                raw = await mgr.call_tool(server_name, qname, targs, role=bifrost_role)
                ok = bool(raw.get("ok"))
                data = raw.get("data") or raw
            except Exception as e:
                ok = False
                data = {"error": str(e)}
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
            yield {"type": "tool_result", "id": tc.id, "result": result_payload, "durationMs": ms}

            tool_out = json.dumps(data)[:4000] if isinstance(data, (dict, list)) else str(data)[:4000]
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_out})

        if choice.finish_reason and choice.finish_reason != "tool_calls":
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
        "costUsd": 0,
    }
    yield {"type": "done"}
