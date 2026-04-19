# O11yBot MCP Server

Self-contained Grafana tool layer for O11yBot. Exposes a REST bridge compatible
with the orchestrator's MCP client — no external dependencies.

## What it does

Owns every MCP tool call the chatbot makes against your Grafana: listing
dashboards, running PromQL queries, creating RED-template dashboards, silencing
alerts, managing folders, etc. One container, one set of env vars, talks to
any Grafana instance.

## Configuration (env vars)

| Variable | Purpose | Default |
|---|---|---|
| `GRAFANA_URL` | Base URL of the target Grafana | `http://host.docker.internal:3200` |
| `GRAFANA_VIEWER_TOKEN` | Service-account token for viewer role | — |
| `GRAFANA_EDITOR_TOKEN` | Service-account token for editor role | — |
| `GRAFANA_ADMIN_TOKEN` | Service-account token for admin role | — |
| `GRAFANA_TOKEN` | Single-token fallback (used for every role if set) | — |
| `GRAFANA_TLS_VERIFY` | Verify Grafana TLS cert | `true` |
| `GRAFANA_TIMEOUT_S` | Per-request timeout seconds | `30` |
| `MCP_SERVER_PORT` | Port to listen on | `8765` |

## Endpoints

```
GET  /health           — liveness probe
GET  /api/tools        — catalog of all 21 tools with input schemas + min_role
POST /api/tools/call   — { "name": "...", "arguments": { "role": "admin", ... } }
```

## Tool catalogue

| Category | Tools |
|---|---|
| Dashboards (read) | `list_dashboards`, `search_dashboards`, `get_dashboard`, `get_dashboard_panels` |
| Dashboards (write) | `create_dashboard`, `create_smart_dashboard`, `update_dashboard`, `delete_dashboard` |
| Alerts | `list_alert_rules`, `get_alert_rule`, `list_alert_instances`, `silence_alert` |
| Datasources | `list_datasources`, `get_datasource`, `query_datasource` |
| Folders | `list_folders`, `create_folder` |
| Admin | `list_users`, `list_service_accounts` |
| Utility | `health_check`, `get_server_info` |

## RBAC

Each tool has a minimum role (`viewer`, `editor`, or `admin`). The server picks
the matching service-account token per call, so calls made by a viewer user
can't mutate state even if they target a write tool.

## Running standalone

```bash
docker build -t ollychat-mcp .
docker run --rm -p 8765:8765 \
  -e GRAFANA_URL=https://grafana.example.com \
  -e GRAFANA_ADMIN_TOKEN=glsa_xxx \
  ollychat-mcp
```

Or via the full O11yBot stack: `docker compose up -d` from the repo root.
