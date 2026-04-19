"""User + service-account admin tools."""
from __future__ import annotations

from grafana_client import client_for
from registry import tool


@tool()
async def list_users(role: str = "admin") -> list[dict]:
    """List all Grafana users in the organisation."""
    c = client_for(role)
    raw = await c.get("/api/org/users") or []
    return [{
        "id": u.get("userId") or u.get("id", 0),
        "login": u.get("login", ""),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "role": u.get("role", ""),
    } for u in raw]


@tool()
async def list_service_accounts(role: str = "admin") -> list[dict]:
    """List all Grafana service accounts."""
    c = client_for(role)
    raw = await c.get("/api/serviceaccounts/search?perpage=100")
    items = (raw or {}).get("serviceAccounts") or []
    return [{
        "id": s.get("id", 0),
        "name": s.get("name", ""),
        "login": s.get("login", ""),
        "role": s.get("role", ""),
        "is_disabled": s.get("isDisabled", False),
        "tokens": s.get("tokens", 0),
    } for s in items]
