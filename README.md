<p align="center">
  <img src="docs/assets/o11ybot-logo.svg" alt="O11yBot" width="100" />
</p>

<h1 align="center">O11yBot</h1>

<p align="center">
  <b>The floating AI chatbot for Grafana — on every page, every dashboard.</b><br/>
  <sub>Ask about metrics, logs, traces, dashboards, alerts — natively in Grafana UI.</sub>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#why-o11ybot">Why O11yBot</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="docs/TESTING.md">Testing</a> •
  <a href="docs/DEPLOYMENT.md">Deploy</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-98%2F98_passing-22c55e?style=flat-square" alt="Tests"/>
  <img src="https://img.shields.io/badge/grafana-11.x-F46800?style=flat-square" alt="Grafana"/>
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square" alt="Python"/>
  <img src="https://img.shields.io/badge/MCP-16_tools-8b5cf6?style=flat-square" alt="MCP"/>
  <img src="https://img.shields.io/badge/LLM-self--hosted_or_cloud-f59e0b?style=flat-square" alt="LLM"/>
  <img src="https://img.shields.io/badge/license-Apache_2.0-blue?style=flat-square" alt="License"/>
</p>

---

## Demo

<p align="center">
  <img src="docs/assets/o11ybot-demo.svg" alt="O11yBot Demo" width="900"/>
</p>

<p align="center"><sub>
  Orange bubble lives on every Grafana page · Ask a question · Real MCP tools run · Maximize · Fullscreen · Drag anywhere
</sub></p>

---

## Why O11yBot

### The problem
Grafana has amazing observability data. But to get answers you need to know:
- Which dashboard to open (out of 100+)
- The right PromQL / LogQL / TraceQL query
- How folders are organized
- What alerts are firing
- What's changed recently

That's context-switching overhead on top of an already-complex UI.

### The solution: chat with your observability
```
You: "list all alerts"
Bot: Found 12 alerts: 🔴 HighLatencyP99 (firing) · 🟡 DiskPressure (pending) · ✅ 10 more ok

You: "search dashboards postgres"
Bot: 3 dashboards matched: **Advanced PostgreSQL Monitoring — ESOBF Dev** · [Open dashboard]

You: "check grafana health"
Bot: Version 11.6.4 · Database: ✓ ok · 3 datasources connected (Mimir, Loki, Tempo)
```

No context switching. No PromQL memorization. Just ask.

---

## Features

### Floating on every page — like Grafana Assistant, but open-source

| Mode | Description |
|---|---|
| 🟠 **Bubble** | Always-on-top orange FAB, bottom-right (draggable to any corner) |
| 💬 **Normal** | 440×600 panel — resizable, repositionable |
| 🖥️ **Maximized** | 75% viewport overlay with blur backdrop |
| ⛶ **Fullscreen** | 100% browser takeover (ESC to exit) |
| ⚪ **Minimized** | Collapses to bubble, keeps history |

### 16 Grafana Tools via MCP ([Bifröst](https://github.com/gpadidala/Bifrost))

| Category | Tools |
|---|---|
| **Dashboards** | `list_dashboards` · `search_dashboards` · `get_dashboard` · `get_dashboard_panels` |
| **Datasources** | `list_datasources` · `get_datasource` · `query_datasource` |
| **Alerts** | `list_alert_rules` · `list_alert_instances` · `silence_alert` · `get_alert_rule` |
| **Folders** | `list_folders` |
| **Users (admin)** | `list_users` · `list_service_accounts` |
| **Meta** | `health_check` · `get_server_info` |

**RBAC-aware**: viewer / editor / admin roles enforced per tool at the MCP layer.

### LLM Flexibility — swap via one env var

```bash
# Dev: self-hosted, zero cost, works offline
OLLYCHAT_DEFAULT_MODEL=qwen2.5:0.5b     # 400MB, runs on any laptop
OLLYCHAT_DEFAULT_MODEL=llama3.2:latest  # 2GB, better reasoning

# Prod: OpenAI
OLLYCHAT_DEFAULT_MODEL=gpt-4o
OLLYCHAT_OPENAI_API_KEY=sk-...

# Prod: Anthropic
OLLYCHAT_DEFAULT_MODEL=claude-sonnet-4-6
OLLYCHAT_ANTHROPIC_API_KEY=sk-ant-...
```

👉 **Users never see the model selector.** Admin controls it centrally.

### Built-in Guardrails
- **PII detection** — 15 patterns (email, SSN, phone, credit cards, IPs, API keys: OpenAI/GitHub/Slack/AWS)
- **Redaction before LLM** — sensitive data never leaves your infra
- **CORS allowlist** — only your Grafana origin allowed
- **Role-based MCP access** — can't call admin tools as viewer

### Per-User Chat History
- Each Grafana user (`admin`, `jane.doe`, `oncall-engineer`) gets an **isolated** chat
- Stored in `localStorage` keyed by Grafana login
- No cross-user data leakage
- Survives page navigation, survives browser restart

### Deep Observability (turtles all the way down)
- Every chat request emits OpenTelemetry traces
- Tool calls tracked with `duration_ms`, success/failure, arguments hash
- Streams cost, token counts, and latency
- Forwards to your existing LGTM stack (Loki / Grafana / Tempo / Mimir)

---

## Advantages Over Alternatives

| Feature | O11yBot | Grafana Assistant | Generic ChatGPT plugin | Bare LLM |
|---|---|---|---|---|
| Floating on every page | ✅ | ✅ (paid) | ❌ | ❌ |
| Open source | ✅ | ❌ | varies | ✅ |
| Real MCP tool calls | ✅ (16) | ✅ | ❌ | ❌ |
| Self-hosted LLM option | ✅ (Ollama) | ❌ (cloud only) | ❌ | ✅ |
| User-isolated history | ✅ | ✅ | varies | ❌ |
| PII redaction | ✅ (15 patterns) | ✅ | rarely | ❌ |
| Intent matcher (no-LLM tool routing) | ✅ | ❌ | ❌ | ❌ |
| RBAC per tool | ✅ | ✅ | ❌ | ❌ |
| 98-test automated suite | ✅ | closed source | varies | ❌ |
| Works with 500MB local model | ✅ | ❌ | ❌ | ❌ |
| Deploy-anywhere (just mount 2 files) | ✅ | ❌ | ❌ | n/a |

### The killer feature: Intent Matcher
Traditional LLM function calling requires a smart model (GPT-4 / Claude). O11yBot includes a **regex-based intent matcher** that routes common queries to MCP tools **before** the LLM ever runs.

This means:
- ⚡ **Sub-second responses** — 114ms to list 113 dashboards
- 💰 **$0 cost** for tool calls (no LLM roundtrip)
- 🧪 **Deterministic** — "list all dashboards" *always* calls `list_dashboards`
- 🪶 **Works with tiny LLMs** — qwen2.5:0.5b doesn't need to understand function schemas

Fall through to LLM only happens for open-ended questions like "what is PromQL?"

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Node.js 20+ (for tests)
- An existing Grafana 10.x+ instance

### 1. Clone and boot the stack

```bash
git clone https://github.com/gpadidala/ollychat-app.git
cd ollychat-app
cp .env.example .env
docker compose up -d
```

This starts: orchestrator (:8000), Ollama (:11434), OTEL collector, Tempo, Mimir, Loki.

### 2. Install into your Grafana

Add to your Grafana's `docker-compose.yml`:

```yaml
services:
  grafana:
    environment:
      - GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=gopal-ollychat-app
    volumes:
      - /path/to/ollychat-app/dist:/var/lib/grafana/plugins/gopal-ollychat-app:ro
      - /path/to/ollychat-app/grafana-index.html:/usr/share/grafana/public/views/index.html:ro
```

Restart Grafana. That's it — the orange bubble appears on every page.

### 3. Start Bifröst MCP (Grafana tool bridge)

```bash
git clone https://github.com/gpadidala/Bifrost.git
cd Bifrost && python3 -m venv .venv && .venv/bin/pip install -e packages/core

# Create a Grafana SA token for Bifrost
# See docs/DEPLOYMENT.md for the curl commands

.venv/bin/grafana-mcp serve --port 8765 &
```

### 4. Wire it up

```bash
# Register MCP with orchestrator
curl -X POST http://localhost:8000/api/v1/mcp/servers \
  -H "Content-Type: application/json" \
  -d '{"name":"bifrost-grafana","url":"http://host.docker.internal:8765","transport":"sse","auth_method":"none"}'

# Enable the plugin
curl -X POST http://admin:admin@localhost:3200/api/plugins/gopal-ollychat-app/settings \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"pinned":true}'
```

### 5. Open Grafana → click the orange bubble → ask away 🎉

```
"list all Grafana dashboards"
"check grafana health"
"search dashboards postgres"
"list datasources"
"what's firing right now?"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser — Grafana UI (any page)                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  O11yBot Widget — floating overlay               │   │
│  │  Draggable · Resizable · Min/Max/Fullscreen      │   │
│  │  Per-user localStorage · SSE parser (CRLF-safe)  │   │
│  └───────────────────┬──────────────────────────────┘   │
└──────────────────────┼──────────────────────────────────┘
                       │ POST /api/v1/chat (SSE)
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Orchestrator (Python FastAPI, :8000)                   │
│                                                         │
│  Request Pipeline:                                      │
│    1. CORS + user identity check                        │
│    2. PII scan (redact before LLM)                      │
│    3. Intent matcher (12 regex patterns)                │
│       ├── MATCH → call MCP tool → format markdown       │
│       └── NO MATCH → forward to LLM                     │
│    4. Stream as SSE (tool_start / tool_result / text)   │
│    5. Emit OTEL trace + usage metrics                   │
└──────┬──────────────────────────────┬───────────────────┘
       │                              │
       ▼                              ▼
┌──────────────────┐         ┌──────────────────────┐
│  Bifröst MCP     │         │  Ollama (local)      │
│  (:8765)         │         │  OpenAI (cloud)      │
│                  │         │  Anthropic (cloud)   │
│  16 tools, RBAC  │         │  — swap via env var  │
└──────┬───────────┘         └──────────────────────┘
       │
       │ Grafana REST API (SA token, role-aware)
       ▼
┌─────────────────────────────────────────────────────────┐
│  Grafana — 113 dashboards, Mimir/Loki/Tempo             │
└─────────────────────────────────────────────────────────┘
```

Full details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Testing

98 automated tests across 5 suites. Run anytime:

```bash
cd tests
./preflight.sh          # verify services are up
./run-all-tests.sh      # full suite
```

```
Suite 1: 17 passed  (API endpoints — health, models, MCP, skills, rules, CORS)
Suite 2: 19 passed  (Intent matcher — dashboards, datasources, alerts, folders)
Suite 3: 22 passed  (UI Widget SSE parser — event types, CRLF, markdown)
Suite 4: 18 passed  (Integration E2E — full chain, 113 dashboards returned)
Suite 5: 22 passed  (Negative — RBAC, errors, stress, Unicode)
TOTAL:   98 passed, 0 failed
```

See [docs/TESTING.md](docs/TESTING.md) for every test detailed with manual curl examples.

---

## Example Queries

```
You: list all Grafana dashboards
Bot: **Found 113 dashboards:**
     • AKS — Cluster Overview & Health · folder: Azure
     • Advanced PostgreSQL Monitoring — ESOBF Dev · folder: Grafana
     • Azure — Application Insights (APM) · folder: Azure
     • Albertsons — Home · folder: Platform & Executive
     • (…and 109 more)

You: check grafana health
Bot: **Grafana Health**
     • Version: 11.6.4
     • Database: ✅ ok
     • Enterprise: false

You: search dashboards aks
Bot: Found 8 dashboards matching "aks":
     • AKS — Cluster Overview & Health
     • AKS — Network & Service Mesh
     • AKS — Node Resource Deep Dive
     • AKS — Pod & Workload Analytics
     • AKS — Storage & Persistent Volumes
     • (…and 3 more)

You: What is PromQL? One sentence.
Bot: PromQL is Prometheus' query language for selecting
     and aggregating time-series data in real-time.
     (LLM fallback — no tool matched)
```

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/TESTING.md](docs/TESTING.md) | 98-test suite with manual curl examples |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Every REST endpoint, SSE event types |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deploy into any Grafana instance |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System diagrams and data flow |

---

## Roadmap

- [x] Floating widget on every Grafana page
- [x] Min / Max / Fullscreen / Close controls
- [x] Per-user chat history (localStorage)
- [x] MCP integration (16 Grafana tools)
- [x] Self-hosted + cloud LLM support
- [x] PII detection (15 patterns)
- [x] Intent matcher (no-LLM tool routing)
- [x] 98-test automated suite + documentation
- [ ] Investigation engine (multi-agent root cause)
- [ ] Skills & Rules management UI
- [ ] PostgreSQL persistence
- [ ] Slack bidirectional integration
- [ ] Grafana IRM webhook bridge
- [ ] Dashboard generation from prompt

---

## Contributing

1. Fork the repo
2. Run `./tests/run-all-tests.sh` to baseline (should be 98/98 passing)
3. Make your changes
4. Add tests for any new intent patterns in `orchestrator/intents.py`
5. Run tests again — all must pass
6. Open a PR with a clear description

---

## License

Apache 2.0 — use, modify, deploy, commercial, all fine.

---

## Credits

Built on the shoulders of giants:

- **[Grafana](https://grafana.com)** — the observability platform we all love
- **[Bifröst](https://github.com/gpadidala/Bifrost)** — Grafana MCP server (sibling project)
- **[Ollama](https://ollama.com)** — local LLM runtime
- **[FastAPI](https://fastapi.tiangolo.com)** + **[sse-starlette](https://github.com/sysid/sse-starlette)** — the API layer
- **[Model Context Protocol](https://modelcontextprotocol.io)** — open standard for tool-calling

---

<p align="center">
  <sub>Made with ⚡ by <a href="https://github.com/gpadidala">Gopal</a></sub>
</p>
