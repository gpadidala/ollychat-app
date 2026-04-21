# O11yBot — Enterprise Deployment Guide

Production-grade checklist for running O11yBot against any Grafana instance.

## Architecture

```
Grafana UI (any instance)
  └─► widget (this repo, loaded via plugin.json)
        └─► orchestrator (FastAPI, port 8000)
              └─► O11yBot MCP (this repo, port 8765)
                    └─► Grafana HTTP API (GRAFANA_URL)
                    └─► Prometheus/Loki/Tempo (via datasource proxy)
```

Everything is owned by this repo — no external MCP dependency.

## Deploying anywhere

### 1. Create three Grafana service-account tokens

In the target Grafana:

1. Admin → **Service accounts** → **New service account**
2. Create three: `o11ybot-viewer` (Viewer role), `o11ybot-editor` (Editor), `o11ybot-admin` (Admin)
3. For each, **Add token** → copy the `glsa_…` value

### 2. Configure `.env`

```bash
cp .env.example .env
```

```env
GRAFANA_URL=https://grafana.yourco.com
GRAFANA_VIEWER_TOKEN=glsa_...
GRAFANA_EDITOR_TOKEN=glsa_...
GRAFANA_ADMIN_TOKEN=glsa_...
GRAFANA_TLS_VERIFY=true         # false for self-signed dev certs
OLLYCHAT_DEFAULT_MODEL=qwen2.5:0.5b   # or claude-sonnet-4-6 / gpt-4o-mini
```

For a single-tenant demo you can set only `GRAFANA_TOKEN=glsa_…` — the same
token is used for every role. Real RBAC requires the three separate tokens.

### 3. Ship the plugin

The app plugin is in `dist/`. Copy it into your Grafana's plugin directory:

```bash
cp -r dist /var/lib/grafana/plugins/gopal-ollychat-app
```

Enable unsigned-plugin loading (dev only) or have the plugin signed:
```
GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=gopal-ollychat-app
```

Restart Grafana.

### 4. Boot the backend stack

```bash
make up
```

Brings up all 10 services (Grafana + orchestrator + MCP + Ollama + Prometheus +
Tempo + Mimir + Loki + OTEL collector + image renderer), auto-mints the SA
tokens in the bundled Grafana (if you haven't set your own), and auto-registers
the MCP with the orchestrator. Point the plugin's widget at `http://localhost:8000`
(the orchestrator).

## Role-based access in practice

| Role | Can do | Cannot do |
|---|---|---|
| `viewer` | all reads, run queries, PromQL help, investigations | any mutation, list users |
| `editor` | + create/update dashboards, create folders, silence alerts, create alert rules, annotations | delete dashboards, list users, delete rules |
| `admin` | everything + delete, user/SA listing, team creation | — |

Role comes from Grafana's session (`X-Grafana-Role` header), forwarded by the
widget, normalised by the orchestrator, enforced at the MCP layer *before* any
Grafana API call is made.

## Self-observability

The MCP server exports its own Prometheus metrics at `http://localhost:8765/metrics`:

```promql
# Tool call rate per tool / role
rate(ollychat_mcp_tool_calls_total[5m])

# Error rate
sum(rate(ollychat_mcp_tool_calls_total{status="error"}[5m]))
  /
sum(rate(ollychat_mcp_tool_calls_total[5m]))

# p95 tool latency
histogram_quantile(0.95, sum by (le, tool) (rate(ollychat_mcp_tool_duration_seconds_bucket[5m])))

# Outbound Grafana API errors
sum by (status_class) (rate(ollychat_mcp_grafana_requests_total[5m]))
```

Each tool invocation also emits a structured audit log:

```json
{
  "event": "tool.call",
  "tool": "create_smart_dashboard",
  "role": "editor",
  "status": "ok",
  "duration_ms": 742,
  "error": null
}
```

Pipe those logs into Loki for cross-user auditing.

## Hardening checklist

- [ ] Set `GRAFANA_TLS_VERIFY=true` and pin the CA if on self-hosted TLS
- [ ] Use **dedicated SAs** per role — never use a human admin token
- [ ] Rate-limit the orchestrator at your ingress; the MCP accepts unauthenticated
      localhost calls only through the orchestrator by default
- [ ] Run the orchestrator + MCP behind a single internal VPN or service mesh —
      expose only the widget + `/api/v1/chat` to users
- [ ] Scrape `/metrics` from the MCP into your production Prometheus
- [ ] Alert on `rate(ollychat_mcp_tool_calls_total{status!="ok"}[5m]) > 0.1`
- [ ] Backup: the MCP is stateless — only the SA tokens are sensitive

## Scaling notes

- **MCP server**: stateless; scale horizontally behind a load balancer.
  Connection pool is per-replica, but Grafana handles concurrent requests fine.
- **Orchestrator**: session state is in the client (localStorage). The server
  keeps only an in-memory MCP client registration, re-established on startup.
- **Ollama / LLM**: single-instance or swap for a managed provider
  (`OLLYCHAT_ANTHROPIC_API_KEY`, `OLLYCHAT_OPENAI_API_KEY`) via `.env`.
- **Widget**: plain JS, zero deps. Reloaded via `?v=Date.now()` so cache is
  never a concern across deploys.
