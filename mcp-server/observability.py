"""Self-observability — Prometheus metrics + structured audit log.

The MCP server exports its own metrics at /metrics so operators can
track tool-call volume, errors, and latency per role/tool combo.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

import structlog
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

_logger = structlog.get_logger("o11ybot-mcp.audit")

REGISTRY = CollectorRegistry()

TOOL_CALLS = Counter(
    "ollychat_mcp_tool_calls_total",
    "Total MCP tool calls",
    ["tool", "role", "status"],
    registry=REGISTRY,
)
TOOL_DURATION = Histogram(
    "ollychat_mcp_tool_duration_seconds",
    "Per-tool call latency",
    ["tool", "role"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)
GRAFANA_REQUESTS = Counter(
    "ollychat_mcp_grafana_requests_total",
    "Outbound requests to the Grafana HTTP API",
    ["method", "status_class"],
    registry=REGISTRY,
)


@contextmanager
def record_tool_call(tool: str, role: str):
    """Time a tool call and emit metrics + an audit log entry on exit."""
    t0 = time.perf_counter()
    status = "ok"
    error: str | None = None
    try:
        yield
    except PermissionError as e:
        status = "forbidden"
        error = str(e)
        raise
    except Exception as e:  # noqa: BLE001
        status = "error"
        error = e.__class__.__name__
        raise
    finally:
        elapsed = time.perf_counter() - t0
        TOOL_DURATION.labels(tool=tool, role=role).observe(elapsed)
        TOOL_CALLS.labels(tool=tool, role=role, status=status).inc()
        _logger.info(
            "tool.call",
            tool=tool,
            role=role,
            status=status,
            duration_ms=int(elapsed * 1000),
            error=error,
        )


def metrics_payload() -> tuple[bytes, str]:
    """Return (body, content-type) for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
