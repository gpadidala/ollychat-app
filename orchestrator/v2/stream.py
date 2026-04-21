"""WebSocket endpoint — /api/v2/stream.

One WS per (user, conversation).  Client sends UserMessage / UserAction /
OpenArtifact / Heartbeat; server streams ReasoningEvent messages back.

Contract lives in packages/reasoning-protocol/. The FastAPI router just
wires sessions + intent matcher + approval gate + MCP together — all the
business logic is shared with v1.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from intents import execute_intent, match_intent

from .protocol import PendingApproval, ReasoningEvent
from .sessions import get_sessions
from .write_tools import is_write_tool

logger = structlog.get_logger()
router = APIRouter()


async def _send_event(
    ws: WebSocket,
    session_id: str,
    seq: int,
    event: str,
    title: str,
    *,
    summary: str = "",
    payload: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    requires_user_action: bool = False,
    human_action_options: list[str] | None = None,
    trace_id: str | None = None,
) -> None:
    msg = ReasoningEvent(
        event=event,                    # type: ignore[arg-type]
        session_id=session_id,
        trace_id=trace_id or uuid.uuid4().hex,
        seq=seq,
        title=title,
        summary=summary,
        payload=payload or {},
        duration_ms=duration_ms,
        requires_user_action=requires_user_action,
        human_action_options=human_action_options or [],
    )
    await ws.send_text(msg.to_json())


@router.websocket("/v2/stream")
async def stream(ws: WebSocket) -> None:
    # WebSocket-level auth: same X-Grafana-* headers as SSE chat, passed
    # as query string for WS handshake (WS doesn't easily carry custom hdrs
    # from browsers).
    user_id = ws.query_params.get("user") or "anonymous"
    role = (ws.query_params.get("role") or "Viewer").capitalize()

    await ws.accept()

    sessions = get_sessions()
    state = await sessions.create(user_id=user_id, role=role)
    logger.info("ws.connected", session_id=state.session_id, user=user_id, role=role)

    # Greet the client — it needs the session_id for all subsequent actions.
    await _send_event(
        ws, state.session_id, state.next_seq(), "info",
        title="Session ready",
        summary=f"Hi {user_id}! I'm O11yBot v2. What would you like to build?",
        payload={"user": user_id, "role": role},
    )
    await sessions.save(state)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await _send_event(ws, state.session_id, state.next_seq(),
                                  "error", title="Invalid JSON",
                                  summary=raw[:120])
                continue

            msg_type = msg.get("type")

            if msg_type == "heartbeat":
                # Client keepalive — no response needed beyond presence.
                continue

            if msg_type == "user_action":
                await _handle_action(ws, state.session_id, msg)
                continue

            if msg_type == "user_message":
                await _handle_user_message(ws, state.session_id, msg)
                continue

            await _send_event(ws, state.session_id, state.next_seq(),
                              "error", title="Unknown message type",
                              summary=str(msg_type))

    except WebSocketDisconnect:
        logger.info("ws.disconnected", session_id=state.session_id)
    except Exception as e:
        logger.error("ws.error", session_id=state.session_id, error=str(e))
        try:
            await ws.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
# Handlers
# ══════════════════════════════════════════════════════════════════

async def _handle_user_message(ws: WebSocket, sid: str, msg: dict[str, Any]) -> None:
    """Core reasoning loop: intent match → plan → (approval gate) → execute → stream."""
    sessions = get_sessions()
    state = await sessions.get(sid)
    if not state:
        await _send_event(ws, sid, 1, "error", title="Session expired",
                          summary="Reconnect to start a new session.")
        return

    content = (msg.get("content") or "").strip()
    if not content:
        return

    state.history.append({"role": "user", "content": content})
    trace_id = uuid.uuid4().hex

    t0 = time.perf_counter()
    intent = await match_intent(content)
    elapsed = int((time.perf_counter() - t0) * 1000)

    if not intent:
        # LLM fallthrough would live here. MVP: tell the user we don't
        # have a matching intent so they can rephrase.
        await _send_event(ws, sid, state.next_seq(), "info",
                          title="No matching tool intent",
                          summary=f"I didn't recognise a specific action in "
                                  f"\"{content[:80]}\". Try: `create an alerts "
                                  f"dashboard`, `list firing alerts`, etc.",
                          duration_ms=elapsed, trace_id=trace_id)
        await sessions.save(state)
        return

    tool = intent["tool"]

    # Always surface intent classification first.
    await _send_event(
        ws, sid, state.next_seq(), "intent_classified",
        title=f"Intent: {tool}",
        summary=intent.get("desc", ""),
        payload={"tool": tool, "arguments": intent["arguments"]},
        duration_ms=elapsed, trace_id=trace_id,
    )

    # READ tool — execute immediately, no approval gate.
    if not is_write_tool(tool):
        role = state.role.lower() if state.role.lower() in ("admin", "editor") else "viewer"
        t1 = time.perf_counter()
        result = await execute_intent(intent, role=role)
        ms = int((time.perf_counter() - t1) * 1000)
        if result.get("ok"):
            await _send_event(ws, sid, state.next_seq(), "action_committed",
                              title=f"{tool} → ok",
                              summary=result.get("content", "")[:600],
                              payload={"tool": tool, "duration_ms": ms},
                              duration_ms=ms, trace_id=trace_id)
        else:
            await _send_event(ws, sid, state.next_seq(), "error",
                              title=f"{tool} failed",
                              summary=result.get("error", "")[:400],
                              duration_ms=ms, trace_id=trace_id)
        await sessions.save(state)
        return

    # WRITE tool — stash + ask for approval.
    pending = PendingApproval(
        seq=state.seq + 1,    # the seq of the event we're about to emit
        trace_id=trace_id,
        tool=tool,
        arguments=dict(intent["arguments"]),
        summary=intent.get("desc", ""),
    )
    state.pending = pending
    await _send_event(
        ws, sid, state.next_seq(), "awaiting_approval",
        title=f"Approve: {tool}",
        summary=(intent.get("desc") or tool)
                + f"\n\nArguments:\n```json\n"
                + json.dumps(intent["arguments"], indent=2)[:800]
                + "\n```",
        payload={"tool": tool, "arguments": intent["arguments"]},
        requires_user_action=True,
        human_action_options=["apply", "discard"],
        duration_ms=elapsed, trace_id=trace_id,
    )
    await sessions.save(state)


async def _handle_action(ws: WebSocket, sid: str, msg: dict[str, Any]) -> None:
    sessions = get_sessions()
    state = await sessions.get(sid)
    if not state:
        await _send_event(ws, sid, 1, "error", title="Session expired",
                          summary="Reconnect to start a new session.")
        return

    verb = msg.get("verb")

    if verb == "discard":
        pending = await sessions.clear_pending(sid)
        await _send_event(ws, sid, state.seq + 1, "info",
                          title="Discarded",
                          summary=f"Dropped pending {pending.tool if pending else 'action'}.")
        return

    if verb == "stop":
        await _send_event(ws, sid, state.seq + 1, "info",
                          title="Stopped",
                          summary="Reasoning paused. Send a new message to continue.")
        return

    if verb == "apply":
        if not state.pending:
            await _send_event(ws, sid, state.seq + 1, "info",
                              title="Nothing to apply",
                              summary="There's no action waiting for approval.")
            return
        pending = state.pending

        # Rebuild an intent-shaped dict by looking up the canonical intent
        # for this tool — for MVP we reuse the original arguments and let
        # execute_intent route by tool name.
        from mcp.client import get_mcp_manager     # lazy — avoids import cycle
        role = state.role.lower() if state.role.lower() in ("admin", "editor") else "viewer"

        t1 = time.perf_counter()
        mgr = get_mcp_manager()
        result = await mgr.call_tool("bifrost-grafana", pending.tool,
                                     pending.arguments, role=role)
        ms = int((time.perf_counter() - t1) * 1000)

        # Clear the pending regardless of outcome.
        state.pending = None
        await sessions.save(state)

        if result.get("ok"):
            data = result.get("data") or {}
            await _send_event(ws, sid, state.next_seq(), "action_committed",
                              title=f"✅ Applied {pending.tool}",
                              summary=data.get("message", "")[:400]
                                      if isinstance(data, dict) else str(data)[:400],
                              payload={"tool": pending.tool, "result": data,
                                       "duration_ms": ms},
                              duration_ms=ms, trace_id=pending.trace_id)
        else:
            await _send_event(ws, sid, state.next_seq(), "error",
                              title=f"❌ {pending.tool} failed",
                              summary=(result.get("error") or "")[:400],
                              duration_ms=ms, trace_id=pending.trace_id)
        return

    await _send_event(ws, sid, state.seq + 1, "error",
                      title="Unknown action verb", summary=str(verb))
