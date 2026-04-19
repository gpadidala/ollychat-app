"""Lightweight async Grafana HTTP client with per-role auth.

One client per role; reused across tool calls via a simple pool.
"""
from __future__ import annotations

from typing import Any

import httpx
import structlog

from config import Settings, get_settings

logger = structlog.get_logger(__name__)


class GrafanaError(Exception):
    def __init__(self, status_code: int, message: str, path: str) -> None:
        self.status_code = status_code
        self.path = path
        super().__init__(f"Grafana API {status_code} on {path}: {message}")


class GrafanaClient:
    def __init__(self, settings: Settings, role: str) -> None:
        self.role = role
        token = settings.token_for_role(role)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=settings.grafana_url,
            timeout=settings.request_timeout_s,
            verify=settings.tls_verify,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, path: str, **kw: Any) -> Any:
        r = await self._client.request(method, path, **kw)
        if r.status_code >= 400:
            raise GrafanaError(r.status_code, r.text[:400], path)
        if not r.content:
            return None
        ct = r.headers.get("content-type", "")
        if "json" in ct:
            return r.json()
        return r.text

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, body: dict[str, Any]) -> Any:
        return await self.request("POST", path, json=body)

    async def put(self, path: str, body: dict[str, Any]) -> Any:
        return await self.request("PUT", path, json=body)

    async def delete(self, path: str) -> Any:
        return await self.request("DELETE", path)


_clients: dict[str, GrafanaClient] = {}


def client_for(role: str) -> GrafanaClient:
    """Return a cached client for the given role."""
    if role not in _clients:
        _clients[role] = GrafanaClient(get_settings(), role)
    return _clients[role]


async def close_all() -> None:
    for c in _clients.values():
        await c.aclose()
    _clients.clear()
