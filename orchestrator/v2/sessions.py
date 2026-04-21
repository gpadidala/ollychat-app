"""Redis-backed session manager — ADR-0005.

Keys:
  ollybot:v2:session:<sid>   JSON blob, 24h TTL
  ollybot:v2:user:<uid>      set of session ids for fast multi-session lookup

All reads + writes go through this module so we can swap Redis for an
in-memory fallback in tests (set `OLLYBOT_SESSION_STORE=memory`).
"""
from __future__ import annotations

import os
from typing import Optional

import structlog

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

from .protocol import PendingApproval, SessionState

logger = structlog.get_logger()

_TTL = int(os.environ.get("OLLYBOT_SESSION_TTL_SECONDS", "86400"))   # 24h
_STORE_KIND = os.environ.get("OLLYBOT_SESSION_STORE", "redis")


class _MemoryStore:
    """Fallback for tests / local runs without Redis."""
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class SessionManager:
    """Async Redis (or in-memory) backed session store."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or os.environ.get("OLLYCHAT_REDIS_URL", "redis://redis:6379/0")
        self._client: aioredis.Redis | _MemoryStore | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        if _STORE_KIND == "memory" or not _REDIS_AVAILABLE:
            self._client = _MemoryStore()
            logger.info("sessions.store", kind="memory")
            return
        try:
            self._client = aioredis.from_url(self._url, decode_responses=True)
            await self._client.ping()
            logger.info("sessions.store", kind="redis", url=self._url)
        except Exception as e:
            logger.warning("sessions.redis-unreachable — falling back to memory",
                           url=self._url, error=str(e))
            self._client = _MemoryStore()

    async def _key(self, sid: str) -> str:
        return f"ollybot:v2:session:{sid}"

    async def create(self, user_id: str, role: str) -> SessionState:
        await self.connect()
        state = SessionState(user_id=user_id, role=role)
        await self._client.setex(await self._key(state.session_id), _TTL,
                                  state.model_dump_json())
        logger.info("session.created", session_id=state.session_id, user=user_id, role=role)
        return state

    async def get(self, sid: str) -> SessionState | None:
        await self.connect()
        raw = await self._client.get(await self._key(sid))
        if not raw:
            return None
        return SessionState.model_validate_json(raw)

    async def save(self, state: SessionState) -> None:
        await self.connect()
        await self._client.setex(await self._key(state.session_id), _TTL,
                                  state.model_dump_json())

    async def delete(self, sid: str) -> None:
        await self.connect()
        await self._client.delete(await self._key(sid))

    async def stash_pending(self, sid: str, pending: PendingApproval) -> None:
        state = await self.get(sid)
        if not state:
            raise KeyError(f"session {sid} not found")
        state.pending = pending
        await self.save(state)

    async def clear_pending(self, sid: str) -> PendingApproval | None:
        state = await self.get(sid)
        if not state or not state.pending:
            return None
        pending = state.pending
        state.pending = None
        await self.save(state)
        return pending


_singleton: SessionManager | None = None


def get_sessions() -> SessionManager:
    global _singleton
    if _singleton is None:
        _singleton = SessionManager()
    return _singleton
