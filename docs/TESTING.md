# O11yBot Testing Guide

Complete testing documentation — **160 automated tests across 8 suites**.

## Quick Start

```bash
cd /Volumes/Gopalmac/Gopal-aiops/ollychat-app/tests

./preflight.sh            # verify all services are up (required)
./run-all-tests.sh        # run all 160 tests

# Run individual suites:
./suite1-api.sh           # 17 tests — API endpoints
./suite2-intents.sh       # 19 tests — Intent matcher
node suite3-widget.js     # 22 tests — UI Widget / SSE parser
node suite4-integration.js  # 18 tests — Integration / E2E
node suite5-negative.js   # 22 tests — Error / negative cases
node suite6-prompts.js    # 18 tests — Prompt engineering
./suite7-categories.sh    # 31 tests — Category intents
```

Expected output:
```
Suite 1 Results: 17 passed, 0 failed   (API endpoints)
Suite 2 Results: 19 passed, 0 failed   (Intent matcher)
Suite 3 Results: 22 passed, 0 failed   (UI Widget / SSE)
Suite 4 Results: 18 passed, 0 failed   (Integration / E2E)
Suite 5 Results: 22 passed, 0 failed   (Negative / Errors)
Suite 6 Results: 18 passed, 0 failed   (Prompt Engineering)
Suite 7 Results: 31 passed, 0 failed   (Category Intents)
TOTAL:          160 passed, 0 failed
```

---

## Architecture Under Test

```
Browser (Grafana :3200)
  │ inject widget via custom index.html
  ↓
O11yBot Widget (JavaScript)
  │ POST /api/v1/chat (SSE streaming)
  ↓
Orchestrator (Python FastAPI :8000)
  │ Intent matcher → Category router → MCP tool OR LLM fallback
  ├──→ Ollama LLM (:11434, qwen2.5:0.5b)
  └──→ O11yBot MCP Server (:8765)
           │ REST bridge /api/tools/call
           ↓
         Grafana API (:3200)
```

---

## Pre-requisites

All services must be running before tests:

```bash
# Orchestrator + LGTM stack
docker ps --filter "name=ollychat"
# Expected: ollychat-orchestrator, ollychat-ollama, ollychat-otel-collector,
#           ollychat-mimir, ollychat-loki, ollychat-tempo

# Main Grafana
docker ps --filter "name=grafana-executive-dashboards"

# O11yBot MCP
curl -s http://localhost:8765/api/tools >/dev/null && echo "O11yBot MCP OK"
# (or restart: cd ../O11yBot MCP && .venv/bin/grafana-mcp serve --port 8765 &)
```

Run `./tests/preflight.sh` to check everything at once.

---

## Endpoints Under Test

| Endpoint | Method | Purpose |
|---|---|---|
| `:8000/api/v1/health` | GET | Orchestrator health |
| `:8000/api/v1/models` | GET | Available LLM models |
| `:8000/api/v1/chat` | POST | Stream chat (SSE) |
| `:8000/api/v1/mcp/servers` | GET/POST/DELETE | MCP server management |
| `:8000/api/v1/mcp/tools` | GET | List MCP tools |
| `:8000/api/v1/mcp/tools/call` | POST | Execute MCP tool |
| `:8000/api/v1/skills` | GET/POST/PUT/DELETE | Skills CRUD |
| `:8000/api/v1/rules` | GET/POST/PUT/DELETE | Rules CRUD |
| `:8000/api/v1/guardrails/scan` | POST | PII detection |
| `:8765/api/tools` | GET | O11yBot MCP tool catalog |
| `:8765/api/tools/call` | POST | O11yBot MCP tool invocation |
| `:3200/api/plugins/gopal-ollychat-app/settings` | GET | Plugin config |
| `:3200/public/plugins/gopal-ollychat-app/o11ybot-widget.js` | GET | Widget JS |

---

## Suite 1: API Endpoints (17 tests)

Validates REST endpoints respond correctly.

| # | Test | Endpoint | Expected |
|---|---|---|---|
| T1 | Orchestrator healthy | `GET /api/v1/health` | `{"status":"healthy"}` |
| T2 | Service name correct | `GET /api/v1/health` | Contains `ollychat-orchestrator` |
| T3 | Models list | `GET /api/v1/models` | ≥1 model |
| T4 | MCP O11yBot MCP connected | `GET /api/v1/mcp/servers` | `status=connected` |
| T5 | 16 MCP tools | `GET /api/v1/mcp/servers` | `toolCount=16` |
| T6 | Tools endpoint | `GET /api/v1/mcp/tools` | 53 tools |
| T7 | Skills list | `GET /api/v1/skills` | 3 default skills |
| T8 | Rules list | `GET /api/v1/rules` | 3 default rules |
| T9 | PII scan detects | `POST /api/v1/guardrails/scan` | `has_pii=true` |
| T10 | PII matches count | `POST /api/v1/guardrails/scan` | 2 matches (email+ssn) |
| T11 | Tool call succeeds | `POST /api/v1/mcp/tools/call` | `ok=true` |
| T12 | CORS preflight | `OPTIONS /api/v1/chat` | allow origin 3200 |
| T13 | Grafana healthy | `GET :3200/api/health` | HTTP 200 |
| T14 | Widget JS served | `GET /public/plugins/.../widget.js` | HTTP 200 |
| T15 | Plugin enabled | `GET /api/plugins/.../settings` | `enabled=true` |
| T16 | O11yBot MCP direct | `GET :8765/api/tools` | 53 tools |
| T17 | HTML has widget | `GET :3200/ (auth)` | script tag present |

### Manual validation
```bash
# Health
curl http://localhost:8000/api/v1/health

# PII scan
curl -X POST http://localhost:8000/api/v1/guardrails/scan \
  -H "Content-Type: application/json" \
  -d '{"text":"Email: user@test.com, SSN: 123-45-6789"}' | jq
```

---

## Suite 2: Intent Matcher (19 tests)

Validates natural-language queries route to correct MCP tools.

| # | Query | Expected Tool |
|---|---|---|
| T1 | `list all Grafana dashboards` | `list_dashboards` |
| T2 | `show dashboards` | `list_dashboards` |
| T3 | `all dashboards` | `list_dashboards` |
| T4 | `list datasources` | `list_datasources` |
| T5 | `show all data sources` | `list_datasources` |
| T6 | `check datasource health` | `list_datasources` |
| T7 | `list all alerts` | `list_alert_rules` |
| T8 | `show firing alerts` | `list_alert_instances` |
| T9 | `active alerts` | `list_alert_instances` |
| T10 | `alert instances` | `list_alert_instances` |
| T11 | `list all folders` | `list_folders` |
| T12 | `check grafana health` | `health_check` |
| T13 | `grafana status` | `health_check` |
| T14 | `grafana version` | `health_check` |
| T15 | `health check` | `health_check` |
| T16 | `mcp server info` | `get_server_info` |
| T17 | `ollychat-mcp info` | `get_server_info` |
| T18 | `search dashboards aks` | `search_dashboards` |
| T19 | `list users` | `list_users` |

### Manual validation
```bash
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"list all dashboards"}],"stream":true}' \
  | grep "tool_start"
# Expected: data: {"type":"tool_start","name":"list_dashboards",...}
```

---

## Suite 3: UI Widget / SSE Parser (22 tests)

Simulates exact browser widget behavior to catch streaming bugs.

### T1-T3: HTTP Response
- HTTP 200 status
- Content-Type: `text/event-stream`
- CORS: `Access-Control-Allow-Origin: http://localhost:3200`

### T4-T8: SSE Event Types
All 5 event types emitted:
- `tool_start` — tool invocation begins
- `tool_result` — tool completed with duration
- `text` — streaming content delta
- `usage` — token counts + cost
- `done` — stream terminator

### T9-T12: Content Correctness
- Content length > 500 bytes
- Mentions `dashboard`
- Markdown bold (`**text**`) present
- Markdown links (`[text](url)`) present

### T13-T15: Tool Metadata
- `tool_start.name === "list_dashboards"`
- `tool_start.id` present
- `tool_result.durationMs` tracked

### T16: CRLF Line Ending Fix
- sse-starlette emits `\r\n\r\n` frames
- Widget normalizes to `\n\n` before parsing
- Expected: 500+ events parsed per query

### T17-T20: Multi-query Isolation
- Sequential queries don't contaminate
- Different tools for different queries
- Content matches each query

### T21-T22: Dashboard Search
- `search dashboards aks` → tool `search_dashboards`
- Args contain `query: "aks"`

### Known Bug (fixed)
Before: widget parsed `\n\n` only, server emits `\r\n\r\n` → ALL events missed, empty bubble.
Fix: `buf = buf.replace(/\r\n/g, "\n")` before parsing.

---

## Suite 4: Integration / E2E (18 tests)

End-to-end tests covering the full request chain.

| # | Test | Verifies |
|---|---|---|
| T1 | Chat → tool → dashboards | HTTP 200 + real dashboard data |
| T2 | User identity propagation | `X-Grafana-User` reaches logs |
| T3 | MCP → Grafana chain | Real v11.6.4, DB ok, 42ms |
| T4 | All tools have `minRole` | 16/53 tools tagged |
| T5 | Admin-only tools | ≥2 (list_users, list_service_accounts) |
| T6 | Plugin enabled | Returns `enabled=true` |
| T7 | Plugin name | "OllyChat" |
| T8 | 6 pages registered | Chat, Investigate, Skills, MCP, Rules, Config |
| T9 | Multi-turn conversation | 3-turn accepted |
| T10 | Multi-turn returns text | Events present |
| T11 | Dashboard count = Grafana | MCP returns 113 = `/api/search` |

### Manual validation
```bash
# Full chain test
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-User: admin" \
  -d '{"messages":[{"role":"user","content":"list all dashboards"}]}' \
  | grep -o "dashboard" | wc -l
# Expected: many matches (response mentions dashboards)
```

---

## Suite 5: Negative / Error Cases (22 tests)

| # | Test | Expected |
|---|---|---|
| T1 | Invalid tool name | `{ok:false, error}` |
| T2 | Unknown server name | HTTP 200 with JSON error (not 500) |
| T3 | RBAC: viewer → admin tool | `PermissionError` in response |
| T4 | Empty messages | HTTP 200 graceful |
| T5 | Malformed schema | HTTP 422 |
| T6 | Non-intent → LLM fallback | `text` events, no `tool_start` |
| T7 | Skills CRUD | Create+delete roundtrip works |
| T8 | Rules CRUD | Create+delete roundtrip works |
| T9 | PII clean text | `has_pii=false` |
| T10 | PII multi-type | Detects ≥3 types (email+ssn+aws) |
| T11 | 5x concurrent requests | All return HTTP 200 |
| T12 | Large payload (10KB) | HTTP 200 accepted |
| T13 | Unicode/emoji | `Hello 👋 日本語 🎉` accepted |

---

## Suite 6: Prompt Engineering (18 tests)

Validates query classifier, tuned sampling, system prompts, few-shot examples.

### Query Classifier

| Query | Expected Category | Tuned Params |
|---|---|---|
| `promql for cpu usage` | `promql_help` | T=0.15, max=600 |
| `what is the RED method?` | `observability_qa` | T=0.2, max=500 |
| `why is payment slow?` | `incident_analysis` | T=0.3, max=1500 |
| `hi` | `chitchat` | T=0.5, max=150 |
| (tool result rephrasing) | `tool_result_formatting` | T=0.1, max=800 |

### Tests

- T1-T3: PromQL help → response contains code fence / `rate(` / `promql`
- T4-T6: Observability Q&A → mentions ≥2 RED terms (rate/error/duration)
- T7: LogQL help → non-empty response
- T8-T10: Intent match still uses fast path (no LLM call)
- T11-T12: Chitchat classification works
- T13-T14: Incident analysis returns substantive response
- T15: User name propagated to system prompt
- T16-T17: Multi-turn conversation
- T18: Response doesn't blindly echo user message

### Manual validation
```bash
# PromQL help should return code fence
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"promql for error rate"}],"stream":true}' \
  | grep -o "promql"
```

---

## Suite 7: Category Intents (31 tests)

Validates category-filtered and service-specific dashboard queries.

### Cloud Providers (5 tests)

| Query | Expected Tag |
|---|---|
| `list AKS dashboards` | `aks` |
| `show Azure dashboards` | `azure` |
| `list OCI dashboards` | `oci` |
| `GCP dashboards` | `gcp` |
| `AWS dashboards` | `aws` |

### Kubernetes (1 test)
- `kubernetes dashboards` → tag `kubernetes`

### Databases (3 tests)

| Query | Expected Tag |
|---|---|
| `database dashboards` | `database` |
| `postgres dashboards` | `postgresql` |
| `redis dashboards` | `redis` |

### Observability Signals (4 tests)

| Query | Expected Tag |
|---|---|
| `show loki dashboards` | `loki` |
| `mimir dashboards` | `mimir` |
| `tempo dashboards` | `tempo` |
| `pyroscope dashboards` | `pyroscope` |

### SRE Patterns (3 tests)

| Query | Expected Tag |
|---|---|
| `SLO dashboards` | `slo` |
| `performance dashboards` | `performance` |
| `error dashboards` | `errors` |

### Compliance / Security (2 tests)

| Query | Expected Tag |
|---|---|
| `security dashboards` | `security` |
| `PCI dashboards` | `pci` |

### Dashboard Levels (2 tests)

| Query | Expected Tag |
|---|---|
| `show executive dashboards` | `executive` |
| `L3 dashboards` | `l3` |

### Cost / Capacity (2 tests)

| Query | Expected Tag |
|---|---|
| `cost dashboards` | `cost` |
| `capacity dashboards` | `capacity` |

### Network / Storage (2 tests)

| Query | Expected Tag |
|---|---|
| `network dashboards` | `network` |
| `storage dashboards` | `storage` |

### Service-specific Searches (3 tests)

| Query | Expected Tool | Query Arg |
|---|---|---|
| `payment-service dashboards` | `search_dashboards` | `payment-service` |
| `dashboards for api-gateway` | `search_dashboards` | `api-gateway` |
| `dashboards for user-svc` | `search_dashboards` | `user-svc` |

### Regression Tests (4 tests)

| Query | Expected Tool |
|---|---|
| `list all dashboards` (plain) | `list_dashboards` |
| `search dashboards aks` | `search_dashboards` |
| `list datasources` | `list_datasources` |
| `check grafana health` | `health_check` |

### Real-data validation

Against 113 real Grafana dashboards:
- AKS → 6 · Azure → 24 · OCI → 22 · Kubernetes → 11
- Loki → 5 · Mimir → 7 · Tempo → 7 · Pyroscope → 1
- Security → 4 · SLO → 8 · Cost → 5 · Database → 5
- Network → 2 · Storage → 2

### Manual validation
```bash
# Category filter returns ONLY matching tag
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"list AKS dashboards"}],"stream":true}' \
  | grep "tool_start"
# Expected: "arguments":{"tags":["aks"]}
```

---

## Bug Fixes Log

### Bug #1 — Intent Pattern Ordering
**Symptom:** `"show firing alerts"` matched `list_alert_rules` (wrong).
**Fix:** Reordered `INTENTS` list — specific patterns before generic ones.
**Fixed in:** `orchestrator/intents.py`

### Bug #2 — Unhandled Exception on Unknown MCP Server
**Symptom:** POST with unknown `server_name` returned HTTP 500 text.
**Fix:** Wrapped `call_tool` in try/except; returns `{ok:false, error}` JSON.
**Fixed in:** `orchestrator/routers/mcp.py`

### Bug #3 — SSE CRLF Parsing
**Symptom:** Chat bubble rendered empty even though server streamed 113 dashboards.
**Cause:** `sse-starlette` uses `\r\n\r\n` as frame separator; widget looked for `\n\n`.
**Fix:** Normalize CRLF → LF before parsing.
**Fixed in:** `o11ybot-widget.js`

### Bug #4 — Category Keyword Collision ("board")
**Symptom:** `"PCI dashboards"` matched Executive category.
**Cause:** Executive keywords included `"board"` which matched `"dashboard"`.
**Fix:** Removed overly-generic keywords.
**Fixed in:** `orchestrator/categories.py`

### Bug #5 — O11yBot MCP Tag Filter AND Semantics
**Symptom:** `"kubernetes dashboards"` returned 0 results despite 11 tagged `kubernetes`.
**Cause:** O11yBot MCP uses AND logic for tags; we sent `["kubernetes","k8s"]` needing BOTH tags.
**Fix:** Send only primary (first) tag from each category.
**Fixed in:** `orchestrator/intents.py`

### Bug #6 — Category Hijacked Explicit Search
**Symptom:** `"search dashboards aks"` routed to category filter instead of `search_dashboards`.
**Cause:** Category detection ran before intent matching.
**Fix:** Added priority-0 "starts with search" check before category lookup.
**Fixed in:** `orchestrator/intents.py`

---

## Adding a New Test

### New intent pattern

1. Add pattern to `orchestrator/intents.py` `INTENTS` list (remember: specific before generic)
2. Add formatter if needed
3. Add test case in `tests/suite2-intents.sh`:
   ```bash
   test_intent "my query" "my query" "expected_tool_name"
   ```

### New category

1. Add entry to `orchestrator/categories.py` `CATEGORIES` dict:
   ```python
   "my_cat": {
     "label": "My Category",
     "tags": ["primary_tag", "secondary"],
     "folder_hints": [],
     "keywords": ["my cat", "other term"],
   }
   ```
2. Add test case in `tests/suite7-categories.sh`:
   ```bash
   test_category "My Cat" "my cat dashboards" "primary_tag"
   ```

### New API endpoint

1. Implement in `orchestrator/routers/*.py`
2. Wire in `orchestrator/main.py`
3. Add curl test to `tests/suite1-api.sh`
4. Add integration test to `tests/suite4-integration.js`

### New UI widget behavior

1. Update `o11ybot-widget.js`
2. Copy to `dist/o11ybot-widget.js`
3. Add SSE-level test in `tests/suite3-widget.js` using Node.js http module

### New prompt category

1. Add to `orchestrator/prompts.py` `QueryType` + profile
2. Add classifier rule in `classify_query()`
3. Add system prompt constant
4. Add few-shot examples
5. Add test in `tests/suite6-prompts.js`

---

## Continuous Verification

Run before every deploy:
```bash
./tests/preflight.sh && ./tests/run-all-tests.sh
```

Expected:
```
Suite 1 Results: 17 passed, 0 failed   (API endpoints)
Suite 2 Results: 19 passed, 0 failed   (Intent matcher)
Suite 3 Results: 22 passed, 0 failed   (UI Widget / SSE)
Suite 4 Results: 18 passed, 0 failed   (Integration / E2E)
Suite 5 Results: 22 passed, 0 failed   (Negative / Errors)
Suite 6 Results: 18 passed, 0 failed   (Prompt Engineering)
Suite 7 Results: 31 passed, 0 failed   (Category Intents)
TOTAL:          160 passed, 0 failed
```

See also: **[docs/VALIDATION.md](VALIDATION.md)** — end-to-end validation scenarios with expected outputs.
