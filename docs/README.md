# O11yBot Documentation

| Doc | Purpose |
|---|---|
| [TESTING.md](TESTING.md) | Full test suite docs — run/maintain all 94 tests |
| [API_REFERENCE.md](API_REFERENCE.md) | All REST endpoints, SSE event types, MCP tools |
| [DEPLOYMENT.md](DEPLOYMENT.md) | How to deploy to any Grafana instance |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System diagrams and data flow |

## Quick Links

### Services
- **Main Grafana**: http://localhost:3200 (admin/admin) — 113 dashboards
- **Orchestrator API**: http://localhost:8000
- **Bifrost MCP**: http://localhost:8765
- **Ollama LLM**: http://localhost:11434

### Run tests
```bash
cd tests
./run-all-tests.sh        # full 94-test suite
./preflight.sh            # service health check only
./suite1-api.sh           # API only (14 tests)
./suite2-intents.sh       # intent matcher (19 tests)
node suite3-widget.js     # SSE parser (22 tests)
node suite4-integration.js  # E2E integration (18 tests)
node suite5-negative.js   # error cases (22 tests)
```

### Widget features
- Floating orange bubble, bottom-right corner (draggable)
- Minimize / Maximize / Fullscreen / Close buttons
- Keyboard: Enter to send, Esc to exit fullscreen
- Per-user chat history (localStorage keyed by Grafana login)
- Streaming responses with markdown rendering
- Intent-matched MCP tool calls with real Grafana data
