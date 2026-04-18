# O11yBot Testing Guide

Complete testing documentation for the O11yBot Grafana chatbot plugin.

## Quick Start

```bash
cd /Volumes/Gopalmac/Gopal-aiops/ollychat-app/tests
./run-all-tests.sh        # Run all 94 tests across 5 suites
./run-suite.sh 1          # Run only Suite 1 (API)
./run-suite.sh 2          # Run only Suite 2 (Intents)
./run-suite.sh 3          # Run only Suite 3 (UI Widget)
./run-suite.sh 4          # Run only Suite 4 (Integration)
./run-suite.sh 5          # Run only Suite 5 (Negative)
```

## Architecture Under Test

```
Browser (Grafana :3200)
  │ inject widget via custom index.html
  ↓
O11yBot Widget (JavaScript)
  │ POST /api/v1/chat (SSE streaming)
  ↓
Orchestrator (Python FastAPI :8000)
  │ Intent matching → MCP routing → Ollama fallback
  ├──→ Ollama LLM (:11434, qwen2.5:0.5b)
  └──→ Bifrost MCP Server (:8765)
           │ REST bridge /api/tools/call
           ↓
         Grafana API (:3200)
```

## Pre-requisites

All containers must be running:
```bash
docker ps --filter "name=ollychat"
# Expected: ollychat-orchestrator, ollychat-ollama, ollychat-otel-collector,
#           ollychat-mimir, ollychat-loki, ollychat-tempo

docker ps --filter "name=grafana-executive-dashboards"
# Expected: grafana-executive-dashboards (Up)

curl -s http://localhost:8765/api/tools >/dev/null && echo "Bifrost OK"
# Expected: Bifrost OK (or restart: cd ../Bifrost && .venv/bin/grafana-mcp serve --port 8765 &)
```

## Endpoints Reference

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
| `:8765/api/tools` | GET | Bifrost tool catalog |
| `:8765/api/tools/call` | POST | Bifrost tool invocation |
| `:3200/api/plugins/gopal-ollychat-app/settings` | GET | Plugin config |
| `:3200/public/plugins/gopal-ollychat-app/o11ybot-widget.js` | GET | Widget JS |

---

## Test Suite 1: API Endpoints (13 tests)

Validates that every REST endpoint responds correctly.

| # | Test | Endpoint | Expected |
|---|---|---|---|
| T1 | Orchestrator health | `GET /api/v1/health` | `{"status":"healthy"}` |
| T2 | Models list | `GET /api/v1/models` | Array of models |
| T3 | MCP servers | `GET /api/v1/mcp/servers` | bifrost-grafana status=connected, 16 tools |
| T4 | MCP tools | `GET /api/v1/mcp/tools` | 16 tools |
| T5 | Skills list | `GET /api/v1/skills` | 3 default skills |
| T6 | Rules list | `GET /api/v1/rules` | 3 default rules |
| T7 | PII scan | `POST /api/v1/guardrails/scan` | Detects email + SSN |
| T8 | Tool call | `POST /api/v1/mcp/tools/call` | Returns dashboards |
| T9 | CORS preflight | `OPTIONS /api/v1/chat` | `Access-Control-Allow-Origin: http://localhost:3200` |
| T10 | Grafana | `GET :3200/api/health` | HTTP 200 |
| T11 | Widget JS | `GET :3200/public/plugins/.../o11ybot-widget.js` | HTTP 200 |
| T12 | Plugin enabled | `GET :3200/api/plugins/gopal-ollychat-app/settings` | `enabled: true` |
| T13 | Widget injection | `GET :3200/` | Contains `o11ybot-widget` script |
| T14 | Bifrost direct | `GET :8765/api/tools` | 16 tools |

### Manual curl commands

```bash
# T1: Health
curl http://localhost:8000/api/v1/health

# T3: MCP servers
curl http://localhost:8000/api/v1/mcp/servers | jq

# T7: PII scan
curl -X POST http://localhost:8000/api/v1/guardrails/scan \
  -H "Content-Type: application/json" \
  -d '{"text":"Email: user@test.com, SSN: 123-45-6789"}' | jq

# T8: Direct MCP tool call
curl -X POST http://localhost:8000/api/v1/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"server_name":"bifrost-grafana","tool_name":"list_dashboards","arguments":{}}' | jq
```

---

## Test Suite 2: Intent Matcher (19 tests)

Validates that natural-language queries route to correct MCP tools.

| # | Query | Expected Tool |
|---|---|---|
| 1 | "list all Grafana dashboards" | `list_dashboards` |
| 2 | "show dashboards" | `list_dashboards` |
| 3 | "all dashboards" | `list_dashboards` |
| 4 | "list datasources" | `list_datasources` |
| 5 | "show all data sources" | `list_datasources` |
| 6 | "check datasource health" | `list_datasources` |
| 7 | "list all alerts" | `list_alert_rules` |
| 8 | "show firing alerts" | `list_alert_instances` |
| 9 | "active alerts" | `list_alert_instances` |
| 10 | "alert instances" | `list_alert_instances` |
| 11 | "list all folders" | `list_folders` |
| 12 | "check grafana health" | `health_check` |
| 13 | "grafana status" | `health_check` |
| 14 | "grafana version" | `health_check` |
| 15 | "health check" | `health_check` |
| 16 | "mcp server info" | `get_server_info` |
| 17 | "bifrost info" | `get_server_info` |
| 18 | "search dashboards aks" | `search_dashboards` |
| 19 | "list users" | `list_users` |

### Manual test

```bash
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"list all dashboards"}],"stream":true}'
# Look for: data: {"type":"tool_start","name":"list_dashboards",...}
```

---

## Test Suite 3: UI Widget / SSE Parser (22 tests)

Simulates the exact browser widget behavior to catch streaming issues.

### What it checks

1. **HTTP Response**
   - Status 200
   - Content-Type: `text/event-stream`
   - CORS header echoes origin

2. **SSE Event Types** (5 total)
   - `tool_start` — when an intent triggers a tool
   - `tool_result` — tool call completed
   - `text` — streaming text content
   - `usage` — token counts and cost
   - `done` — stream terminator

3. **Content Parsing**
   - Content length > 500 bytes
   - Markdown bold (`**text**`) present
   - Markdown links (`[text](url)`) present

4. **CRLF Line Ending Fix**
   - sse-starlette emits `\r\n\r\n` frame separators
   - Widget normalizes to `\n\n` before parsing
   - Expected: 500+ events parsed per query

5. **Multi-query Isolation**
   - Sequential queries don't contaminate each other
   - State is clean between requests

### Known issue fixed

Before the fix, widget parsed `\n\n` directly → missed ALL events because server emits `\r\n\r\n`. Now: `buf = buf.replace(/\r\n/g, "\n")` before parsing.

---

## Test Suite 4: Integration (18 tests)

End-to-end tests covering the full request chain.

### Key tests

- **E2E flow**: Chat query → Intent match → MCP call → Bifrost → Grafana → 113 dashboards returned
- **User identity propagation**: `X-Grafana-User` header reaches orchestrator logs
- **MCP → Grafana chain**: Bifrost `health_check` returns real Grafana v11.6.4
- **Role metadata**: All 16 tools have `minRole`, 2 admin-only tools
- **Plugin registration**: 6 pages registered (Chat, Investigate, Skills, MCP, Rules, Config)
- **Multi-turn conversation**: History passed correctly
- **Dashboard count consistency**: MCP and Grafana API both return 113

---

## Test Suite 5: Negative / Error Cases (22 tests)

| # | Test | Expected |
|---|---|---|
| T1 | Invalid tool name | `{ok:false, error:"..."}` |
| T2 | Invalid server name | `{ok:false, error:"..."}` (not 500) |
| T3 | RBAC block | viewer role can't call `list_users` → `PermissionError` |
| T4 | Empty messages | HTTP 200 graceful |
| T5 | Malformed schema | HTTP 422 validation |
| T6 | Non-intent query | Falls through to Ollama LLM |
| T7 | Skills CRUD | Create + delete roundtrip |
| T8 | Rules CRUD | Create + delete roundtrip |
| T9 | Clean text PII scan | `has_pii: false` |
| T10 | Multi-type PII | Detects 3+ types (email, ssn, api_key) |
| T11 | Concurrent requests | 5 parallel all succeed |
| T12 | Large payload | 10KB message accepted |
| T13 | Unicode/emoji | 🎉 Japanese 日本語 accepted |

---

## Bug Fixes Log

### Bug #1 — Intent Pattern Ordering

**Symptom:** Queries like "show firing alerts" were matching `list_alert_rules` instead of `list_alert_instances`.

**Cause:** Generic patterns registered before specific ones. Python iterates the `INTENTS` list in order.

**Fix:** Reordered patterns by specificity:
1. Most specific (MCP info) → first
2. Specific variants (search, firing alerts) → before generic
3. Most generic (health status) → last

Location: `orchestrator/intents.py` `INTENTS` list.

### Bug #2 — Unhandled Exception in MCP Router

**Symptom:** POSTing to `/api/v1/mcp/tools/call` with unknown `server_name` returned HTTP 500 `"Internal Server Error"` text.

**Cause:** `RuntimeError: MCP server X not connected` uncaught.

**Fix:** Wrapped in try/except in `routers/mcp.py`. Now returns `{ok: false, error: "..."}` JSON.

### Bug #3 — CRLF Line Endings in SSE Parser

**Symptom:** O11yBot chat bubble showed empty content even though server was sending data correctly.

**Cause:** `sse-starlette` emits frames separated by `\r\n\r\n` (CRLF), but widget parser used `indexOf("\n\n")` which never matched.

**Fix:** Added `buf = buf.replace(/\r\n/g, "\n")` normalization before parsing.

Location: `o11ybot-widget.js` line ~330.

---

## How to Add a New Test

### For a new intent pattern

1. Add the pattern to `orchestrator/intents.py` `INTENTS` list
2. Add a formatter function if the tool returns new data
3. Add a test case to `tests/suite2-intents.sh`:
   ```bash
   test_intent "my new query" "my new query" "expected_tool_name"
   ```

### For a new API endpoint

1. Implement in `orchestrator/routers/*.py`
2. Wire in `orchestrator/main.py`
3. Add curl test to `tests/suite1-api.sh`
4. Add integration test to `tests/suite4-integration.js`

### For a new UI widget behavior

1. Update `o11ybot-widget.js`
2. Copy to `dist/o11ybot-widget.js`
3. Add SSE-level test to `tests/suite3-widget.js` using Node.js http module

---

## Continuous Verification

Run before every deploy:
```bash
./tests/run-all-tests.sh
```

Expected output:
```
Suite 1 Results: 17 passed, 0 failed   (API endpoints)
Suite 2 Results: 19 passed, 0 failed   (Intent matcher)
Suite 3 Results: 22 passed, 0 failed   (UI Widget / SSE)
Suite 4 Results: 18 passed, 0 failed   (Integration / E2E)
Suite 5 Results: 22 passed, 0 failed   (Negative / Errors)
TOTAL: 98/98 passed
```
