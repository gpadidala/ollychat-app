<p align="center">
  <img src="docs/assets/o11ybot-logo.svg" alt="O11yBot" width="100" />
</p>

<h1 align="center">O11yBot</h1>

<p align="center">
  <b>The floating AI chatbot for Grafana — on every page, every dashboard.</b><br/>
  <sub>Ask about metrics, logs, traces, dashboards, alerts in natural language.</sub>
</p>

<p align="center">
  <a href="#-demo">Demo</a> •
  <a href="#-why-o11ybot">Why</a> •
  <a href="#-features">Features</a> •
  <a href="docs/INSTALLATION.md">Install</a> •
  <a href="docs/DEPLOYMENT.md">Deploy</a> •
  <a href="docs/USE_CASES.md">Use cases</a> •
  <a href="docs/API_REFERENCE.md">API</a> •
  <a href="docs/ARCHITECTURE.md">Architecture</a> •
  <a href="https://github.com/gpadidala/ollychat-app/issues">Report bug</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-160%2F160_passing-22c55e?style=flat-square" alt="Tests"/>
  <img src="https://img.shields.io/badge/grafana-10.0%2B-F46800?style=flat-square" alt="Grafana"/>
  <img src="https://img.shields.io/badge/python-3.12%2B-3776AB?style=flat-square" alt="Python"/>
  <img src="https://img.shields.io/badge/MCP-53_tools-8b5cf6?style=flat-square" alt="MCP"/>
  <img src="https://img.shields.io/badge/LLM-self--hosted_or_cloud-f59e0b?style=flat-square" alt="LLM"/>
  <img src="https://img.shields.io/badge/license-Apache_2.0-blue?style=flat-square" alt="License"/>
  <img src="https://img.shields.io/badge/PRs-welcome-green?style=flat-square" alt="PRs welcome"/>
</p>

---

## 🎬 Demo

<p align="center">
  <img src="docs/assets/o11ybot-demo.gif" alt="O11yBot in action" width="900"/>
</p>

<p align="center"><sub>
  <b>o11Y Place Home</b> → <b>user asks "list dashboards"</b> → <b>streams 113 real results</b> → <b>navigates to AKS dashboard</b> → <b>bot follows!</b> → <b>asks "check grafana health"</b> → <b>goes to Logs</b> → <b>maximizes</b> → <b>fullscreen advantages</b>
</sub></p>

### 📸 Screenshots — every page, same bot

<table>
<tr>
<td align="center" width="50%">
  <img src="docs/assets/screenshot-home-bubble.png" alt="O11yBot on Grafana Home" width="100%"/>
  <br/><sub><b>🏠 Home page</b> — "Welcome to o11Y Place" · pulsing bubble</sub>
</td>
<td align="center" width="50%">
  <img src="docs/assets/screenshot-home-chat.png" alt="O11yBot chat on Home" width="100%"/>
  <br/><sub><b>💬 Chat on Home</b> — 113 dashboards streamed in 114ms</sub>
</td>
</tr>
<tr>
<td align="center" width="50%">
  <img src="docs/assets/screenshot-aks-bubble.png" alt="O11yBot on AKS dashboard" width="100%"/>
  <br/><sub><b>📊 AKS dashboard</b> — bot follows across pages · no context switch</sub>
</td>
<td align="center" width="50%">
  <img src="docs/assets/screenshot-aks-chat.png" alt="O11yBot health check on AKS" width="100%"/>
  <br/><sub><b>💓 Health check</b> — version 11.6.4 · 3 datasources · 42ms</sub>
</td>
</tr>
<tr>
<td align="center" width="50%">
  <img src="docs/assets/screenshot-logs-maximized.png" alt="Maximized on Logs page" width="100%"/>
  <br/><sub><b>⚡ Maximized on Logs</b> — 75% viewport with blur backdrop</sub>
</td>
<td align="center" width="50%">
  <img src="docs/assets/screenshot-fullscreen.png" alt="Fullscreen advantages" width="100%"/>
  <br/><sub><b>⛶ Fullscreen</b> — all advantages at a glance</sub>
</td>
</tr>
</table>

### 🎛️ 4 Window Modes

Click the window controls in the chat header:
- **Minimize (−)** — collapse to the floating bubble, keep history
- **Maximize (□)** — overlay 75% of the viewport with blur backdrop
- **Fullscreen (⛶)** — full 100vw × 100vh browser takeover
- **Close (×)** — same as minimize
- Press **Esc** to exit fullscreen/maximized

---

## 💡 Why O11yBot

### The Problem
Grafana has incredible observability data, but to get answers you need to:
- Remember which dashboard (out of 100+) has what you need
- Know the right PromQL / LogQL / TraceQL syntax
- Click through folders to find alerts
- Switch context between tools

### The Solution
Chat with your observability — in the same UI, on every page.

```
💬 "list all dashboards"        → 113 dashboards across 15 folders
💬 "check grafana health"        → Version 11.6.4, DB: ok
💬 "show firing alerts"          → 2 firing, 3 pending
💬 "search dashboards postgres"  → 3 matches, direct links
💬 "list datasources"            → Mimir, Loki, Tempo
💬 "what is PromQL?"             → LLM answers in plain English
```

**No context switching. No syntax memorization. Just ask.**

---

## ✨ Features

| | Feature | |
|---|---|---|
| 🟠 | **Always on** — floating bubble on every Grafana page | |
| 🖱️ | **Draggable** — move to any corner, stays there across navigation | |
| 🖥️ | **4 window modes** — FAB / Normal / Maximized / Fullscreen | |
| ⌨️ | **Keyboard** — `Enter` to send, `Esc` to exit fullscreen | |
| 👤 | **Per-user history** — isolated by Grafana login, in `localStorage` | |
| 🔌 | **16 MCP tools** — dashboards, datasources, alerts, folders, users, search | |
| 🧠 | **LLM flexibility** — Ollama (self-hosted), OpenAI, Anthropic — swap via env | |
| 🔐 | **RBAC-aware** — viewer / editor / admin enforced at MCP layer | |
| 🛡️ | **PII detection** — 15 patterns (email, SSN, API keys, AWS, etc.) | |
| ⚡ | **Intent matcher** — sub-second, $0 tool calls (no LLM roundtrip) | |
| 📊 | **Full observability** — OpenTelemetry → LGTM stack | |
| ✅ | **98 automated tests** — documented, production-ready | |

### The killer feature: Intent Matcher

Traditional LLM function calling requires smart models (GPT-4 / Claude). O11yBot includes a **regex-based intent matcher** that routes common queries to MCP tools **before** the LLM runs.

- ⚡ **~114ms** to list 113 dashboards (measured, no LLM in the hot path)
- 💰 **$0 cost** for matched queries (no LLM tokens burned)
- 🎯 **Deterministic** — `"list dashboards"` always calls `list_dashboards`
- 🪶 **Works with tiny LLMs** — a 500MB local model is enough; large models are optional

LLM fallback only runs for open-ended questions.

---

## 📦 Installation Guide

Two paths — pick one. Full step-by-step is in **[docs/INSTALLATION.md](docs/INSTALLATION.md)**.

### Prerequisites
- **Docker + Docker Compose** (Engine ≥ 24, Compose ≥ v2.20)
- **An existing Grafana 10.0+ instance** (OSS or Enterprise) — *or* use the bundled one
- **Admin access to Grafana** — to create three service-account tokens

### Option A — 60-second local demo (bundled stack)

```bash
git clone https://github.com/gpadidala/ollychat-app.git
cd ollychat-app
cp .env.example .env
docker compose up -d
```

Brings up Grafana on `http://localhost:3002` with the plugin already mounted
and a bundled LGTM stack. Zero SA tokens needed for the demo.

Open Grafana → click the orange bubble bottom-right → ask **`list all dashboards`**.

### Option B — Production install (your own Grafana)

Four steps — complete walkthrough in [docs/INSTALLATION.md](docs/INSTALLATION.md).

1. **Create 3 SA tokens** in the target Grafana (viewer / editor / admin roles) — or use the one-liner loop in [INSTALLATION.md §3c](docs/INSTALLATION.md#3c-cli-shortcut-oss--enterprise-grafana-api).

2. **Configure `.env`** — point at your Grafana:

   ```env
   GRAFANA_URL=https://grafana.yourco.com
   GRAFANA_VIEWER_TOKEN=glsa_xxx
   GRAFANA_EDITOR_TOKEN=glsa_yyy
   GRAFANA_ADMIN_TOKEN=glsa_zzz
   ```

3. **Install the plugin** into your Grafana host — [INSTALLATION.md §5](docs/INSTALLATION.md#5-install-the-plugin) covers OSS, Enterprise, Helm, systemd.

4. **Boot the stack + register MCP**:

   ```bash
   docker compose up -d
   curl -X POST http://localhost:8000/api/v1/mcp/servers \
     -H 'Content-Type: application/json' \
     -d '{"name":"bifrost-grafana","url":"http://ollychat-mcp:8765","enabled":true}'
   ```

Expected response: `{"ok":true,"server":{"status":"connected","toolCount":53}}`.

### Verify with the test suite

```bash
cd tests
./preflight.sh          # service health
./run-all-tests.sh      # 160 assertions across 8 suites
```

Expected tail: `RESULT: ALL SUITES PASSED`. See [docs/VALIDATION.md](docs/VALIDATION.md)
for a 9-command post-deploy smoke test covering every critical code path.

### Configuring the LLM (admin-only)

Edit `.env`:

```bash
# Dev (self-hosted, free)
OLLYCHAT_DEFAULT_MODEL=qwen2.5:0.5b

# Prod — OpenAI
OLLYCHAT_DEFAULT_MODEL=gpt-4o
OLLYCHAT_OPENAI_API_KEY=sk-...

# Prod — Anthropic
OLLYCHAT_DEFAULT_MODEL=claude-sonnet-4-6
OLLYCHAT_ANTHROPIC_API_KEY=sk-ant-...
```

Then: `docker restart ollychat-orchestrator`

---

## ⚙️ Configuration reference

Every knob is a env var — no config files, no secrets in git.

### Target Grafana (required)

| Var | Purpose | Example |
|---|---|---|
| `GRAFANA_URL` | Base URL of the target Grafana | `https://grafana.yourco.com` |
| `GRAFANA_VIEWER_TOKEN` | SA token, Viewer role | `glsa_…` |
| `GRAFANA_EDITOR_TOKEN` | SA token, Editor role | `glsa_…` |
| `GRAFANA_ADMIN_TOKEN` | SA token, Admin role | `glsa_…` |
| `GRAFANA_TOKEN` | Single-token fallback for demos (used for every role) | `glsa_…` |
| `GRAFANA_TLS_VERIFY` | Verify Grafana TLS cert | `true` (default) |
| `GRAFANA_TIMEOUT_S` | Per-request timeout seconds | `30` |
| `MCP_SERVER_PORT` | Port the MCP binds to | `8765` |

### Orchestrator / LLM

| Var | Purpose |
|---|---|
| `OLLYCHAT_DEFAULT_MODEL` | `qwen2.5:0.5b` · `gpt-4o` · `claude-sonnet-4-6` |
| `OLLYCHAT_ANTHROPIC_API_KEY` · `OLLYCHAT_OPENAI_API_KEY` · `OLLYCHAT_GOOGLE_API_KEY` | Cloud LLM keys |
| `OLLYCHAT_OLLAMA_BASE_URL` | Local LLM endpoint |
| `OLLYCHAT_DEFAULT_MAX_TOKENS` · `OLLYCHAT_DEFAULT_TEMPERATURE` | Generation config |
| `OLLYCHAT_PII_ENABLED` · `OLLYCHAT_PII_MODE` | PII scanner (`redact` / `block` / `log`) |
| `OLLYCHAT_BIFROST_URL` | Where the orchestrator finds the MCP server (default: `http://ollychat-mcp:8765`) |
| `OLLYCHAT_OTEL_EXPORTER_ENDPOINT` | OTLP collector endpoint |

Full list with defaults in [.env.example](.env.example).

---

## 📡 API Guide

Base URL: `http://localhost:8000`

### `POST /api/v1/chat` — Stream a chat response

The primary endpoint. Streams as Server-Sent Events (SSE) with `text/event-stream` content type.

**Request:**
```bash
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-User: admin" \
  -d '{
    "messages": [{"role": "user", "content": "list all dashboards"}],
    "max_tokens": 4096,
    "temperature": 0.2,
    "stream": true
  }'
```

**Response (SSE event stream):**
```
data: {"type":"tool_start","id":"abc","name":"list_dashboards","input":{}}

data: {"type":"tool_result","id":"abc","result":{"ok":true},"durationMs":114}

data: {"type":"text","delta":"**Found 113 dashboards:**\n\n- **AKS..."}

data: {"type":"text","delta":" — folder: Azure_..."}

data: {"type":"usage","usage":{"promptTokens":0,"completionTokens":0,"totalTokens":0},"costUsd":0.0}

data: {"type":"done"}
```

### `GET /api/v1/health` — Health check
```bash
curl http://localhost:8000/api/v1/health
# {"status":"healthy","service":"ollychat-orchestrator","version":"1.0.0"}
```

### MCP Server Management

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/mcp/servers` | List connected MCP servers |
| `POST` | `/api/v1/mcp/servers` | Register a new MCP server |
| `DELETE` | `/api/v1/mcp/servers/{name}` | Remove an MCP server |
| `POST` | `/api/v1/mcp/servers/{name}/toggle` | Enable / disable |

Register the MCP server:
```bash
curl -X POST http://localhost:8000/api/v1/mcp/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "bifrost-grafana",
    "url": "http://ollychat-mcp:8765",
    "transport": "sse",
    "auth_method": "none"
  }'
```

### MCP Tools

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/mcp/tools` | List all 16 tools from all servers |
| `POST` | `/api/v1/mcp/tools/call` | Execute a tool directly |

Call a tool:
```bash
curl -X POST http://localhost:8000/api/v1/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "ollychat-mcp-grafana",
    "tool_name": "list_dashboards",
    "arguments": {}
  }'
# {"ok":true,"data":[...113 items...],"duration_ms":114}
```

### Skills & Rules CRUD

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/skills` | List skills |
| `POST` | `/api/v1/skills` | Create skill |
| `PUT` | `/api/v1/skills/{id}` | Update skill |
| `DELETE` | `/api/v1/skills/{id}` | Delete skill |
| `GET` | `/api/v1/skills/search?q=<query>` | Keyword search |
| `GET` | `/api/v1/rules` | List rules |
| `POST` | `/api/v1/rules` | Create rule |
| `PUT` | `/api/v1/rules/{id}` | Update rule |
| `DELETE` | `/api/v1/rules/{id}` | Delete rule |

### Guardrails

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/guardrails/scan` | Detect PII in text |

```bash
curl -X POST http://localhost:8000/api/v1/guardrails/scan \
  -H "Content-Type: application/json" \
  -d '{"text":"Contact: user@test.com, SSN: 123-45-6789"}'
# {
#   "has_pii": true,
#   "redacted_text": "Contact: [EMAIL_REDACTED], SSN: [SSN_REDACTED]",
#   "matches": [...]
# }
```

### Intent Matcher — supported queries

| Query Pattern | MCP Tool |
|---|---|
| `list/show/all dashboards` | `list_dashboards` |
| `search dashboards <query>` | `search_dashboards` |
| `list/show datasources` | `list_datasources` |
| `check datasource health` | `list_datasources` |
| `list all alerts` | `list_alert_rules` |
| `firing/active alerts` | `list_alert_instances` |
| `list folders` | `list_folders` |
| `list users` (admin) | `list_users` |
| `grafana health/status/version` | `health_check` |
| `mcp/ollychat-mcp info` | `get_server_info` |

Full API reference: **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)**

---

## 🏗️ Architecture

<p align="center">
  <img src="docs/assets/architecture.svg" alt="O11yBot Architecture" width="1100"/>
</p>

### Request flow (step-by-step)

1. **User** types query in floating widget → Browser sends `POST /api/v1/chat` with SSE
2. **Widget** adds `X-Grafana-User` header, JSON body with messages
3. **Orchestrator pipeline**:
   1. CORS + user identity check
   2. PII scan (redact before LLM)
   3. **Intent matcher** — 60+ regex patterns → MATCH or LLM fallback
   4. If MATCH → call MCP tool via HTTP bridge
   5. Format result as markdown, stream back as SSE
4. **O11yBot MCP server** receives tool call → enforces RBAC (viewer / editor / admin)
5. MCP server calls **Grafana REST API** with the role-appropriate SA token
6. Grafana returns data → MCP → Orchestrator → Widget
7. Widget renders markdown in the bubble — streaming text, links, tool metadata

### Key design decisions

- **Intent matcher before LLM** — reliable tool calls even with 500MB local models
- **Widget injection via custom index.html** — works on every page without touching Grafana core
- **Per-user localStorage** — no server-side session needed, privacy by default
- **SSE over WebSockets** — simpler, works through proxies, no keepalive issues
- **MCP REST bridge** — orchestrator doesn't need MCP SDK

Full details: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

---

## ✅ Testing

**98 automated tests** across 5 suites. Run anytime:

```bash
cd tests
./preflight.sh         # verify services are up
./run-all-tests.sh     # full suite
```

### Test Suites

| Suite | Tests | Focus |
|---|---|---|
| **1. API Endpoints** | 17 | REST health, models, MCP, skills, rules, CORS, plugin registration |
| **2. Intent Matcher** | 19 | Every NL query → correct MCP tool |
| **3. UI Widget / SSE** | 22 | Event types, CRLF parsing, markdown, multi-query |
| **4. Integration E2E** | 18 | Full chain: widget → orchestrator → MCP → Grafana |
| **5. Negative** | 22 | RBAC, errors, Unicode, 10KB payloads, 5x concurrent |

### Run individual suites

```bash
./tests/suite1-api.sh              # 17 tests
./tests/suite2-intents.sh          # 19 tests
node tests/suite3-widget.js        # 22 tests
node tests/suite4-integration.js   # 18 tests
node tests/suite5-negative.js      # 22 tests
```

Full testing guide: **[docs/TESTING.md](docs/TESTING.md)**

---

## 📚 Documentation

Ordered by typical journey — start at 0.

| # | Doc | When to read it |
|---|---|---|
| 0 | **[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)** | Folder tree + per-file purpose |
| 1 | **[docs/INSTALLATION.md](docs/INSTALLATION.md)** | Zero → boot. OSS + Enterprise paths, SA tokens, env vars, first smoke test |
| 2 | **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Production — Docker Compose, Kubernetes/Helm, bare-metal systemd, each with validation + rollback |
| 3 | **[docs/VALIDATION.md](docs/VALIDATION.md)** | 9-command post-deploy smoke test + 20 end-to-end scenarios |
| 4 | **[docs/USE_CASES.md](docs/USE_CASES.md)** | Full 53-tool capability matrix by role + example prompts |
| 5 | **[docs/ENTERPRISE.md](docs/ENTERPRISE.md)** | RBAC, self-observability, hardening, scaling |
| 6 | **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | System diagrams + data flow |
| 7 | **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** | REST endpoints, SSE event types, MCP tools |
| 8 | **[docs/RBAC.md](docs/RBAC.md)** | Role design + service-account setup |
| 9 | **[docs/TESTING.md](docs/TESTING.md)** | All 160 automated tests, expected outputs |
| — | **[docs/assets/RECORD_DEMO.md](docs/assets/RECORD_DEMO.md)** | How to record your own demo GIF |

---

## 🎯 Advanced capabilities

Everything O11yBot does end-to-end — no external product comparisons, just
what's in this repo.

- **Floating widget on every Grafana page** — FAB / Normal / Maximized / Fullscreen
- **53 MCP tools** covering dashboards, alerts, datasources, folders, teams,
  plugins, library panels, annotations, users, and service accounts
- **4 compound workflow tools** — `investigate_alert`, `correlate_signals`
  (Prometheus + Loki + Tempo in one call), `create_slo_dashboard`,
  `find_dashboards_using_metric`
- **Slot-filling wizards** for alert and dashboard creation — lists every
  datasource + folder so the user picks rather than the bot guessing
- **Metric discovery** before dashboard creation — queries the Prometheus
  datasource for the real metric names that exist, so panels never render
  "No data"
- **LLM-as-judge reranker** for fuzzy search results — top candidates get
  a relevance score and a one-line "why it fits" reason
- **Local fuzzy search** over every dashboard with typo-tolerant multi-keyword
  intersection (e.g. `oracle kpi dashbords`)
- **Regex intent matcher** routes common queries to the right MCP tool
  without an LLM round-trip — deterministic, cheap, works with tiny models
- **Self-owned MCP server** — no external MCP dependency; point `GRAFANA_URL`
  + role tokens at any Grafana and the stack runs
- **Role-based tokens** (viewer / editor / admin) enforced at the MCP layer
  before any Grafana API call
- **Self-observability** — `/metrics` endpoint exposes
  `ollychat_mcp_tool_calls_total`, `ollychat_mcp_tool_duration_seconds`,
  `ollychat_mcp_grafana_requests_total`, plus a structured `tool.call`
  audit log line per invocation
- **Per-user chat history** with multi-session support (VSCode-style tabs),
  isolated by Grafana username in `localStorage`
- **PII detection** with 15 patterns, redaction mode on by default
- **Streaming responses** via SSE with CRLF normalisation + graceful abort
- **160-test automated suite** across 8 suites (API, intents, widget parser,
  integration, negative, prompt engineering, categories, RBAC)
- **Authoring cookbooks** — PromQL, LogQL, TraceQL, SLO — static responses,
  no LLM tokens

---

## 🛣️ Roadmap

- [x] Floating widget on every Grafana page
- [x] Min / Max / Fullscreen / Close controls
- [x] Per-user chat history (localStorage)
- [x] MCP integration (16 Grafana tools)
- [x] Self-hosted + cloud LLM support
- [x] PII detection (15 patterns)
- [x] Intent matcher (no-LLM tool routing)
- [x] 98-test automated suite
- [x] Full documentation
- [ ] Investigation engine (multi-agent root cause analysis)
- [ ] Skills & Rules management UI (currently API-only)
- [ ] PostgreSQL persistence (currently in-memory)
- [ ] Slack bidirectional integration
- [ ] Grafana IRM webhook bridge
- [ ] Dashboard generation from prompt

---

## 🤝 Contributing

1. Fork the repo
2. Run `./tests/run-all-tests.sh` to baseline (must be 98/98 passing)
3. Make your changes
4. Add tests for new intent patterns in `orchestrator/intents.py`
5. Run tests again — all must pass
6. Open a PR with a clear description

---

## 📄 License

Apache 2.0 — use, modify, deploy, commercial, all fine.

---

## 🧱 Tech stack

<p align="center">
  <a href="https://grafana.com"><img src="https://img.shields.io/badge/Grafana-F46800?style=flat-square&logo=grafana&logoColor=white"/></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/Python_3.12-3776AB?style=flat-square&logo=python&logoColor=white"/></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white"/></a>
  <a href="https://www.docker.com"><img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white"/></a>
  <a href="https://react.dev"><img src="https://img.shields.io/badge/React_18-61DAFB?style=flat-square&logo=react&logoColor=black"/></a>
  <a href="https://www.typescriptlang.org"><img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white"/></a>
  <a href="https://ollama.com"><img src="https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white"/></a>
  <a href="https://www.anthropic.com"><img src="https://img.shields.io/badge/Anthropic-191717?style=flat-square&logo=anthropic&logoColor=white"/></a>
  <a href="https://openai.com"><img src="https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white"/></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-8b5cf6?style=flat-square"/></a>
  <a href="https://opentelemetry.io"><img src="https://img.shields.io/badge/OpenTelemetry-425CC7?style=flat-square&logo=opentelemetry&logoColor=white"/></a>
  <a href="https://prometheus.io"><img src="https://img.shields.io/badge/Prometheus-E6522C?style=flat-square&logo=prometheus&logoColor=white"/></a>
</p>

- **Python 3.12 + FastAPI** — orchestrator + MCP server, both async-native
- **httpx** with per-role token pooling — outbound Grafana API calls
- **Vanilla JS widget** — zero framework dependencies, loads on every Grafana page
- **React 18 + TypeScript** — optional plugin shell pages (Config, Investigate, Skills)
- **Model Context Protocol** — tool-calling contract; `/api/tools` + `/api/tools/call`
- **OpenTelemetry** — orchestrator emits traces + metrics to any OTLP collector
- **Prometheus client** — MCP exports `/metrics` for self-observability
- **Ollama / OpenAI / Anthropic / Google** — LLM backends, one env var to switch

---

## 🙏 Credits

- **[Grafana Labs](https://grafana.com)** — the observability platform everything plugs into
- **[Model Context Protocol](https://modelcontextprotocol.io)** — the open tool-calling standard
- **[Ollama](https://ollama.com)** — local LLM runtime that makes self-hosted LLMs painless
- **[FastAPI](https://fastapi.tiangolo.com)** + **[sse-starlette](https://github.com/sysid/sse-starlette)** — the async API layer
- **[Prometheus](https://prometheus.io)** + **[OpenTelemetry](https://opentelemetry.io)** — the observability substrate

---

<p align="center">
  <sub>If O11yBot saves your team time,&nbsp;<a href="https://github.com/gpadidala/ollychat-app">give it a ⭐ on GitHub</a>.</sub><br/><br/>
  <a href="https://github.com/gpadidala"><img src="https://img.shields.io/badge/GitHub-gpadidala-181717?style=flat-square&logo=github" alt="GitHub"/></a>
  &nbsp;
  <a href="https://github.com/gpadidala/ollychat-app/issues"><img src="https://img.shields.io/badge/Report_a_bug-EF4444?style=flat-square&logo=github" alt="Report a bug"/></a>
  &nbsp;
  <a href="https://github.com/gpadidala/ollychat-app/discussions"><img src="https://img.shields.io/badge/Ask_a_question-22c55e?style=flat-square&logo=github" alt="Discussions"/></a>
</p>

<p align="center">
  <sub>Built with ⚡ by <a href="https://github.com/gpadidala">Gopal</a></sub>
</p>
