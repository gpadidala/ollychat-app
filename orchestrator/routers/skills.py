"""Skills CRUD endpoints — in-memory store for Phase 1, PostgreSQL for production."""
from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = structlog.get_logger()
router = APIRouter()

# In-memory store (replaced with PostgreSQL in Phase 6)
_skills: dict[str, dict[str, Any]] = {}

# Pre-loaded default skills
_DEFAULT_SKILLS = [
    {
        "id": "skill-triage",
        "name": "Incident Triage Runbook",
        "description": "Standard triage procedure for production incidents using golden signals",
        "category": "incident-triage",
        "systemPrompt": """Follow this investigation procedure:
1. Check golden signals: latency (P50/P95/P99), traffic (RPS), errors (5xx rate), saturation (CPU/memory)
2. Search error logs correlated with incident timeframe
3. Review trace latency distribution for slow spans
4. Check recent deployments in the last 4 hours
5. Check for related alerts and incidents

Always provide specific PromQL/LogQL/TraceQL queries with your findings.
Use the RED method (Rate, Errors, Duration) for service analysis.""",
        "toolWhitelist": ["query_prometheus", "search_logs", "search_traces"],
        "modelPreference": "claude-sonnet-4-6",
        "slashCommand": "triage",
        "tags": ["incident", "triage", "golden-signals", "RED"],
        "visibility": "everybody",
        "createdBy": "system",
        "createdAt": time.time(),
        "updatedAt": time.time(),
    },
    {
        "id": "skill-db-health",
        "name": "Database Health Check",
        "description": "Diagnose database connection pool exhaustion and performance issues",
        "category": "database",
        "systemPrompt": """Investigate database health:
1. Check pg_stat_activity_count for connection pool usage
2. Look for connection timeout errors in logs
3. Query pg_locks for blocking queries
4. Check pod restart counts for DB-dependent services
5. Review pg_stat_statements for slow queries

Remediation:
- Connection pool full: Scale PgBouncer replicas
- Blocking query: Identify and escalate to DBA
- Recent deploy: Check if schema migration caused issues""",
        "toolWhitelist": ["query_prometheus", "search_logs"],
        "slashCommand": "check-db",
        "tags": ["database", "postgres", "connection-pool"],
        "visibility": "everybody",
        "createdBy": "system",
        "createdAt": time.time(),
        "updatedAt": time.time(),
    },
    {
        "id": "skill-capacity",
        "name": "Capacity Planning Analysis",
        "description": "Analyze resource utilization trends and forecast capacity needs",
        "category": "infrastructure",
        "systemPrompt": """Perform capacity analysis:
1. Check CPU/memory utilization trends over the last 7 days
2. Identify top resource consumers by namespace/service
3. Compare current usage against resource requests/limits
4. Project growth rate based on historical trends
5. Identify right-sizing opportunities

Provide specific recommendations with projected dates for capacity limits.""",
        "toolWhitelist": ["query_prometheus"],
        "slashCommand": "capacity",
        "tags": ["capacity", "infrastructure", "planning"],
        "visibility": "everybody",
        "createdBy": "system",
        "createdAt": time.time(),
        "updatedAt": time.time(),
    },
]

# Initialize with defaults
for s in _DEFAULT_SKILLS:
    _skills[s["id"]] = s


class SkillRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    systemPrompt: str = ""
    toolWhitelist: list[str] = Field(default_factory=list)
    modelPreference: str | None = None
    slashCommand: str | None = None
    tags: list[str] = Field(default_factory=list)
    visibility: str = "just-me"


@router.get("/skills")
async def list_skills():
    return {"skills": list(_skills.values())}


@router.post("/skills")
async def create_skill(body: SkillRequest):
    skill_id = f"skill-{uuid.uuid4().hex[:8]}"
    skill = {
        "id": skill_id,
        **body.model_dump(),
        "createdBy": "user",
        "createdAt": time.time(),
        "updatedAt": time.time(),
    }
    _skills[skill_id] = skill
    logger.info("skill.created", id=skill_id, name=body.name)
    return {"ok": True, "skill": skill}


@router.put("/skills/{skill_id}")
async def update_skill(skill_id: str, body: SkillRequest):
    if skill_id not in _skills:
        return {"ok": False, "error": "Skill not found"}
    _skills[skill_id].update({**body.model_dump(), "updatedAt": time.time()})
    return {"ok": True, "skill": _skills[skill_id]}


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str):
    _skills.pop(skill_id, None)
    return {"ok": True}


@router.get("/skills/search")
async def search_skills(q: str):
    """Simple keyword search (replaced with semantic search in production)."""
    q_lower = q.lower()
    results = [
        s for s in _skills.values()
        if q_lower in s["name"].lower()
        or q_lower in s["description"].lower()
        or any(q_lower in t.lower() for t in s.get("tags", []))
    ]
    return {"skills": results}
