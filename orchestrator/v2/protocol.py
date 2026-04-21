"""Reasoning-event protocol — wire contract between the v2 canvas and orchestrator.

Every message emitted over the WebSocket MUST validate against one of the
schemas in this package. Client → server and server → client types live here
so there is exactly one source of truth.

Server → client : `ReasoningEvent`
Client → server : `UserMessage` | `UserAction` | `OpenArtifact` | `Heartbeat`

A companion `schema.json` is generated from these Pydantic models at build
time so a future TS client can codegen its types from the same source.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════
# Server → client
# ══════════════════════════════════════════════════════════════════

EventKind = Literal[
    "intent_classified",     # "You want to create a service-health dashboard for checkout-svc."
    "plan_proposed",         # "I'll build 6 panels: availability, RPS, latency…"
    "data_source_selected",  # "Using Prometheus (datasource: prom-prod) — metrics X, Y are present."
    "query_generated",       # Shows PromQL/LogQL/TraceQL with syntax highlighting.
    "panel_building",        # Fires as each panel is being placed on the canvas.
    "panel_ready",           # Panel written to the draft; canvas should refresh.
    "layout_resolved",       # "Arranged as 3×2 grid…"
    "validation_result",     # Dry-run + DS probe result.
    "awaiting_approval",     # Human-in-the-loop gate before any write.
    "action_committed",      # Actual Grafana write with returned UID/URL.
    "error",                 # Structured error — includes retryable? + next-step hint.
    "info",                  # Free-form narration (fallback).
]


class ReasoningEvent(BaseModel):
    """Every server→client message. Stable wire format."""

    type: Literal["reasoning_event"] = "reasoning_event"
    event: EventKind
    session_id: str
    trace_id: str
    seq: int                    # monotonic per session
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int | None = None
    title: str                  # one-liner for the timeline card
    summary: str = ""           # optional body — markdown OK
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_user_action: bool = False
    human_action_options: list[str] = Field(default_factory=list)  # ["apply","edit","discard"]

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=False)


# ══════════════════════════════════════════════════════════════════
# Client → server
# ══════════════════════════════════════════════════════════════════

ActionVerb = Literal["apply", "edit", "discard", "undo", "redo", "stop"]
ArtifactType = Literal["dashboard", "alert_rule", "panel"]


class UserMessage(BaseModel):
    """Natural-language input from the user."""
    type: Literal["user_message"] = "user_message"
    session_id: str
    content: str
    role: str = "Viewer"        # Grafana role — drives RBAC preflight


class UserAction(BaseModel):
    """Approval-gate response or control verb (apply / discard / undo / stop)."""
    type: Literal["user_action"] = "user_action"
    session_id: str
    verb: ActionVerb
    target_seq: int | None = None   # which event this action responds to


class OpenArtifact(BaseModel):
    """"Open dashboard/alert <uid>" action from the canvas."""
    type: Literal["open_artifact"] = "open_artifact"
    session_id: str
    artifact_type: ArtifactType
    uid: str


class Heartbeat(BaseModel):
    type: Literal["heartbeat"] = "heartbeat"
    session_id: str


# ══════════════════════════════════════════════════════════════════
# Session state (held in Redis)
# ══════════════════════════════════════════════════════════════════


class PendingApproval(BaseModel):
    """Write proposal waiting for an `apply` or `discard`."""
    seq: int                    # the seq of the awaiting_approval event
    trace_id: str
    tool: str                   # e.g. "create_smart_dashboard"
    arguments: dict[str, Any]
    summary: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionState(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    role: str                        # Viewer / Editor / Admin
    seq: int = 0                     # monotonically increasing event counter
    history: list[dict[str, Any]] = Field(default_factory=list)   # chat messages
    pending: PendingApproval | None = None
    draft_uid: str | None = None     # UID of the current [DRAFT] dashboard if any
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq


__all__ = [
    "EventKind",
    "ReasoningEvent",
    "ActionVerb",
    "ArtifactType",
    "UserMessage",
    "UserAction",
    "OpenArtifact",
    "Heartbeat",
    "PendingApproval",
    "SessionState",
]
