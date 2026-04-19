# O11yBot API Reference

Complete reference for every endpoint exposed by the O11yBot orchestrator.

Base URL: `http://localhost:8000`

---

## Health & Meta

### `GET /api/v1/health`

Health check.

**Response:**
```json
{"status": "healthy", "service": "ollychat-orchestrator", "version": "1.0.0"}
```

### `GET /api/v1/models`

List available LLM models (filtered by configured API keys; Ollama always included).

**Response:**
```json
{
  "models": [
    {
      "id": "llama3.2:latest",
      "provider": "ollama",
      "displayName": "Llama 3.2 (Local)",
      "contextWindow": 128000,
      "costPer1kIn": 0.0,
      "costPer1kOut": 0.0,
      "supportsTools": false,
      "supportsStreaming": true,
      "strengths": ["local", "private", "free"]
    }
  ]
}
```

---

## Chat (SSE Streaming)

### `POST /api/v1/chat`

Stream a chat completion. Auto-routes between intent matcher (MCP tools) and LLM fallback.

**Request body:**
```json
{
  "messages": [
    {"role": "user", "content": "list all dashboards"}
  ],
  "system": "Optional system prompt",
  "max_tokens": 4096,
  "temperature": 0.2,
  "stream": true,
  "model": "optional-override-for-admin"
}
```

**Request headers (optional):**
- `X-Grafana-User`: User login (for user-specific history)
- `X-Grafana-Org-Id`: Grafana org ID
- `Origin`: Used by CORS

**Response:** `text/event-stream` (SSE)

Event types (`\r\n\r\n` separated):

```
data: {"type":"tool_start","id":"...","name":"list_dashboards","input":{}}

data: {"type":"tool_result","id":"...","result":{"ok":true},"durationMs":114}

data: {"type":"text","delta":"**Found 113 dashboards:**\n\n- ..."}

data: {"type":"usage","usage":{"promptTokens":0,"completionTokens":0,"totalTokens":0},"costUsd":0.0}

data: {"type":"done"}
```

Error event:
```
data: {"type":"error","message":"..."}
```

---

## MCP Server Management

### `GET /api/v1/mcp/servers`

List all configured MCP servers and their connection status.

**Response:**
```json
{
  "servers": [
    {
      "name": "ollychat-mcp-grafana",
      "url": "http://host.docker.internal:8765",
      "transport": "sse",
      "status": "connected",
      "toolCount": 16,
      "authMethod": "none",
      "enabled": true
    }
  ]
}
```

### `POST /api/v1/mcp/servers`

Register a new MCP server. Connection attempted immediately; tools discovered.

**Request:**
```json
{
  "name": "ollychat-mcp-grafana",
  "url": "http://host.docker.internal:8765",
  "transport": "sse",
  "auth_method": "none",
  "auth_token": "",
  "tool_filter": []
}
```

**Response:**
```json
{"ok": true, "server": {...}}
```

### `DELETE /api/v1/mcp/servers/{name}`

Remove an MCP server.

### `POST /api/v1/mcp/servers/{name}/toggle`

Enable/disable a server.

**Request:** `{"enabled": true}`

---

## MCP Tools

### `GET /api/v1/mcp/tools`

List all discovered tools across all connected MCP servers.

**Response:**
```json
{
  "tools": [
    {
      "name": "list_dashboards",
      "description": "List dashboards, optionally filtered by folder...",
      "inputSchema": {...},
      "serverName": "ollychat-mcp-grafana",
      "minRole": "viewer"
    }
  ]
}
```

### `POST /api/v1/mcp/tools/call`

Execute a tool.

**Request:**
```json
{
  "server_name": "ollychat-mcp-grafana",
  "tool_name": "list_dashboards",
  "arguments": {}
}
```

**Success response:**
```json
{
  "ok": true,
  "data": [...],
  "duration_ms": 114
}
```

**Error response:**
```json
{
  "ok": false,
  "error": "Tool 'list_users' requires role 'admin', but caller has role 'viewer'.",
  "duration_ms": 23
}
```

---

## Skills

### `GET /api/v1/skills`

List all skills.

### `POST /api/v1/skills`

Create a skill.

**Request:**
```json
{
  "name": "Incident Triage",
  "description": "Standard triage procedure",
  "category": "incident-triage",
  "systemPrompt": "Follow this procedure:\n1. Check...",
  "toolWhitelist": ["query_prometheus", "search_logs"],
  "modelPreference": "claude-sonnet-4-6",
  "slashCommand": "triage",
  "tags": ["incident", "triage"],
  "visibility": "everybody"
}
```

### `PUT /api/v1/skills/{skill_id}`

Update a skill (same schema as POST).

### `DELETE /api/v1/skills/{skill_id}`

Delete a skill.

### `GET /api/v1/skills/search?q={query}`

Keyword search across name, description, tags.

---

## Rules

### `GET /api/v1/rules`

List all rules.

### `POST /api/v1/rules`

Create a rule.

**Request:**
```json
{
  "name": "Environment Context",
  "content": "Our primary metrics datasource is Mimir...",
  "scope": "everybody",
  "enabled": true,
  "applications": ["assistant", "investigation"]
}
```

### `PUT /api/v1/rules/{rule_id}`

Update a rule.

### `DELETE /api/v1/rules/{rule_id}`

Delete a rule.

---

## Guardrails / PII

### `POST /api/v1/guardrails/scan`

Scan text for PII patterns.

**Request:**
```json
{"text": "Contact: user@example.com, SSN: 123-45-6789"}
```

**Response:**
```json
{
  "has_pii": true,
  "redacted_text": "Contact: [EMAIL_REDACTED], SSN: [SSN_REDACTED]",
  "matches": [
    {"type": "email", "start": 9, "end": 26, "confidence": 0.95},
    {"type": "ssn", "start": 33, "end": 44, "confidence": 0.90}
  ]
}
```

**Supported PII types (15):** email, phone_us, phone_international, ssn, credit_card_visa, credit_card_mastercard, credit_card_amex, ip_address_v4, api_key_openai, api_key_github, api_key_slack, api_key_aws, api_key_generic, date_of_birth, address_us.

---

## Intent Matcher Patterns

The orchestrator intercepts natural-language queries matching these patterns and routes to MCP tools. Unmatched queries fall through to the LLM.

| Query pattern | Tool called | Tool server |
|---|---|---|
| `list/show/all dashboards` | `list_dashboards` | ollychat-mcp-grafana |
| `search dashboards <query>` | `search_dashboards` | ollychat-mcp-grafana |
| `list/show datasources` | `list_datasources` | ollychat-mcp-grafana |
| `check datasource health` | `list_datasources` | ollychat-mcp-grafana |
| `list alerts` | `list_alert_rules` | ollychat-mcp-grafana |
| `firing/active alerts` | `list_alert_instances` | ollychat-mcp-grafana |
| `list folders` | `list_folders` | ollychat-mcp-grafana |
| `list users` | `list_users` | ollychat-mcp-grafana (admin) |
| `grafana health/status/version` | `health_check` | ollychat-mcp-grafana |
| `health check` / `ping` | `health_check` | ollychat-mcp-grafana |
| `mcp/ollychat-mcp info` | `get_server_info` | ollychat-mcp-grafana |

Defined in: `orchestrator/intents.py`.

---

## MCP Tools (16 total from O11yBot MCP)

| Tool | Min Role | Description |
|---|---|---|
| `list_dashboards` | viewer | List dashboards filtered by folder/tags |
| `search_dashboards` | viewer | Full-text dashboard search |
| `get_dashboard` | viewer | Full dashboard JSON by UID |
| `get_dashboard_panels` | viewer | Panels of a dashboard |
| `list_datasources` | viewer | All configured datasources |
| `get_datasource` | viewer | Datasource details by UID |
| `query_datasource` | viewer | Run a query against a datasource |
| `list_folders` | viewer | Dashboard folders |
| `list_alert_rules` | viewer | Unified alerting rules |
| `get_alert_rule` | viewer | Alert rule by UID |
| `list_alert_instances` | viewer | Firing/pending alert instances |
| `silence_alert` | editor | Create alertmanager silence |
| `list_users` | admin | Organization users |
| `list_service_accounts` | admin | Service accounts |
| `health_check` | viewer | Ping Grafana |
| `get_server_info` | viewer | O11yBot MCP metadata |

---

## Widget (Browser-side)

**Widget URL:** `/public/plugins/gopal-ollychat-app/o11ybot-widget.js`

**Injection point:** `/usr/share/grafana/public/views/index.html` (mounted read-only)

### Public state keys (localStorage)

- `o11ybot-<username>`: per-user widget state
  - `msgs`: last 100 messages
  - `posX`, `posY`: custom position
  - `mode`: `"normal"` | `"maximized"` | `"fullscreen"`

### Keyboard shortcuts

- `Enter`: send message
- `Shift+Enter`: newline in input
- `Escape`: exit fullscreen or maximized mode

### Window controls

- **Clear**: wipe this user's chat history
- **Minimize (−)**: collapse to floating bubble (keeps history)
- **Maximize (□)**: 75% viewport overlay with blur backdrop
- **Fullscreen (⛶)**: 100% viewport
- **Close (×)**: collapse to floating bubble + reset mode
