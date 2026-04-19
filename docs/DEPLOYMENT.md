# O11yBot Deployment Guide

How to install O11yBot into any Grafana instance.

## What gets deployed

1. **Plugin** (`dist/`) — mounted to `/var/lib/grafana/plugins/gopal-ollychat-app`
2. **Widget script** (`dist/o11ybot-widget.js`) — injected globally via custom index.html
3. **Orchestrator** (`orchestrator/`) — FastAPI service on port 8000
4. **O11yBot MCP** (sibling repo) — MCP server on port 8765
5. **Ollama** (optional) — self-hosted LLM for dev

## Prerequisites

- Docker + Docker Compose
- Node.js (for testing)
- Python 3.11+ (for O11yBot MCP)

## Installation Steps

### 1. Start the orchestrator stack

```bash
cd /Volumes/Gopalmac/Gopal-aiops/ollychat-app
cp .env.example .env        # edit with OPENAI_API_KEY for prod
docker compose up -d
```

This starts: orchestrator, ollama, otel-collector, tempo, mimir, loki.

### 2. Start O11yBot MCP server

```bash
cd /Volumes/Gopalmac/Gopal-aiops/O11yBot MCP
python3 -m venv .venv
.venv/bin/pip install -e packages/core
.venv/bin/grafana-mcp serve --port 8765 &
```

Point `.env` to your Grafana instance:
```
GRAFANA_MCP_ENVIRONMENTS__DEV__BASE_URL=http://localhost:3200
GRAFANA_MCP_ENVIRONMENTS__DEV__SERVICE_ACCOUNTS__VIEWER=glsa_xxxxxxxx
```

Create the SA token in Grafana:
```bash
SA=$(curl -s -X POST http://admin:admin@localhost:3200/api/serviceaccounts \
  -H "Content-Type: application/json" \
  -d '{"name":"ollybot-mcp","role":"Viewer"}')
SA_ID=$(echo "$SA" | jq -r '.id')
TOKEN=$(curl -s -X POST "http://admin:admin@localhost:3200/api/serviceaccounts/$SA_ID/tokens" \
  -H "Content-Type: application/json" \
  -d '{"name":"ollybot-token"}' | jq -r '.key')
echo "Token: $TOKEN"
```

### 3. Install into your Grafana

Add to your Grafana `docker-compose.yml`:

```yaml
services:
  grafana:
    environment:
      - GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=gopal-ollychat-app
    volumes:
      - /path/to/ollychat-app/dist:/var/lib/grafana/plugins/gopal-ollychat-app:ro
      - /path/to/ollychat-app/grafana-index.html:/usr/share/grafana/public/views/index.html:ro
```

Restart Grafana:
```bash
docker compose restart grafana
```

### 4. Register MCP server with orchestrator

```bash
curl -X POST http://localhost:8000/api/v1/mcp/servers \
  -H "Content-Type: application/json" \
  -d '{"name":"ollychat-mcp-grafana","url":"http://host.docker.internal:8765","transport":"sse","auth_method":"none"}'
```

### 5. Enable the plugin

```bash
curl -X POST http://admin:admin@localhost:3200/api/plugins/gopal-ollychat-app/settings \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"pinned":true}'
```

### 6. Verify

```bash
cd /Volumes/Gopalmac/Gopal-aiops/ollychat-app/tests
./preflight.sh
./run-all-tests.sh
```

Open http://localhost:3200 — orange O11yBot bubble appears bottom-right.

## Configuration

### LLM Provider (admin-only, not user-visible)

Edit `.env`:
```
# Dev (self-hosted, no cost)
OLLYCHAT_DEFAULT_MODEL=qwen2.5:0.5b

# Prod (OpenAI)
OLLYCHAT_DEFAULT_MODEL=gpt-4o
OLLYCHAT_OPENAI_API_KEY=sk-...

# Prod (Anthropic)
OLLYCHAT_DEFAULT_MODEL=claude-sonnet-4-6
OLLYCHAT_ANTHROPIC_API_KEY=sk-ant-...
```

Restart: `docker restart ollychat-orchestrator`

### CORS origins

Widget sends requests from Grafana to orchestrator. `.env`:
```
OLLYCHAT_CORS_ORIGINS=["*"]  # dev
# or specific:
# OLLYCHAT_CORS_ORIGINS=["http://localhost:3200","https://grafana.example.com"]
```

### Widget orchestrator URL

In production where orchestrator is on a different host, update:
```
ollychat-app/o11ybot-widget.js
  var ORCHESTRATOR = "https://ollybot.example.com";
```
Then `cp o11ybot-widget.js dist/`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Orange bubble not appearing | Check `grafana-index.html` is mounted. `docker restart grafana`. Clear browser cache. |
| "Failed to fetch" in bubble | CORS issue. Verify `OLLYCHAT_CORS_ORIGINS` and `Access-Control-Allow-Origin` header matches browser origin. |
| Empty chat bubble | SSE parser bug (CRLF vs LF). Already fixed in current widget. Verify widget version. |
| "MCP server not connected" | Re-register via curl POST to `/api/v1/mcp/servers`. In-memory store clears on orchestrator rebuild. |
| Intent returns wrong tool | Check `orchestrator/intents.py` — patterns are ordered by specificity. |

## Production Checklist

- [ ] Use specific CORS origins, not `["*"]`
- [ ] Serve orchestrator behind HTTPS
- [ ] Use Grafana SA token with minimal role (viewer)
- [ ] Persist MCP server registration to database (currently in-memory)
- [ ] Add rate limiting on orchestrator
- [ ] Enable OpenTelemetry export (already wired)
- [ ] Replace Ollama with commercial LLM (OpenAI/Anthropic/Bedrock)
- [ ] Review PII patterns for your compliance needs
