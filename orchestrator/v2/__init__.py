"""v2 — Interactive Reasoning Canvas.

Everything in this package is gated behind `OLLYBOT_INTERACTIVE_MODE=true`.
v1 routes at `/api/v1/*` and the existing SSE chat flow are untouched.

Structure:
  sessions.py       Redis-backed session manager (ADR-0005)
  stream.py         WebSocket endpoint /api/v2/stream
  actions.py        POST /api/v2/sessions/{sid}/action
  write_tools.py    Taxonomy of tools that require approval
  canvas.py         GET /api/v2/canvas — minimal HTML demo page (ADR-0002)
"""
from __future__ import annotations

import os


def interactive_mode_enabled() -> bool:
    """Master feature flag. Default false — v1 behaviour preserved."""
    return os.environ.get("OLLYBOT_INTERACTIVE_MODE", "false").lower() == "true"
