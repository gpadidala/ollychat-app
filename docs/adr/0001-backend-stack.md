# ADR-0001 — Backend stack for v2

- **Status:** Accepted (2026-04-20)
- **Context:** v2 master brief §4.2 asks us to match v1 unless v1 blocks WebSocket streaming. v1 audit §3.1 confirmed v1 is FastAPI + httpx + pydantic v2 + structlog + OpenTelemetry.

## Decision
Keep Python / FastAPI. Add:
- `websockets` (or `uvicorn[standard]` bundled `websockets`) for `/api/v2/stream`.
- `redis[hiredis]>=5.1` async client for session + snapshot store.
- `asyncpg>=0.30` for the append-only audit log.
- `tenacity>=9` for retries + exponential backoff on every outbound HTTP client.
- `pybreaker>=1.2` for circuit-breaker state machines per outbound target.

No new language runtime. The orchestrator image stays `python:3.12-slim`; the
Dockerfile already forwards the corporate-TLS build args so the new deps
install cleanly on locked-down laptops.

## Alternatives considered
- **Node.js (Fastify + `ws`)** — rejected. v1 is Python; the intent matcher
  (1714 LOC), MCP client, and PII scanner all live in Python. Rewriting them
  in TS to unify runtimes trades real cost for no behavioural gain.
- **gRPC instead of WebSocket** — rejected. The frontend is a Grafana app
  plugin; browsers can't speak gRPC natively and gRPC-Web adds a proxy layer.
  WebSocket is what `@grafana/runtime` already uses for Grafana Live.
- **Separate "reasoning service" microservice** — deferred. Single process
  keeps ops simple for MVP; we can split later if QPS demands it.

## Consequences
- `orchestrator/requirements.txt` gains 4 deps.
- New router tree under `orchestrator/routers/v2/` — v1 routes untouched.
- Compose gains a `redis` service (ADR-0005) and later a `postgres` service
  (ADR-0007).

## Backward-compat
All v1 routes under `/api/v1/*` keep exactly their current shape. The widget
continues talking SSE. v2 endpoints are under `/api/v2/*`; the feature flag
`OLLYBOT_INTERACTIVE_MODE` gates emission of new reasoning-event types.
