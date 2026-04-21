# O11yBot Architecture

## System Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                    Browser (Grafana User)                          │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Grafana UI (http://localhost:3200)                          │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐   │ │
│  │  │  O11yBot Widget (floating overlay, ALL pages)        │   │ │
│  │  │                                                      │   │ │
│  │  │  States: FAB | Normal | Maximized | Fullscreen       │   │ │
│  │  │  Per-user localStorage: o11ybot-<username>           │   │ │
│  │  │  SSE parser: CRLF normalization                      │   │ │
│  │  └──────────────────┬───────────────────────────────────┘   │ │
│  └─────────────────────┼───────────────────────────────────────┘ │
│                        │                                          │
│                        │ POST /api/v1/chat (SSE)                 │
│                        │ Origin: localhost:3200                  │
│                        │ X-Grafana-User: admin                   │
└────────────────────────┼──────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│  Orchestrator (Python FastAPI, port 8000)                          │
│                                                                    │
│  Pipeline:                                                         │
│    1. CORS preflight ✓                                            │
│    2. Intent matcher → tries 12 patterns                           │
│       ┌──────────────────────────┐                                │
│       │  MATCH → Call MCP tool   │                                │
│       │  NO MATCH → Forward LLM  │                                │
│       └──────────────────────────┘                                │
│    3. Format result as markdown + stream as SSE                    │
│    4. Emit usage + done events                                    │
│                                                                    │
│  Routes:                                                           │
│    /api/v1/chat         (SSE streaming)                           │
│    /api/v1/mcp/*        (tool mgmt)                               │
│    /api/v1/skills/*     (skills CRUD)                             │
│    /api/v1/rules/*      (rules CRUD)                              │
│    /api/v1/guardrails/* (PII detection)                           │
└────────┬─────────────────────────────┬──────────────────────────┘
         │                             │
         │ tool call                   │ LLM fallback
         ▼                             ▼
┌────────────────────┐       ┌────────────────────┐
│  O11yBot MCP       │       │  Ollama (local)    │
│  (port 8765)       │       │  (port 11434)      │
│                    │       │                    │
│  16 Grafana tools: │       │  qwen2.5:0.5b      │
│  - list_dashboards │       │  llama3.2:latest   │
│  - list_datasources│       │                    │
│  - list_alert_rules│       │  No API key needed │
│  - health_check    │       │  Self-hosted       │
│  - (12 more)       │       └────────────────────┘
│                    │
│  RBAC: viewer/     │
│        editor/     │
│        admin       │
└────────┬───────────┘
         │ Grafana REST API
         │ (uses SA token)
         ▼
┌─────────────────────────────────────────────────────────┐
│  Grafana (grafana-executive-dashboards, port 3200)      │
│                                                         │
│  - 113 dashboards across 15 folders                     │
│  - 3 datasources (Mimir, Loki, Tempo)                   │
│  - Alerting                                             │
│  - Plugin: gopal-ollychat-app (enabled)                 │
│  - Custom index.html (widget injection)                 │
└─────────────────────────────────────────────────────────┘
```

## Request Flow: "List all Grafana dashboards"

```
1. USER types "list all Grafana dashboards" in O11yBot widget
                         │
2. Widget              fetch(POST /api/v1/chat)
                         │   Content-Type: application/json
                         │   Origin: http://localhost:3200
                         │   X-Grafana-User: admin
                         ▼
3. Orchestrator receives, extracts last user message
   └── intent.match_intent("list all Grafana dashboards")
       └── Pattern (list|show|all).*(dashboard) MATCHES
           └── returns {server:"bifrost-grafana", tool:"list_dashboards", args:{}}
                         │
4. Orchestrator emits SSE: {type:"tool_start", name:"list_dashboards"}
                         │
5. Orchestrator calls MCP REST bridge:
   └── POST http://host.docker.internal:8765/api/tools/call
       {"name":"list_dashboards","arguments":{}}
                         │
6. O11yBot MCP receives tool call
   └── enforce_role("list_dashboards","viewer") ✓
   └── GrafanaClient (viewer token) calls Grafana REST
       └── GET http://localhost:3200/api/search?type=dash-db
                         │
7. Grafana returns 113 dashboards as JSON
                         │
8. O11yBot MCP maps to DashboardSummary[] → returns to orchestrator
                         │
9. Orchestrator emits SSE: {type:"tool_result", durationMs:114}
                         │
10. Orchestrator formats via fmt_dashboards() → markdown
    └── "**Found 113 dashboards:**\n\n- **AKS...** — folder: _Azure_..."
                         │
11. Orchestrator chunks markdown → emits {type:"text", delta:"..."} events
                         │
12. Widget receives SSE stream
    └── Normalizes CRLF → LF
    └── Parses each frame (split by \n\n)
    └── Accumulates text deltas → updates bubble innerHTML via fmtMd()
    └── Renders markdown: bold, links, lists
                         │
13. Final: {type:"usage"} + {type:"done"}
    └── Widget shows token/cost meta
    └── Removes typing indicator
    └── saveState() → localStorage
```

## Data Flow Channels

```
Widget <--SSE--> Orchestrator <--REST--> O11yBot MCP <--REST--> Grafana
       (stream)              (request)            (proxy)
```

- **Widget ↔ Orchestrator**: SSE streaming over HTTP POST. CORS: `localhost:3200` → `localhost:8000`.
- **Orchestrator ↔ O11yBot MCP**: REST bridge endpoint `/api/tools/call`. No streaming.
- **O11yBot MCP ↔ Grafana**: REST API with service account token. Role-aware (viewer/editor/admin).

## State Management

### Browser (Widget)
- **Per-user localStorage**: `o11ybot-<login>` key
  - `msgs[]` (last 100)
  - `posX`, `posY` (custom drag position)
  - `mode` (normal/maximized/fullscreen)
- **Session-only**: `open`, `streaming` flags (reset each page load)

### Orchestrator (In-memory)
- MCP servers dict (resets on container restart — must re-register)
- Skills dict (3 defaults + user-created)
- Rules dict (3 defaults + user-created)

### O11yBot MCP
- HTTP client pool per-environment/role (reused)
- Status map per server

## Security Boundaries

| Boundary | Mechanism |
|---|---|
| Browser → Orchestrator | CORS allowlist |
| Orchestrator → O11yBot MCP | Network-local (Docker host.docker.internal) |
| O11yBot MCP → Grafana | SA token, RBAC enforced per tool |
| PII scanning | Applied to user messages before LLM |

## Technology Stack

| Layer | Tech |
|---|---|
| Widget | Vanilla JavaScript (no framework) |
| Orchestrator | FastAPI + Pydantic + sse-starlette |
| Intent matcher | Regex + ordered priority |
| MCP server | Python FastMCP (O11yBot MCP) |
| Local LLM | Ollama (qwen2.5:0.5b, llama3.2) |
| Prod LLM | OpenAI / Anthropic (swap via env) |
| Observability | OpenTelemetry + LGTM stack |
| Storage | In-memory (upgrade to Postgres for prod) |

## Key Design Decisions

1. **Intent matcher before LLM** — reliable tool calling even with tiny local LLMs that can't do function calling.

2. **Widget injection via custom index.html** — works on every Grafana page without touching Grafana core. Cache-busted with `?v=Date.now()`.

3. **Per-user localStorage keys** — each Grafana user gets isolated chat history; no server-side session needed.

4. **Admin-only model config** — users never see/pick models; `OLLYCHAT_DEFAULT_MODEL` env var controls it.

5. **SSE over WebSockets** — simpler, works through proxies, no connection keepalive headaches.

6. **MCP REST bridge pattern** — O11yBot MCP exposes `/api/tools/call` so the orchestrator doesn't need the MCP SDK.
