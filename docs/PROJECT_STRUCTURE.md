# O11yBot — Project Structure

This document is the map. Every top-level folder + every runtime file is listed
with its purpose so new contributors can orient themselves in a single scroll.

## Top-level layout

```
ollychat-app/
├── Makefile                    One-command stack — make up / down / restart / test
├── docker-compose.yaml         The ONLY compose file — 10 services wired
├── .env.example                Every env var documented (copy to .env)
├── README.md                   Entry point
│
├── plugin.json                 Grafana App plugin manifest (v3 schema)
├── dist/                       Built plugin assets Grafana loads (widget + Go bin)
├── src/                        React/TypeScript sources for the plugin shell
├── o11ybot-widget.js           Self-contained vanilla-JS floating widget (source)
├── grafana-index.html          Custom Grafana index.html that injects the widget
│
├── mcp-server/                 O11yBot's own MCP server (Python / FastAPI, 53 tools)
├── orchestrator/               Chat + LLM orchestrator (Python / FastAPI)
├── pkg/                        Go backend plugin resources (proxy shim)
│
├── dashboards/                 113 provisioned Grafana dashboards across 14 folders
├── provisioning/               Datasource + dashboard-provider + Prometheus config
├── scripts/                    Bootstrap + maintenance shell scripts
│   └── bootstrap-tokens.sh     Idempotent SA-token minting (auto-runs on `make up`)
│
├── otel-collector-config.yaml  Telemetry pipeline
├── tempo-config.yaml           Traces
├── mimir-config.yaml           Metrics
├── loki-config.yaml            Logs
│
├── tests/                      Eight test suites — 160 tests
└── docs/                       All documentation (this file included)
```

## `mcp-server/` — the MCP tool layer

Exposes `/api/tools` and `/api/tools/call` over REST.  Stateless, per-role
HTTP client pool, 53 tools.  Deploy against any Grafana with env vars.

```
mcp-server/
├── Dockerfile                  python:3.12-slim, installs requirements.txt
├── requirements.txt            fastapi, httpx, structlog, prometheus-client
├── main.py                     FastAPI app + /health + /metrics + /api/tools*
├── config.py                   Settings dataclass pulled from env vars
├── grafana_client.py           Async httpx client w/ per-role Authorization
├── rbac.py                     TOOL_MINIMUM_ROLE + enforce() helper
├── registry.py                 @tool decorator + JSON-schema introspection
├── observability.py            Prometheus counters/histograms + audit log ctx mgr
└── tools/
    ├── __init__.py             Imports every module → triggers @tool registration
    ├── _panel_templates.py     RED + discovery-driven panel builders
    ├── dashboards.py           list/search/get/panels + create (smart/plain)/update/delete
    ├── alerts.py               rules CRUD, instances, silences, contact points, policies
    ├── annotations.py          list / create / delete annotations
    ├── datasources.py          list/get + query + LogQL + TraceQL + metric / label discovery
    ├── folders.py              list/get/create/update/delete
    ├── library_panels.py       list / get reusable panels
    ├── plugins.py              list / get plugin metadata
    ├── teams.py                list/create + members
    ├── users.py                list users, list service accounts
    ├── utility.py              health_check, get_server_info
    └── workflows.py            Compound tools: investigate_alert, correlate_signals,
                                create_slo_dashboard, find_dashboards_using_metric,
                                alert_wizard, dashboard_wizard
```

## `orchestrator/` — chat + LLM routing

SSE-streamed chat endpoint.  Intent matcher fires before the LLM so tool calls
are cheap and deterministic.  Falls through to prompt-engineered LLM for open
questions.

```
orchestrator/
├── Dockerfile                  python:3.12-slim
├── requirements.txt
├── main.py                     FastAPI app, CORS, lifespan, OTEL init
├── config.py                   pydantic-settings.  Reads OLLYCHAT_* env vars
├── otel_setup.py               OpenTelemetry init (optional, skip if no collector)
├── intents.py                  ~1700 LOC — intent matcher, 60+ patterns, formatters,
│                               LLM-as-judge reranker plumbing, _match_mutation_intent,
│                               local fuzzy search, semantic synonym expansion
├── categories.py               35+ dashboard categories with keywords + tags
├── prompts.py                  Five query categories w/ tuned temperature/top_p,
│                               system prompts, few-shot examples
├── mcp/
│   └── client.py               MCP client manager (connects to /api/tools*)
├── routers/
│   ├── chat.py                 POST /api/v1/chat — SSE streaming + tool dispatch
│   ├── models.py               GET /api/v1/models — SUPPORTED_MODELS catalog
│   ├── mcp.py                  Register / unregister MCP servers at runtime
│   └── investigate.py          Investigation engine (seed for future multi-agent)
├── core/                       Investigation primitives (hypothesis, correlation,
│                               parallel collector, postmortem) — reserved for
│                               the multi-agent investigator rollout
├── guardrails/                 PII scanner (15 patterns) + redact engine
├── models/                     Pydantic persistence models (skills, rules)
├── storage/                    PostgreSQL adapter (reserved)
└── tools/                      LGTM query helpers reused by workflows
```

## Widget — `o11ybot-widget.js`

A single vanilla JS file that ships inside `dist/`.  Grafana's custom index.html
(`grafana-index.html`) inserts a `<script>` tag so the widget loads on every page.

Key state:
- `state.sessions[]` — per-user chat sessions, keyed by Grafana `login`
- `state.activeSessionId` — current session UID
- `state.open / state.mode` — FAB / normal / maximized / fullscreen
- LocalStorage: `o11ybot-<username>`

Rendered elements:
- `.ob-panel` — the floating window
- `.ob-tabs` — 💬 Chat and 🕑 History
- `.ob-welcome` — time-aware greeting + quick-action grid (role-gated)
- `.ob-msgs` — message thread with markdown rendering
- `.ob-in` — composer; Enter to send, Shift+Enter for newline

## `src/` — the Grafana App plugin shell

```
src/
├── module.ts                   Plugin registration (AppPlugin + pages)
├── plugin.json                 App plugin manifest
├── types.ts                    Shared TypeScript types
├── constants.ts                Default prompts + API paths
├── styles.ts                   useStyles2 theme integration
├── pages/
│   ├── App.tsx                 React Router root
│   ├── ChatPage.tsx            Main chat UI (for users who open the plugin page)
│   ├── ConfigPage.tsx          Plugin settings (orchestrator URL, model, PII)
│   ├── MCPConfigPage.tsx       MCP server management UI
│   ├── InvestigatePage.tsx     4-tab investigation workspace
│   ├── SkillsPage.tsx          Skill editor
│   └── RulesPage.tsx           Rules editor
├── components/
│   ├── ChatMessage.tsx         Message bubble, markdown, role avatar
│   ├── ChatInput.tsx           TextArea + send button
│   ├── ConversationSidebar.tsx Past conversations
│   ├── ModelSelector.tsx       LLM model dropdown
│   ├── ToolCallCard.tsx        Tool invocation visualisation
│   ├── ToolApprovalDialog.tsx  Approve/reject mutating tool calls
│   ├── CostBadge.tsx           Per-message cost + token tooltip
│   └── PIIWarning.tsx          Redact / send override dialog
├── hooks/
│   ├── useChat.ts              Streaming chat hook (fetch + ReadableStream)
│   └── useBackendSrv.ts        Grafana backend service wrapper
└── services/                   Typed clients for orchestrator endpoints
```

## `pkg/` — Go backend (plugin proxy)

```
pkg/
├── main.go                     Plugin entrypoint (app.ManagedInstance)
└── plugin/
    ├── app.go                  App struct + HTTP client to orchestrator
    └── resources.go            CallResource proxy: /chat, /health, /models
```

Role: forwards the Grafana user session to the orchestrator so the browser
doesn't speak CORS directly to `:8000`.

## `dashboards/` — 113 provisioned Grafana dashboards

Every dashboard JSON lives here, organised by Grafana folder. Grafana loads
them on boot via the providers config in `provisioning/dashboards/`.

```
dashboards/
├── L0-executive/            (1) — L0 command center
├── L1-domain/               (3) — infra · apps · profiling overview
├── L2-service/              (1) — service golden signals
├── L3-deepdive/             (4) — trace · log · profile · k8s debug
├── azure/                  (24) — compute · storage · db · AKS …
├── grafana/                (10) — grafana self-monitoring
├── loki/                    (5) — log dashboards
├── mimir/                   (5) — metric dashboards
├── tempo/                   (3) — trace dashboards
├── pyroscope/               (3) — profile dashboards
├── observability-kpi/       (7) — SLO · error budget · business KPIs
├── oci/                    (22) — Oracle Cloud Infrastructure
├── platform/               (17) — home page + executive command center
└── volume/                  (6) — cross-stack capacity planning
```

## `provisioning/` — Grafana auto-provisioning

Grafana picks these up on boot.

```
provisioning/
├── datasources/datasources.yaml   Pre-configured Prometheus/Mimir datasource
├── dashboards/dashboards.yaml     14 providers, one per dashboards/ folder
└── prometheus.yml                 Prometheus stub config (served by the bundled prometheus)
```

## `scripts/` — operational helpers

```
scripts/
└── bootstrap-tokens.sh    Mint viewer/editor/admin SA tokens in the bundled
                           Grafana on first `make up`, write them to .env,
                           restart the MCP so it picks them up. Idempotent —
                           skips when valid tokens already exist.
```

## `tests/`

Eight suites — 160 assertions.  Run with `./tests/run-all-tests.sh`.

| Suite | File | Tests |
|---|---|---|
| 1 | `suite1-api.sh`         | 17 — API + CORS + tool catalog |
| 2 | `suite2-intents.sh`     | 19 — intent matcher coverage |
| 3 | `suite3-widget.js`      | 22 — SSE parser |
| 4 | `suite4-integration.js` | 18 — E2E chat → tool → response |
| 5 | `suite5-negative.js`    | 22 — errors + edge cases |
| 6 | `suite6-prompts.js`     | 18 — prompt engineering |
| 7 | `suite7-categories.sh`  | 31 — category routing |
| 8 | `suite8-rbac.sh`        | 13 — role enforcement |

## `docs/`

```
docs/
├── README.md                   Index (start here)
├── PROJECT_STRUCTURE.md        This file
├── INSTALLATION.md             Zero-to-boot install — OSS + Enterprise paths
├── DEPLOYMENT.md               Deploy anywhere; production hardening
├── ENTERPRISE.md               RBAC, self-observability, scaling
├── ARCHITECTURE.md             System diagram + data flow
├── API_REFERENCE.md            REST endpoints + SSE event types + MCP tool catalog
├── USE_CASES.md                Every use case O11yBot supports (full matrix)
├── RBAC.md                     Role design + service-account setup
├── VALIDATION.md               End-to-end validation scenarios (manual)
├── TESTING.md                  Automated test suite reference
└── assets/                     Screenshots, GIFs, logo SVGs
```

## Docker Compose services

| Service | Port | Purpose |
|---|---|---|
| `ollychat-grafana` | 3002 | Dev Grafana w/ the plugin mounted |
| `ollychat-orchestrator` | 8000 | Chat API |
| `ollychat-mcp` | 8765 | O11yBot's own MCP server (this repo) |
| `ollychat-ollama` | 11434 | Local LLM for dev/test |
| `ollychat-otel-collector` | 4327/4328 | OTLP gRPC/HTTP ingress |
| `ollychat-tempo` | 3210 | Traces |
| `ollychat-mimir` | 9010 | Metrics |
| `ollychat-loki` | 3110 | Logs |

## Where configuration lives

| Layer | Source of truth |
|---|---|
| Widget | None — it reads everything from the Grafana user session |
| Orchestrator | `OLLYCHAT_*` env vars (see `.env.example`) |
| MCP server | `GRAFANA_URL`, `GRAFANA_{VIEWER,EDITOR,ADMIN}_TOKEN` env vars |
| Grafana | `GF_*` env vars + files under `provisioning/` |

No YAML config files, no secrets in git — everything is env vars at runtime.
