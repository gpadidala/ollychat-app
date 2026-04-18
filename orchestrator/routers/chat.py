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
            spec = SUPPORTED_MODELS.get(model, {})
            provider = spec.get("provider", "anthropic")

            if provider == "anthropic":
                async for event in _stream_anthropic(model, body, settings):
                    if event.get("type") == "usage":
                        total_input_tokens = event.get("usage", {}).get("promptTokens", 0)
                        total_output_tokens = event.get("usage", {}).get("completionTokens", 0)
                    yield {"data": json.dumps(event)}

            elif provider == "openai":
                async for event in _stream_openai(model, body, settings):
                    if event.get("type") == "usage":
                        total_input_tokens = event.get("usage", {}).get("promptTokens", 0)
                        total_output_tokens = event.get("usage", {}).get("completionTokens", 0)
                    yield {"data": json.dumps(event)}

            elif provider == "ollama":
                async for event in _stream_ollama(model, body, settings):
                    yield {"data": json.dumps(event)}

            else:
                yield {"data": json.dumps({"type": "error", "message": f"Unsupported provider: {provider}"})}
                return

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


async def _stream_ollama(model: str, body: ChatRequest, settings):
    """Stream from Ollama local API."""
    messages = []
    if body.system:
        messages.append({"role": "system", "content": body.system})
    messages.extend([{"role": m.role, "content": m.content} for m in body.messages])

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": body.temperature,
                    "num_predict": body.max_tokens,
                },
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
