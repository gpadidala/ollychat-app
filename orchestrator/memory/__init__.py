"""Conversation memory — shared by v1 SSE widget + v2 WS canvas.

Keys:
  ollybot:convo:<user>:<org>   JSON list of last N turns, 1h TTL

A "turn" is a compact record of a completed assistant action, kept small
so it can be fed back into intent matching on the next turn:

    {
      "ts":       1712345678,
      "tool":     "create_smart_dashboard",
      "args":     {"title": "Mimir Read", "topic": "mimir read"},
      "result":   {"uid": "afj...", "url": "/d/afj.../mimir-read", "title": "Mimir Read"},
      "ok":       true,
    }

Read with `get_history()`, write with `record_turn()`. In-memory fallback
is automatic when Redis is unreachable — handy for tests + fresh local.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import structlog

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

logger = structlog.get_logger()

_TTL = int(os.environ.get("OLLYBOT_CONVO_TTL_SECONDS", "3600"))  # 1h
_MAX_TURNS = int(os.environ.get("OLLYBOT_CONVO_MAX_TURNS", "5"))


class _MemoryStore:
    def __init__(self) -> None:
        self._s: dict[str, str] = {}

    async def get(self, k: str) -> str | None:
        return self._s.get(k)

    async def setex(self, k: str, ttl: int, v: str) -> None:
        self._s[k] = v


class ConversationMemory:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or os.environ.get("OLLYCHAT_REDIS_URL", "redis://redis:6379/0")
        self._client: Any = None

    async def _connect(self) -> None:
        if self._client is not None:
            return
        if not _REDIS_AVAILABLE:
            self._client = _MemoryStore()
            logger.info("convo.memory.store", kind="in-memory")
            return
        try:
            c = aioredis.from_url(self._url, encoding="utf-8", decode_responses=True)
            await c.ping()
            self._client = c
            logger.info("convo.memory.store", kind="redis", url=self._url)
        except Exception as e:
            logger.warning("convo.memory.redis.unavailable", error=str(e))
            self._client = _MemoryStore()

    @staticmethod
    def _key(user: str, org: str) -> str:
        return f"ollybot:convo:{user}:{org}"

    async def get_history(self, user: str, org: str) -> list[dict[str, Any]]:
        await self._connect()
        raw = await self._client.get(self._key(user, org))
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    async def record_turn(
        self,
        user: str,
        org: str,
        tool: str,
        args: dict[str, Any],
        result: dict[str, Any],
        ok: bool,
    ) -> None:
        await self._connect()
        history = await self.get_history(user, org)
        # Keep the *useful* slice of result — dashboards get (uid, url, title);
        # other tools get a short textual message. We never persist full tool
        # payloads, which could be huge.
        compact_result = _compact_result(tool, result)
        history.append(
            {
                "ts": int(time.time()),
                "tool": tool,
                "args": _compact_args(args),
                "result": compact_result,
                "ok": bool(ok),
            }
        )
        history = history[-_MAX_TURNS:]
        await self._client.setex(self._key(user, org), _TTL, json.dumps(history))


def _compact_args(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (args or {}).items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)) and len(v) <= 20:
            out[k] = list(v)[:20]
    return out


def _compact_result(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    r = result or {}
    compact: dict[str, Any] = {}
    for k in ("uid", "url", "title", "version", "status", "dashboard_uid"):
        if k in r:
            compact[k] = r[k]
    msg = r.get("message") or r.get("content")
    if isinstance(msg, str):
        compact["message"] = msg[:400]
    return compact


_singleton: ConversationMemory | None = None


def get_memory() -> ConversationMemory:
    global _singleton
    if _singleton is None:
        _singleton = ConversationMemory()
    return _singleton
