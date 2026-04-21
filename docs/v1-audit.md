# OllyBot v1 — System Audit

**Audit date:** 2026-04-20  ·  **Auditor:** Staff Observability Platform Architect (v2 lead)
**Commit audited:** `e4e4412` on `main`  ·  **Repo:** `ollychat-app/`

This is the ground-truth snapshot of what v1 is and does *today*, so v2 work
in [v2-design.md](v2-design.md) is evidence-based, not speculative.
Every claim below is linked to the concrete file + line number in the repo.

---

## 1. Executive summary

v1 is a **production-grade, self-contained, single-command Grafana chatbot** with
a surprisingly complete feature set — but its architecture is **fundamentally
ill-suited to the v2 brief**:

| v1 today | v2 brief requirement |
|---|---|
| Floating vanilla-JS widget injected globally | Split-pane "reasoning canvas" React plugin page |
| **SSE** (one-way stream) | **WebSocket** (bidirectional — approve / edit / discard / undo / stop) |
| Client-side `localStorage` session only | **Server-side sessions** in Redis, 24h TTL, multi-pod via sticky |
| Writes fire as soon as an intent matches | **Human-in-the-loop approval** — `awaiting_approval` → `apply` |
| No snapshot stack, no undo | **Bounded 20-snapshot stack**, undo / redo / revert / compare |
| No draft dashboard concept | Ephemeral `[DRAFT]` board + Grafana Live refresh → promote on apply |
| Regex intent matcher → MCP dispatch | **Typed LLM tool-calling** + `propose_panel`/`commit_dashboard` tools |
| RBAC enforced *at MCP call time only* | **RBAC preflight** against `/api/access-control/user/permissions` at plan time |
| No audit log table | Append-only Postgres audit with before/after hashes |
| No circuit breakers | Circuit breaker on every outbound HTTP client |

**v2 is additive, not a rewrite** — the v1 widget and SSE chat endpoint keep working
behind the existing feature flag. The new surface is a second route inside the
same Grafana plugin, behind `OLLYBOT_INTERACTIVE_MODE=true`.

---

## 2. Repo + deploy topology

**Single repo, single compose file, one-command boot.** After commits
`0129cc0` + `b928525`, everything runs from `ollychat-app/`:

```
ollychat-app/
├── docker-compose.yaml          # the ONLY compose, 10 services, health-gated depends_on
├── Makefile                     # make up is the install story
├── dashboards/                  # 113 provisioned Grafana dashboards (14 folders)
├── provisioning/                # datasources + dashboard providers + prometheus.yml
├── scripts/bootstrap-tokens.sh  # idempotent SA-token minting on first boot
├── orchestrator/                # Python / FastAPI — chat + LLM router
├── mcp-server/                  # Python / FastAPI — 53 MCP tools, own Dockerfile
├── dist/ + src/                 # Grafana app plugin (React) + vanilla JS widget
├── grafana-index.html           # custom index.html that injects the widget globally
└── tests/                       # 8 suites, 160 assertions
```

Compose services (10): `grafana`, `grafana-renderer`, `ollychat-orchestrator`,
`ollychat-mcp`, `ollychat-ollama`, `ollychat-prometheus`, `ollychat-otel-collector`,
`ollychat-tempo`, `ollychat-mimir`, `ollychat-loki`.

Deployment: docker compose only. **No Helm chart, no Kubernetes manifests.**
v2 brief §11 wants `/deploy/k8s/` with a Helm chart — **net-new.**

---

## 3. Backend — what v1 looks like

### 3.1 Stack

| Concern | Actual (ref) |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI (`orchestrator/main.py`) |
| Runtime | `uvicorn[standard]>=0.30` |
| HTTP client | `httpx[http2]>=0.27` (async) |
| Validation | Pydantic v2 + pydantic-settings |
| Streaming | `sse-starlette>=2.1` — `EventSourceResponse` at `chat.py:250` |
| Tracing | OpenTelemetry SDK + OTLP gRPC exporter (`orchestrator/otel_setup.py`) |
| Logging | `structlog>=24` → stdout JSON (`main.py:18-30`) |
| LLM SDKs | `anthropic>=0.39`, `openai>=1.50`, raw httpx for Ollama/Gemini |

**Conclusion:** v1 stack is *already* the stack v2 §4.2 recommends (FastAPI +
httpx + pydantic v2). **No language/framework change required.** We add
`websockets`, `tenacity` (circuit breaker), a Redis async driver, and a
Postgres async driver. Documented under ADR-0001.

### 3.2 Routes

```
GET    /api/v1/health
GET    /api/v1/models
POST   /api/v1/chat                          ← SSE streaming, the primary endpoint
POST   /api/v1/investigate                   ← reserved, not wired to UI yet
GET    /api/v1/mcp/servers
POST   /api/v1/mcp/servers
DELETE /api/v1/mcp/servers/{name}
POST   /api/v1/mcp/servers/{name}/toggle
GET    /api/v1/mcp/tools
POST   /api/v1/mcp/tools/call
GET    /api/v1/skills                        ← stubbed in-memory store
POST   /api/v1/skills
PUT    /api/v1/skills/{id}
DELETE /api/v1/skills/{id}
GET    /api/v1/skills/search
GET    /api/v1/rules
POST   /api/v1/rules
PUT    /api/v1/rules/{id}
DELETE /api/v1/rules/{id}
POST   /api/v1/guardrails/scan
```

No WebSocket endpoint. No `/ws` route. No session endpoints.
**v2 adds:** `WS /api/v2/stream`, `GET /api/v2/sessions/{sid}`,
`POST /api/v2/sessions/{sid}/action`, `POST /api/v2/drafts/{uid}/promote`.

### 3.3 Chat request flow (today)

`POST /api/v1/chat` in `orchestrator/routers/chat.py` (888 lines):

```
  1. request.headers["X-Grafana-User"]  →  grafana_user
     request.headers["X-Grafana-Role"]  →  bifrost_role (viewer/editor/admin)
  2. last_user_msg = last user message in body.messages
  3. intent = await match_intent(last_user_msg)     ← 60+ regex patterns, intents.py (1714 LOC)
  4. if intent:
       yield {"type":"tool_start", …}
       result = await execute_intent(intent, role=bifrost_role)
                   └─► mgr.call_tool(server, tool, args, role)
                       └─► POST {mcp_url}/api/tools/call
       yield {"type":"tool_result", …}
       if intent.get("judge") and raw_data: ranked = await _judge_rerank(...)
       stream formatted markdown as text-delta events
       yield {"type":"usage", "costUsd":…}
       yield {"type":"done"}
  5. else:
       query_type = classify_query(last_user_msg)
       messages   = build_messages(query_type, ..., system=...)
       async for event in _call_llm(model, messages, cfg):
         yield event
```

**Critical observation:** step 4 executes MCP writes (`create_dashboard`,
`create_alert_rule`, `delete_dashboard`) as soon as the regex matches, with
**zero approval handshake**. v2 §8 says *"Never commit to Grafana without
explicit user approval for create / update / delete."* This is the single
biggest behavioural change in v2.

### 3.4 MCP layer

`mcp-server/` is the bundled, self-owned MCP server (replaces the external
Bifröst dependency). Tool inventory at `e4e4412`:

| Area | File | Tools |
|---|---|---|
| Alerts | `alerts.py` | 12 |
| Annotations | `annotations.py` | 3 |
| Dashboards | `dashboards.py` | 10 |
| Datasources | `datasources.py` | 7 |
| Folders | `folders.py` | 5 |
| Library panels | `library_panels.py` | 2 |
| Plugins | `plugins.py` | 2 |
| Teams | `teams.py` | 4 |
| Users | `users.py` | 2 |
| Utility | `utility.py` | 2 |
| Workflows (compound) | `workflows.py` | 7 |
| **Total** | | **56 tools** |

(The README says 53 — the 3-tool delta is from workflow/plugin additions
after the last README sync. Fix in next doc pass.)

MCP transport: **REST bridge**, not MCP-protocol-over-stdio:
- `GET /api/tools` → tool catalog with JSON Schema input definitions
- `POST /api/tools/call` → `{"name": "...", "arguments": {..., "role": "..."}}`

This is deliberately simple and works — v2 can keep it. The brief §4.5 says
*"Tool / function calling is mandatory"* — today that contract exists but is
used by the **orchestrator's regex matcher**, not by the LLM directly. v2
must route LLM tool-calls through the same REST bridge.

### 3.5 LLM gateway

File: `orchestrator/routers/chat.py` + `orchestrator/prompts.py`.

**Providers wired:** Anthropic, OpenAI, Google (Gemini), Ollama — all with
streaming. Models enumerated in `routers/models.py` / `SUPPORTED_MODELS`.
Provider selected by model prefix (`claude-*` → Anthropic, `gpt-*` → OpenAI,
`gemini-*` → Google, everything else → Ollama).

**Prompt categories** (`prompts.py`):
- `tool_result_formatting` (temp 0.1, max 800)
- `observability_qa` (0.2, 500)
- `promql_help` / `logql_help` / `traceql_help` (0.15, 600)
- `incident_analysis` (0.3, 1500)
- `chitchat` (0.5, 150)

**Gap vs v2 §4.5:**
- No task-based provider routing (cheap model for summaries, top-tier for plan
  generation). v1 uses one `OLLYCHAT_DEFAULT_MODEL` for everything.
- No fallback chain (provider A → B → C). Single provider per call.
- No LLM tool-calling contract. The model writes markdown; the orchestrator's
  regex matcher decides what tool to invoke. **This is the biggest semantic
  divergence.**

### 3.6 Guardrails

`orchestrator/guardrails/pii.py` — **18 regex patterns** (email, SSN, AWS key,
GCP key, credit card, JWT, IPv4/v6, phone, URL with creds, etc.).
Modes: `redact`, `block`, `log`.

**Gap vs v2 §8:** no **prompt-injection defence** for content pulled from
dashboards / alert annotations / log lines. v2 must wrap any Grafana content
going into an LLM prompt in quoted untrusted blocks.

### 3.7 Session model (or lack of)

**There is no server-side session.** State lives entirely in the browser:

```js
// o11ybot-widget.js:48, 104
var STORE_KEY = "o11ybot-" + grafanaUser.login;   // per-user localStorage key
localStorage.setItem(STORE_KEY, JSON.stringify({
  sessions: state.sessions,
  activeSessionId: state.activeSessionId,
  ...
}));
```

Every HTTP request is stateless. The orchestrator never sees a session-id;
it reassembles context from `body.messages` every turn.

**Implications for v2:**
- Snapshot stack, draft dashboard state, approval-pending state all need a
  server-side home (Redis per §4.6).
- `.env` already declares `redis_url: "redis://redis:6379/0"` and
  `postgres_url: "postgresql://ollychat:ollychat@postgres:5432/ollychat"`
  at `config.py:58-59` — **but neither is used in code**. Docker compose
  doesn't even start a Redis or Postgres container. **Net-new work.**

### 3.8 Circuit breakers, retries, backoff

None. httpx calls use `timeout=30s` and fail fast. `mgr.call_tool` catches
exceptions and returns `{"ok": false, "error": "…"}` but no half-open state,
no backoff, no tripping threshold.

**v2 §4.2 requires** `tenacity` + a circuit breaker on every outbound HTTP
client. Needs to wrap: Grafana API, Ollama, Anthropic, OpenAI, Google, MCP.

---

## 4. Frontend — what the user actually sees

### 4.1 Two surfaces, one dominant

| Surface | Role | Where |
|---|---|---|
| **Floating widget** (`o11ybot-widget.js`, 1900 LOC vanilla JS) | The real UX — the orange bubble on every Grafana page | Injected globally via `grafana-index.html` → `/public/plugins/gopal-ollychat-app/o11ybot-widget.js` |
| **Grafana app plugin** (`src/`, React + TS) | Six plugin pages declared in `plugin.json` | `/a/gopal-ollychat-app/{chat,investigate,skills,mcp,rules,config}` |

The React plugin pages exist but are **largely stubs**. Users interact almost
exclusively with the vanilla-JS widget.

### 4.2 Widget architecture

- Single IIFE, no framework, no build step. Ships as a static file.
- State: `state.sessions[]` in localStorage keyed by Grafana login.
- Four window modes: FAB, Normal, Maximised, Fullscreen.
- SSE parsing with CRLF-safe buffer handling (covered by suite3-widget.js).
- Event types the widget understands today: `tool_start`, `tool_result`,
  `text` (delta), `usage`, `done`, `error`.

**v2 implication:** the split-pane reasoning canvas is a **net-new React
page**, not an extension of the widget. The widget keeps doing what it does
(the "quick chat" surface). The canvas lives at a new plugin route like
`/a/gopal-ollychat-app/canvas`, behind `OLLYBOT_INTERACTIVE_MODE`.

### 4.3 Grafana auth in the browser

The widget reads the active Grafana user from `window.grafanaBootData`
(set by Grafana) and forwards three headers to the orchestrator:

- `X-Grafana-User`
- `X-Grafana-Org-Id`
- `X-Grafana-Role`  (Admin / Editor / Viewer)

The orchestrator trusts these headers. This is fine for the widget (same-origin,
Grafana-signed) but **not sufficient for v2's RBAC preflight**, which needs
to hit `GET /api/access-control/user/permissions` with the *user's* token to
check specific write scopes (`dashboards:write` on a folder). v1 only has
three shared service-account tokens; it has no per-user OAuth pass-through.

**Net-new for v2:** OAuth token forwarding, per §4.2 *"forwarded user OAuth
tokens (preferred for multi-tenant)"*. Grafana Cloud already supports this
via the `datasource.proxy` pattern — v2 documents the flow in ADR-0004.

---

## 5. Observability — dogfood scorecard

v1 **already instruments itself well** compared to the average chatbot:

| v2 §9 requirement | v1 state |
|---|---|
| OpenTelemetry traces | ✅ `orchestrator/otel_setup.py` — OTLP gRPC exporter to the bundled Grafana Alloy / OTEL collector |
| Prometheus `/metrics` endpoint | ⚠️ MCP server has `/metrics` (`mcp-server/observability.py`). **Orchestrator does NOT.** |
| Structured JSON logs | ✅ `structlog` on both services |
| `ollybot_requests_total{kind,status}` | ❌ not defined |
| `ollybot_llm_latency_seconds` | ❌ not defined |
| `ollybot_grafana_api_latency_seconds` | ⚠️ MCP has `ollychat_mcp_grafana_requests_total{method,status_class}` — missing latency histogram |
| `ollybot_draft_commits_total` | ❌ no drafts in v1 |
| `ollybot_reasoning_events_total` | ❌ no reasoning events in v1 |
| `ollybot_circuit_breaker_state` | ❌ no circuit breakers in v1 |
| Self-dashboard "OllyBot Operations" | ❌ dashboards folder has nothing bot-specific |
| Self-alert rules (LLM error rate, breaker open) | ❌ not shipped |

**v2 work:** add `/metrics` to orchestrator, add the full metric catalogue
in §9, ship a pre-built operations dashboard under `/deploy/dashboards/` and
a matching alert ruleset under `/deploy/alerts/`, auto-provision both on
startup (skippable via `OLLYBOT_SELF_PROVISION=false`).

---

## 6. Testing — current baseline

8 suites, 160 passing assertions (`tests/`):

| Suite | File | Assertions | Focus |
|---|---|---|---|
| 1 | `suite1-api.sh` | 17 | API + CORS + tool catalog |
| 2 | `suite2-intents.sh` | 19 | Intent matcher coverage |
| 3 | `suite3-widget.js` | 22 | SSE parser (Node driver, vanilla JS target) |
| 4 | `suite4-integration.js` | 18 | E2E chat → tool → Grafana |
| 5 | `suite5-negative.js` | 22 | Errors, edge cases, Unicode, concurrency |
| 6 | `suite6-prompts.js` | 18 | Prompt engineering outputs |
| 7 | `suite7-categories.sh` | 31 | Category routing (35+ categories) |
| 8 | `suite8-rbac.sh` | 13 | Role enforcement |

**Gap vs v2 §13:** no **chaos tests** (kill Grafana / LLM / Redis mid-flow),
no **load test** at 200 concurrent sessions, no **security corpus** for
prompt-injection. No **Playwright e2e** — `suite3-widget.js` is a Node
string-level parser test, not a browser-driven flow.

---

## 7. Storage — declared, not used

`orchestrator/config.py:58-59`:

```python
postgres_url: str = "postgresql://ollychat:ollychat@postgres:5432/ollychat"
redis_url: str = "redis://redis:6379/0"
```

`orchestrator/storage/` — empty package; no adapter code.

Nothing imports either URL. `docker-compose.yaml` has no `postgres` or
`redis` service. The audit-log, snapshot-stack, session-state infrastructure
v2 needs is **entirely net-new**.

---

## 8. RBAC, safety, governance

### 8.1 What v1 does
- `mcp-server/rbac.py` defines `TOOL_MINIMUM_ROLE` — every tool has a min
  role. `enforce()` raises `PermissionError` at tool-call time.
- Three role-scoped SA tokens: `GRAFANA_{VIEWER,EDITOR,ADMIN}_TOKEN` in
  `.env`, automatically minted by `scripts/bootstrap-tokens.sh` on first
  boot of the bundled Grafana.
- PII scanner before LLM calls.

### 8.2 What v1 doesn't do (v2 §8)
- **No approval gate.** When an intent like `create dashboard for X`
  matches, the write fires immediately.
- **No RBAC preflight.** v1 calls the tool and lets it fail; v2 must check
  `/api/access-control/user/permissions` at *plan* time and refuse early.
- **No dry-run mode.** No `OLLYBOT_DRY_RUN=true` global switch.
- **No rate limiting.** No per-user / global mutation caps.
- **No destructive-action gating.** Delete fires on one regex match.
- **No prompt-injection defence** for content pulled from dashboards.
- **No secret scrubber** in the pre-LLM pass (PII ≠ secret-shaped strings;
  the current scanner covers 18 PII types but not `glsa_…` or similar).

### 8.3 Smallest safe-write PR first
When v2 lands the approval gate, the cheapest MVP is:
1. Every intent that targets a write tool emits `awaiting_approval` **instead**
   of executing.
2. Orchestrator stashes the proposed `{tool, args}` in Redis keyed by
   session_id.
3. A follow-up `POST /api/v2/sessions/{sid}/action {"verb":"apply"}`
   executes the stashed call.

That single change closes the biggest safety gap and is implementable in
~200 LOC behind `OLLYBOT_INTERACTIVE_MODE`.

---

## 9. Backward compatibility — what v2 must not break

1. `POST /api/v1/chat` SSE protocol — the widget depends on it. Keep
   `v1` path, add `v2/stream` (WebSocket) for the canvas.
2. The six widget event types (`tool_start`, `tool_result`, `text`,
   `usage`, `done`, `error`) — widget depends on the exact JSON shape.
3. The widget's `localStorage` key format — existing users have history.
4. `/api/v1/mcp/servers` and `/api/v1/mcp/tools/*` — admin tooling relies
   on the REST bridge shape.
5. `scripts/bootstrap-tokens.sh` idempotence — `make up` must stay
   one-command.
6. The 160 existing tests must stay green.
7. The auto-MCP-registration on orchestrator startup
   (`main.py:62-82` — lifespan hook wiring).

v2 work lives under `/api/v2/*` and a new plugin page route.

---

## 10. Summary — what v2 inherits, what's net-new

### v1 gifts v2 (reuse, don't rebuild)
- FastAPI + httpx + pydantic v2 + sse-starlette + structlog + OTEL stack
- 53+ MCP tools in `mcp-server/` with role enforcement
- Three-role SA token flow + `bootstrap-tokens.sh`
- Bundled docker-compose with Grafana + LGTM + Ollama + renderer + MCP
- 113 provisioned dashboards
- PII scanner (18 patterns)
- Intent matcher + LLM-as-judge (for fuzzy search only)
- Grafana app plugin scaffold (we add a new page inside it)
- Auto-MCP-registration on orchestrator lifespan
- 160-assertion test baseline

### v2 net-new work
- WebSocket endpoint + reasoning-event protocol (`packages/reasoning-protocol/`)
- Server-side session manager (Redis-backed)
- Snapshot stack + diff viewer + undo (`packages/diff-snapshot/`)
- Draft dashboard lifecycle (`[DRAFT]` + promote) + Grafana Live
- Approval gate (`awaiting_approval` → `apply`)
- RBAC preflight via `/api/access-control/user/permissions`
- OAuth user-token forwarding for multi-tenant
- Circuit breakers on every outbound client (`tenacity` + state machine)
- Prompt-injection quoting + secret scrubber
- Split-pane React page in the existing plugin
- Alert rule preview pane with live threshold visualisation
- Multi-provider LLM routing with task-based selection + fallback chain
- LLM tool-calling contract (not regex-dispatched) — `propose_panel`,
  `probe_metric`, `commit_dashboard`, …
- Audit log (append-only Postgres) with before/after hashes
- Postgres + Redis wiring in compose (currently declared in env, unused)
- Helm chart under `/deploy/k8s/`
- Self-observability dashboard + alerts auto-provisioning
- Chaos + load + Playwright e2e tests
- ADRs 0001-00NN for every contentious decision

### ADRs that must be written before code
1. **ADR-0001 — Backend stack** (confirm FastAPI + WebSocket + websockets lib)
2. **ADR-0002 — Frontend surface** (second React page in existing plugin vs standalone Next.js)
3. **ADR-0003 — Draft dashboard strategy** (`[DRAFT]` prefix + Grafana Live vs iframe+postMessage)
4. **ADR-0004 — Auth propagation** (SA tokens vs forwarded user OAuth)
5. **ADR-0005 — Session store** (Redis schema, TTL, eviction)
6. **ADR-0006 — LLM tool-calling contract** (REST bridge vs native MCP vs Anthropic tool_use)
7. **ADR-0007 — Snapshot + audit persistence** (Postgres schema, retention)
8. **ADR-0008 — Backward compat guarantees** (explicit v1 API surface + SemVer policy)

---

## 11. Recommendation

Phase 0 of the v2 plan (§12) can start immediately:

1. Produce `docs/v2-design.md` (next deliverable per §15.2) based on this audit.
2. Write ADRs 0001–0003 (the foundation-blockers).
3. Scaffold `packages/reasoning-protocol/` as the first concrete package
   (schema + TS/Py types — shared contract between frontend and backend).
4. Add Redis + Postgres services to `docker-compose.yaml` (both declared in
   env, both unused — low-risk plumbing).

All of the above are **additive and non-breaking**. Nothing in v1 changes
until Phase 1 PR #1 lands the new WebSocket endpoint — and that's
gated by `OLLYBOT_INTERACTIVE_MODE=false` by default.

**Ready to proceed to `docs/v2-design.md` on your approval.**
