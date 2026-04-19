"""Team management — list / create / members."""
from __future__ import annotations

from grafana_client import client_for
from registry import tool


@tool()
async def list_teams(role: str = "viewer") -> list[dict]:
    """List all Grafana teams in the current organisation."""
    c = client_for(role)
    raw = await c.get("/api/teams/search?perpage=200") or {}
    teams = raw.get("teams") or []
    return [{
        "id": t.get("id", 0),
        "uid": t.get("uid", ""),
        "name": t.get("name", ""),
        "email": t.get("email", ""),
        "member_count": t.get("memberCount", 0),
    } for t in teams]


@tool()
async def create_team(
    name: str,
    email: str = "",
    role: str = "admin",
) -> dict:
    """Create a new team."""
    c = client_for(role)
    body = {"name": name, "email": email}
    raw = await c.post("/api/teams", body) or {}
    return {
        "ok": True,
        "team_id": raw.get("teamId", 0),
        "message": raw.get("message") or f"Team '{name}' created",
    }


@tool()
async def list_team_members(team_id: int, role: str = "viewer") -> list[dict]:
    """List members of a team by team_id."""
    c = client_for(role)
    raw = await c.get(f"/api/teams/{team_id}/members") or []
    return [{
        "userId": m.get("userId", 0),
        "email": m.get("email", ""),
        "login": m.get("login", ""),
        "name": m.get("name", ""),
        "permission": m.get("permission", 0),
    } for m in raw]


@tool()
async def add_team_member(
    team_id: int,
    user_id: int,
    role: str = "admin",
) -> dict:
    """Add a user to a team."""
    c = client_for(role)
    raw = await c.post(f"/api/teams/{team_id}/members", {"userId": user_id})
    return {"ok": True, "team_id": team_id, "user_id": user_id,
            "message": (raw or {}).get("message") or f"User {user_id} added to team {team_id}"}
