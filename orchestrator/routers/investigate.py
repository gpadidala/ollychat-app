"""Investigation endpoint — multi-agent agentic loop with SSE progress streaming.

Adapted from o11y-sre-agent/agent/core/loop.py with hypothesis ranking
and postmortem generation.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from config import get_settings

logger = structlog.get_logger()
router = APIRouter()


# --- Hypothesis Patterns (from o11y-sre-agent) ---

HYPOTHESIS_PATTERNS = [
    {
        "pattern": "DeploymentRegression",
        "description": "A recent deployment introduced a regression",
        "signals": ["recent_changes", "error_logs", "slo_degradation"],
        "remediation": "Roll back the recent deployment",
        "rollback": "kubectl rollout undo deployment/<service>",
    },
    {
        "pattern": "OOMKilled",
        "description": "Pod killed due to memory exhaustion",
        "signals": ["oom_events", "memory_saturation"],
        "remediation": "Increase memory limits or fix memory leak",
    },
    {
        "pattern": "DependencyFailure",
        "description": "Upstream dependency is failing or slow",
        "signals": ["slow_traces", "connection_errors", "network_drops"],
        "remediation": "Check upstream service health; add circuit breaker",
    },
    {
        "pattern": "DatabaseConnectionExhaustion",
        "description": "Database connection pool is full",
        "signals": ["too_many_connections_logs", "pg_stat_activity_high"],
        "remediation": "Scale connection pooler (PgBouncer); identify long-running queries",
    },
    {
        "pattern": "CertificateExpiry",
        "description": "TLS certificate is expired or expiring",
        "signals": ["cert_expiry_metric", "tls_handshake_errors"],
        "remediation": "Renew the TLS certificate",
    },
    {
        "pattern": "NodeDiskPressure",
        "description": "Kubernetes node under disk pressure",
        "signals": ["disk_pressure_condition", "pod_eviction_events"],
        "remediation": "Clean up disk space; expand PVC",
    },
    {
        "pattern": "CascadingFailure",
        "description": "Multiple independent signals degraded simultaneously",
        "signals": ["multi_signal_degradation"],
        "remediation": "Isolate failing components; implement bulkheads",
    },
    {
        "pattern": "ConfigDrift",
        "description": "ConfigMap or Secret was recently changed",
        "signals": ["configmap_change", "secret_change"],
        "remediation": "Revert config change and investigate",
    },
    {
        "pattern": "DNSFailure",
        "description": "DNS resolution failures",
        "signals": ["dns_error_rate_high"],
        "remediation": "Check CoreDNS health; review DNS policies",
    },
]


class InvestigateRequest(BaseModel):
    question: str
    model: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    stream: bool = True


@router.post("/investigate")
async def investigate(body: InvestigateRequest):
    """Run multi-agent investigation with SSE progress streaming."""
    settings = get_settings()
    investigation_id = str(uuid.uuid4())
    model = body.model or settings.default_model

    logger.info("investigation.start", id=investigation_id, question=body.question[:200], model=model)

    async def event_generator():
        t0 = time.perf_counter()
        observations = []
        hypotheses = []

        try:
            # Step 1: Plan investigation
            yield {"data": json.dumps({"type": "progress", "message": "Planning investigation strategy..."})}

            # Step 2: Simulate multi-agent investigation
            # In production, this calls the LLM with tool definitions and runs the agentic loop.
            # For now, we demonstrate the streaming event protocol.

            investigation_steps = [
                ("Checking golden signals (latency, traffic, errors, saturation)", "metrics_agent"),
                ("Searching error logs for anomalies", "logs_agent"),
                ("Analyzing trace latency distribution", "traces_agent"),
                ("Checking recent deployments", "deployment_agent"),
                ("Querying pod health and resource usage", "infra_agent"),
            ]

            for step_msg, agent in investigation_steps:
                yield {"data": json.dumps({"type": "progress", "message": f"[{agent}] {step_msg}"})}

                # Simulate tool call
                yield {"data": json.dumps({
                    "type": "tool_call",
                    "tool": f"{agent}.query",
                    "args": {"question": body.question},
                })}

                # Simulate tool result
                obs = {
                    "tool": f"{agent}.query",
                    "args": {"question": body.question},
                    "result": f"Sample result from {agent}",
                    "ok": True,
                    "timestamp": time.time(),
                }
                observations.append(obs)

                yield {"data": json.dumps({
                    "type": "tool_result",
                    "tool": f"{agent}.query",
                    "result": obs["result"],
                    "duration_ms": 250,
                })}

            # Step 3: Generate hypotheses
            yield {"data": json.dumps({"type": "progress", "message": "Ranking hypotheses based on evidence..."})}

            for i, pattern in enumerate(HYPOTHESIS_PATTERNS[:3]):
                h = {
                    "rank": i + 1,
                    "pattern": pattern["pattern"],
                    "confidence": max(20, 90 - i * 25),
                    "evidence": [f"Evidence from {s}" for s in pattern["signals"][:2]],
                    "impact": pattern["description"],
                    "remediation": pattern.get("remediation"),
                    "rollback": pattern.get("rollback"),
                }
                hypotheses.append(h)
                yield {"data": json.dumps({"type": "hypothesis", **h})}

            # Step 4: Generate report
            yield {"data": json.dumps({"type": "progress", "message": "Generating investigation report..."})}

            report_md = f"""# Investigation Report

## Question
{body.question}

## Root Cause
{hypotheses[0]["pattern"]}: {hypotheses[0]["impact"]}

## Evidence
{chr(10).join(f"- {e}" for e in hypotheses[0]["evidence"])}

## Recommended Actions
1. {hypotheses[0].get("remediation", "Investigate further")}
2. Review recent deployment history
3. Set up monitoring alerts for this failure mode

## Observations
{chr(10).join(f"- [{o['tool']}] {o['result']}" for o in observations)}
"""

            duration_ms = int((time.perf_counter() - t0) * 1000)

            # Final result
            investigation = {
                "id": investigation_id,
                "question": body.question,
                "status": "complete",
                "trigger": "manual",
                "rootCause": f"{hypotheses[0]['pattern']}: {hypotheses[0]['impact']}",
                "confidence": hypotheses[0]["confidence"],
                "impact": hypotheses[0]["impact"],
                "affectedServices": body.context.get("services", ["unknown-service"]),
                "recommendedActions": [
                    hypotheses[0].get("remediation", "Investigate further"),
                    "Review recent deployment history",
                    "Set up monitoring alerts",
                ],
                "observations": observations,
                "hypotheses": hypotheses,
                "report": report_md,
                "createdAt": t0,
                "completedAt": time.time(),
                "costUsd": 0.05,
            }

            yield {"data": json.dumps({"type": "complete", "investigation": investigation})}

        except Exception as e:
            logger.error("investigation.failed", id=investigation_id, error=str(e))
            yield {"data": json.dumps({"type": "error", "message": str(e)})}

    return EventSourceResponse(event_generator())
