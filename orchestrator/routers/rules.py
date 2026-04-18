"""Rules CRUD endpoints — behavioral guidelines applied to every conversation."""
from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = structlog.get_logger()
router = APIRouter()

# In-memory store
_rules: dict[str, dict[str, Any]] = {}

# Pre-loaded default rules
_DEFAULT_RULES = [
    {
        "id": "rule-env-context",
        "name": "Environment Context",
        "content": """Our primary metrics datasource is Mimir (Prometheus-compatible).
Our logs are in Loki. Our traces are in Tempo.
When discussing CPU, use container_cpu_usage_seconds_total.
When discussing memory, use container_memory_working_set_bytes.
Our main namespaces are: production, staging, shared-services.
Our critical services are: api-gateway, payment-service, user-service, order-service.""",
        "scope": "everybody",
        "enabled": True,
        "applications": ["assistant", "investigation"],
    },
    {
        "id": "rule-response-format",
        "name": "Response Format",
        "content": """Be concise and direct. Limit responses to 300 words unless producing an investigation report.
Use bullet points for actionable recommendations.
Always include relevant metric names and thresholds.
When suggesting a query, include the full PromQL/LogQL/TraceQL.
If unsure, state uncertainty clearly rather than guessing.
Always mention the time range when referencing metrics.""",
        "scope": "everybody",
        "enabled": True,
        "applications": ["assistant"],
    },
    {
        "id": "rule-escalation",
        "name": "Incident Triggers",
        "content": """If API latency P99 exceeds 5 seconds for more than 5 minutes, recommend declaring a P2 incident.
If error rate exceeds 5% for any critical service, recommend declaring a P1 incident.
Always check the deployment timeline before suggesting code-level issues.
Suggest rollback only if a deployment occurred within the last 2 hours.
For database issues, always check connection pool metrics before blaming the application.""",
        "scope": "everybody",
        "enabled": True,
        "applications": ["assistant", "investigation"],
    },
]

for r in _DEFAULT_RULES:
    _rules[r["id"]] = r


class RuleRequest(BaseModel):
    name: str
    content: str
    scope: str = "just-me"
    enabled: bool = True
    applications: list[str] = Field(default_factory=lambda: ["assistant"])


@router.get("/rules")
async def list_rules():
    return {"rules": list(_rules.values())}


@router.post("/rules")
async def create_rule(body: RuleRequest):
    rule_id = f"rule-{uuid.uuid4().hex[:8]}"
    rule = {"id": rule_id, **body.model_dump()}
    _rules[rule_id] = rule
    logger.info("rule.created", id=rule_id, name=body.name)
    return {"ok": True, "rule": rule}


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, body: RuleRequest):
    if rule_id not in _rules:
        return {"ok": False, "error": "Rule not found"}
    _rules[rule_id].update(body.model_dump())
    return {"ok": True, "rule": _rules[rule_id]}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    _rules.pop(rule_id, None)
    return {"ok": True}


def get_active_rules(application: str = "assistant") -> list[dict[str, Any]]:
    """Get all enabled rules for a given application context."""
    return [
        r for r in _rules.values()
        if r["enabled"] and application in r.get("applications", [])
    ]
