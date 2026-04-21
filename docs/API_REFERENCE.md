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

The orchestrator intercepts natural-language queries matching 60+ regex patterns and
routes them to MCP tools. Unmatched queries fall through to the LLM. Defined in
[`orchestrator/intents.py`](../orchestrator/intents.py).

Representative examples — see [USE_CASES.md](USE_CASES.md) for the full matrix:

| Query pattern | Tool called |
|---|---|
| `list/show/all dashboards`                              | `list_dashboards` |
| `list AKS / Azure / Loki dashboards`                    | `list_dashboards` with tag filter |
| `search dashboards <query>`                             | `search_dashboards` |
| `<random words> dashboards`                             | `list_dashboards` + local fuzzy + LLM-as-judge rerank |
| `show/describe/summarize dashboard <uid>`               | `get_dashboard` |
| `create dashboard "X"` / `create payment-service dashboard now` | `create_smart_dashboard` (auto metric discovery) |
| `create dashboard "X" on datasource <uid> in folder <uid>` | `create_smart_dashboard` (explicit args) |
| `create dashboard` (under-specified)                    | `dashboard_wizard` (asks DS + folder) |
| `delete dashboard <uid>`                                | `delete_dashboard` (admin) |
| `list alert rules` / `firing alerts`                    | `list_alert_rules` · `list_alert_instances` |
| `explain alert <uid>` / `investigate alert <uid>`       | `get_alert_rule` · `investigate_alert` workflow |
| `create alert for X`                                    | `alert_wizard` (asks DS + folder + metric) |
| `silence alert <uid>`                                   | `silence_alert` (editor) |
| `list contact points / policies / silences`             | `list_contact_points` · `list_notification_policies` · `list_silences` |
| `list datasources` / `get datasource <uid>`             | `list_datasources` · `get_datasource` |
| `run promql <expr>` / `search logs for <svc>` / `find slow traces` | `query_datasource` · `query_loki` · `query_tempo` |
| `list metric names` / `list metrics matching <rx>`      | `list_metric_names` |
| `list folders / create folder "X"`                      | `list_folders` · `create_folder` |
| `list teams / create team "X"`                          | `list_teams` · `create_team` (admin) |
| `list plugins` / `list datasource plugins`              | `list_plugins` |
| `list library panels` · `list annotations`              | `list_library_panels` · `list_annotations` |
| `correlate service <svc>`                               | `correlate_signals` (metrics + logs + traces) |
| `create slo for <svc>`                                  | `create_slo_dashboard` |
| `which dashboards use metric <name>`                    | `find_dashboards_using_metric` |
| `promql / logql / traceql / slo cookbook`               | static cookbook (no tool call) |
| `where do I find <feature>` / `decode error: <msg>`     | static navigation / error-decoder help |
| `list users / list service accounts`                    | `list_users` · `list_service_accounts` (admin) |
| `grafana health/status/version` / `ping`                | `health_check` |
| `mcp server info`                                       | `get_server_info` |

---

## MCP Tools (53 total, bundled with the repo)

The MCP server lives in [`mcp-server/`](../mcp-server/) and is auto-registered with
the orchestrator on startup. Roles are enforced at the MCP layer via per-role
service-account tokens — the caller's Grafana role is passed in the tool-call
arguments.

### Dashboards (8)

| Tool | Role | Description |
|---|---|---|
| `list_dashboards`        | viewer | List dashboards filtered by folder UID / tags |
| `search_dashboards`      | viewer | Full-text dashboard search |
| `get_dashboard`          | viewer | Full dashboard JSON by UID |
| `get_dashboard_panels`   | viewer | Panel list for a dashboard |
| `create_dashboard`       | editor | Create an empty dashboard with title + tags + folder |
| `create_smart_dashboard` | editor | Auto-discover metrics + build 14–22 typed panels |
| `update_dashboard`       | editor | In-place patch of title / tags / panels / description |
| `delete_dashboard`       | admin  | Remove a dashboard by UID |

### Alerts (11)

| Tool | Role | Description |
|---|---|---|
| `list_alert_rules`            | viewer | All unified alerting rules |
| `get_alert_rule`              | viewer | Single rule detail by UID |
| `list_alert_instances`        | viewer | Currently firing / pending instances |
| `silence_alert`               | editor | Create an Alertmanager silence by alert UID |
| `list_silences`               | viewer | All active silences |
| `delete_silence`              | editor | Unmute by silence ID |
| `create_alert_rule`           | editor | Provision a Grafana-managed alert rule |
| `update_alert_rule`           | editor | Patch title / expr / threshold / for / severity |
| `delete_alert_rule`           | admin  | Remove rule by UID |
| `list_contact_points`         | viewer | Alert notification contact points |
| `list_notification_policies`  | viewer | Notification policy routing tree |
| `list_mute_timings`           | viewer | Alert mute timings |

### Datasources & queries (8)

| Tool | Role | Description |
|---|---|---|
| `list_datasources`    | viewer | All configured datasources |
| `get_datasource`      | viewer | One datasource detail by UID |
| `query_datasource`    | viewer | Run any query (PromQL / LogQL / TraceQL / SQL) |
| `query_loki`          | viewer | LogQL range query with line limit |
| `query_tempo`         | viewer | TraceQL query returning trace summaries |
| `list_metric_names`   | viewer | Prometheus metric-name discovery with regex filter |
| `list_label_values`   | viewer | Label value discovery |

### Folders (5)

| Tool | Role | Description |
|---|---|---|
| `list_folders`   | viewer | All dashboard folders |
| `get_folder`     | viewer | Folder metadata by UID |
| `create_folder`  | editor | New folder with optional parent |
| `update_folder`  | editor | Rename folder |
| `delete_folder`  | admin  | Remove folder (force-deletes rules inside) |

### Annotations (3) · Library panels (2) · Plugins (2) · Teams (4) · Users (2)

| Tool | Role | Description |
|---|---|---|
| `list_annotations`        | viewer | Recent annotations (time-range / tags / dashboard UID) |
| `create_annotation`       | editor | Deploy marker / incident annotation |
| `delete_annotation`       | editor | Remove by annotation ID |
| `list_library_panels`     | viewer | Reusable library panels |
| `get_library_panel`       | viewer | One library panel's full model |
| `list_plugins`            | viewer | All installed plugins (type filter optional) |
| `get_plugin`              | viewer | Plugin settings + metadata |
| `list_teams`              | viewer | Teams in the active org |
| `create_team`             | admin  | Create a new team |
| `list_team_members`       | viewer | Team roster |
| `add_team_member`         | admin  | Add user to a team |
| `list_users`              | admin  | Org users |
| `list_service_accounts`   | admin  | Service accounts |

### Workflow tools (6) — compound, multi-step orchestrations

| Tool | Role | What it does |
|---|---|---|
| `investigate_alert`            | viewer | Rule + firing instances + related dashboards + next-step suggestions |
| `correlate_signals`            | viewer | Prometheus + Loki + Tempo for one service in a single call |
| `create_slo_dashboard`         | editor | 8-panel SLO: SLI, error-budget consumed, fast + slow burn rate |
| `find_dashboards_using_metric` | viewer | Impact analysis — every dashboard that references a metric |
| `alert_wizard`                 | viewer | Returns datasources + folders + metric suggestions to fill in an alert |
| `dashboard_wizard`             | viewer | Same flow for dashboard creation |

### Utility (2)

| Tool | Role | Description |
|---|---|---|
| `health_check`     | viewer | Grafana version + database status |
| `get_server_info`  | viewer | MCP server metadata (tool count, grafana_url, transport) |

Total: **53 tools · 4 internal cookbooks** (promql / logql / traceql / slo —
served without a tool call by [`prompts.py`](../orchestrator/prompts.py)).

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
