"""Chat endpoint with SSE streaming — the primary API for the Grafana plugin.

Adapted from:
- Bifrost llm.ts streaming patterns
- o11y-sre-agent LLM router with fallback chains
- llm-o11y-platform OTEL instrumentation
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from config import get_settings
from intents import execute_intent, match_intent
from prompts import build_messages, classify_query, get_generation_config
from routers.models import SUPPORTED_MODELS

logger = structlog.get_logger()

router = APIRouter()


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = ""
    messages: list[ChatMessageIn]
    system: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.2
    top_p: float = 0.9
    stream: bool = True
    tools: list[dict[str, Any]] | None = None


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """Stream a chat completion via SSE.

    SSE events follow the LLMEvent protocol:
      data: {"type": "text", "delta": "..."}
      data: {"type": "tool_start", "id": "...", "name": "...", "input": {...}}
      data: {"type": "tool_result", "id": "...", "result": ..., "durationMs": 123}
      data: {"type": "usage", "usage": {...}, "costUsd": 0.0023}
      data: {"type": "done"}
      data: {"type": "error", "message": "..."}
    """
    settings = get_settings()
    model = body.model or settings.default_model
    request_id = str(uuid.uuid4())

    # Extract Grafana user context from headers
    grafana_user = request.headers.get("X-Grafana-User", "anonymous")
    grafana_org = request.headers.get("X-Grafana-Org-Id", "1")
    # RBAC: map Grafana role to Bifrost role (viewer/editor/admin)
    grafana_role_raw = request.headers.get("X-Grafana-Role", "Viewer").lower()
    # Normalize: "Admin" → admin, "Editor" → editor, everything else → viewer
    if grafana_role_raw in ("admin", "grafana admin"):
        bifrost_role = "admin"
    elif grafana_role_raw == "editor":
        bifrost_role = "editor"
    else:
        bifrost_role = "viewer"

    logger.info(
        "chat_request",
        request_id=request_id,
        model=model,
        message_count=len(body.messages),
        user=grafana_user,
        org=grafana_org,
    )

    async def event_generator():
        t0 = time.perf_counter()
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            # ── Intent matching: intercept MCP-related queries ──
            # This gives reliable tool calling even for small LLMs.
            last_user_msg = ""
            for m in reversed(body.messages):
                if m.role == "user":
                    last_user_msg = m.content
                    break

            intent = await match_intent(last_user_msg) if last_user_msg else None

            # Build conversation history (exclude current message, keep recent)
            history = [
                {"role": m.role, "content": m.content}
                for m in body.messages[:-1]  # excl. last user message
            ]

            if intent:
                logger.info("intent.matched", tool=intent["tool"], user_msg=last_user_msg[:100])

                # Emit tool_start event
                yield {"data": json.dumps({
                    "type": "tool_start",
                    "id": request_id,
                    "name": intent["tool"],
                    "input": intent["arguments"],
                })}

                # Execute the intent with Grafana RBAC enforcement
                result = await execute_intent(intent, role=bifrost_role)

                if result["ok"]:
                    yield {"data": json.dumps({
                        "type": "tool_result",
                        "id": request_id,
                        "result": {"ok": True},
                        "durationMs": result["duration_ms"],
                    })}

                    # ── OPTIONAL LLM post-processing ──
                    # For small queries with clean data, use the direct formatter.
                    # For rich queries, pass through LLM for natural language.
                    use_llm_format = _should_use_llm_formatting(intent, result, last_user_msg)

                    if use_llm_format:
                        # Feed raw tool data to LLM with formatting prompt
                        messages = build_messages(
                            query_type="tool_result_formatting",
                            user_message=last_user_msg,
                            user_name=grafana_user,
                            user_role="viewer",
                            tool_name=intent["tool"],
                            tool_result=result.get("raw_data", result["content"]),
                        )
                        cfg = get_generation_config("tool_result_formatting")
                        async for event in _call_llm(model, messages, cfg, settings):
                            if event.get("type") == "usage":
                                total_input_tokens = event.get("usage", {}).get("promptTokens", 0)
                                total_output_tokens = event.get("usage", {}).get("completionTokens", 0)
                            yield {"data": json.dumps(event)}
                    else:
                        # Fast path: stream the pre-formatted content
                        content = result["content"]
                        chunk_size = 40
                        for i in range(0, len(content), chunk_size):
                            yield {"data": json.dumps({"type": "text", "delta": content[i:i+chunk_size]})}

                    yield {"data": json.dumps({
                        "type": "usage",
                        "usage": {
                            "promptTokens": total_input_tokens,
                            "completionTokens": total_output_tokens,
                            "totalTokens": total_input_tokens + total_output_tokens,
                        },
                        "costUsd": _calculate_cost(model, total_input_tokens, total_output_tokens),
                    })}
                    yield {"data": json.dumps({"type": "done"})}
                    return
                else:
                    yield {"data": json.dumps({
                        "type": "tool_result",
                        "id": request_id,
                        "error": result["error"],
                        "durationMs": 0,
                    })}
                    err_text = f"**Tool call failed:** {result['error']}\n\nPlease try again or rephrase your question."
                    for i in range(0, len(err_text), 40):
                        yield {"data": json.dumps({"type": "text", "delta": err_text[i:i+40]})}
                    yield {"data": json.dumps({"type": "done"})}
                    return

            # ═══════════════════════════════════════════════
            # No intent matched — use LLM with prompt engineering
            # ═══════════════════════════════════════════════
            query_type = classify_query(last_user_msg)
            logger.info("query.classified", type=query_type, user_msg=last_user_msg[:100])

            messages = build_messages(
                query_type=query_type,
                user_message=last_user_msg,
                history=history,
                user_name=grafana_user,
                user_role="viewer",
            )
            cfg = get_generation_config(query_type)

            async for event in _call_llm(model, messages, cfg, settings):
                if event.get("type") == "usage":
                    total_input_tokens = event.get("usage", {}).get("promptTokens", 0)
                    total_output_tokens = event.get("usage", {}).get("completionTokens", 0)
                yield {"data": json.dumps(event)}

            # Emit final usage + cost
            cost = _calculate_cost(model, total_input_tokens, total_output_tokens)
            yield {"data": json.dumps({
                "type": "usage",
                "usage": {
                    "promptTokens": total_input_tokens,
                    "completionTokens": total_output_tokens,
                    "totalTokens": total_input_tokens + total_output_tokens,
                },
                "costUsd": cost,
            })}

            yield {"data": json.dumps({"type": "done"})}

        except Exception as e:
            logger.error("chat_stream_error", request_id=request_id, error=str(e))
            yield {"data": json.dumps({"type": "error", "message": str(e)})}

        finally:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                "chat_complete",
                request_id=request_id,
                model=model,
                duration_ms=duration_ms,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

    return EventSourceResponse(event_generator())


# ═══════════════════════════════════════════════════════════════
# Prompt-engineered LLM dispatcher
# ═══════════════════════════════════════════════════════════════

def _should_use_llm_formatting(intent: dict, result: dict, user_msg: str) -> bool:
    """Decide whether to pass tool results through LLM for natural formatting.

    Use LLM when:
    - The query is nuanced ("what's firing in prod?") rather than exact ("list alerts")
    - The tool returned a lot of data that needs summarization
    - The user phrased it conversationally

    Skip LLM when:
    - Query is a direct imperative ("list all dashboards")
    - Result is a simple list < 20 items
    - User likely wants the full structured list
    """
    # Simple heuristic: if the user query is > 50 chars or contains analytical words,
    # post-process with LLM. Otherwise use the fast path.
    msg_lower = user_msg.lower()
    analytical_words = [
        "why", "what's", "analyze", "explain", "summarize", "summary",
        "tell me about", "how many", "which", "health of",
    ]
    is_analytical = any(w in msg_lower for w in analytical_words)

    raw = result.get("raw_data")
    data_is_large = isinstance(raw, (list, dict)) and len(str(raw)) > 5000

    # For dev with tiny local LLM, skip LLM formatting to avoid slow/weird output
    # Re-enable this when using gpt-4o or claude-sonnet-4-6 in prod
    return False  # TODO: flip to `is_analytical or data_is_large` in prod


async def _call_llm(model: str, messages: list, cfg, settings):
    """Unified LLM call using prompt-engineered messages + tuned config.

    Routes to the correct provider based on model prefix.
    """
    spec = SUPPORTED_MODELS.get(model, {})
    provider = spec.get("provider", "ollama")

    # Build a minimal body using the config
    class _Body:
        pass
    b = _Body()
    b.system = None  # system is already in messages[0]
    b.max_tokens = cfg.max_tokens
    b.temperature = cfg.temperature
    # Convert dict messages to ChatMessageIn-like objects
    b.messages = [ChatMessageIn(role=m["role"], content=m["content"]) for m in messages]

    if provider == "anthropic":
        # Anthropic requires system separate from messages
        sys_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        b.system = sys_msg
        b.messages = [ChatMessageIn(role=m["role"], content=m["content"]) for m in messages if m["role"] != "system"]
        async for event in _stream_anthropic(model, b, settings):
            yield event
    elif provider == "openai":
        async for event in _stream_openai(model, b, settings):
            yield event
    elif provider == "ollama":
        async for event in _stream_ollama(model, b, settings, config=cfg):
            yield event
    else:
        yield {"type": "error", "message": f"Unsupported provider: {provider}"}


# --- Provider Implementations ---

async def _stream_anthropic(model: str, body: ChatRequest, settings):
    """Stream from Anthropic Messages API."""
    if not settings.anthropic_api_key:
        yield {"type": "error", "message": "Anthropic API key not configured"}
        return

    messages = [{"role": m.role, "content": m.content} for m in body.messages if m.role != "system"]

    request_body = {
        "model": model,
        "messages": messages,
        "max_tokens": body.max_tokens,
        "temperature": body.temperature,
        "stream": True,
    }
    if body.system:
        request_body["system"] = body.system

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
            },
            json=request_body,
        ) as response:
            if response.status_code != 200:
                text = await response.aread()
                yield {"type": "error", "message": f"Anthropic {response.status_code}: {text.decode()[:400]}"}
                return

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    for line in frame.split("\n"):
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                continue
                            try:
                                evt = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            if evt.get("type") == "content_block_delta":
                                delta = evt.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield {"type": "text", "delta": delta.get("text", "")}

                            elif evt.get("type") == "message_delta":
                                usage = evt.get("usage", {})
                                if usage:
                                    yield {
                                        "type": "usage",
                                        "usage": {
                                            "promptTokens": usage.get("input_tokens", 0),
                                            "completionTokens": usage.get("output_tokens", 0),
                                            "totalTokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                                        },
                                        "costUsd": 0,
                                    }


async def _stream_openai(model: str, body: ChatRequest, settings):
    """Stream from OpenAI Chat Completions API."""
    if not settings.openai_api_key:
        yield {"type": "error", "message": "OpenAI API key not configured"}
        return

    messages = []
    if body.system:
        messages.append({"role": "system", "content": body.system})
    messages.extend([{"role": m.role, "content": m.content} for m in body.messages])

    request_body = {
        "model": model,
        "messages": messages,
        "max_tokens": body.max_tokens,
        "temperature": body.temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.openai_api_key}",
            },
            json=request_body,
        ) as response:
            if response.status_code != 200:
                text = await response.aread()
                yield {"type": "error", "message": f"OpenAI {response.status_code}: {text.decode()[:400]}"}
                return

            async for line in response.aiter_lines():
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue
                try:
                    evt = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choices = evt.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield {"type": "text", "delta": content}

                usage = evt.get("usage")
                if usage:
                    yield {
                        "type": "usage",
                        "usage": {
                            "promptTokens": usage.get("prompt_tokens", 0),
                            "completionTokens": usage.get("completion_tokens", 0),
                            "totalTokens": usage.get("total_tokens", 0),
                        },
                        "costUsd": 0,
                    }


async def _ensure_ollama_model(model: str, settings) -> str | None:
    """Check if model exists in Ollama; if not, pull it. Returns error or None."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            if r.status_code != 200:
                return f"Ollama not reachable: HTTP {r.status_code}"
            tags = r.json()
            installed = [m.get("name", "") for m in tags.get("models", [])]
            if model in installed or model.split(":")[0] in [n.split(":")[0] for n in installed]:
                return None  # already installed
    except Exception as e:
        return f"Ollama not reachable: {e}"

    # Pull the model
    logger.info("ollama.pulling_model", model=model)
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/pull",
                json={"name": model, "stream": False},
                timeout=600,
            )
            if r.status_code == 200:
                logger.info("ollama.model_pulled", model=model)
                return None
            return f"Failed to pull model: {r.text[:200]}"
    except Exception as e:
        return f"Failed to pull model: {e}"


async def _stream_ollama(model: str, body: ChatRequest, settings, config=None):
    """Stream from self-hosted Ollama. Auto-pulls the model if not present.

    Uses tuned sampling params from `config` (GenerationConfig) when provided,
    else falls back to body.temperature/max_tokens.
    """
    # Ensure model is available
    pull_error = await _ensure_ollama_model(model, settings)
    if pull_error:
        yield {"type": "error", "message": pull_error}
        return

    messages = []
    if body.system:
        messages.append({"role": "system", "content": body.system})
    messages.extend([{"role": m.role, "content": m.content} for m in body.messages])

    # Ollama sampling options — tuned per query type when config is provided
    if config:
        options = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "num_predict": config.max_tokens,
            # Anti-repetition (helps small models)
            "repeat_penalty": 1.15,
            "repeat_last_n": 64,
            # Stop tokens for cleaner output
            "stop": ["<|im_end|>", "<|endoftext|>"],
        }
    else:
        options = {
            "temperature": body.temperature,
            "top_p": 0.9,
            "num_predict": body.max_tokens,
            "repeat_penalty": 1.1,
        }

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": options,
            },
        ) as response:
            if response.status_code != 200:
                text = await response.aread()
                yield {"type": "error", "message": f"Ollama {response.status_code}: {text.decode()[:400]}"}
                return

            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = chunk.get("message", {}).get("content")
                if content:
                    yield {"type": "text", "delta": content}


def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD based on model pricing."""
    spec = SUPPORTED_MODELS.get(model)
    if not spec:
        return 0.0
    return (input_tokens / 1000) * spec["cost_per_1k_in"] + (output_tokens / 1000) * spec["cost_per_1k_out"]
