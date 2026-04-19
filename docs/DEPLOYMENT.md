# O11yBot — Production Deployment Guide

Where [INSTALLATION.md](INSTALLATION.md) gets you to "it works on my laptop",
this document covers the production paths:

- **Path A — Single-node Docker Compose** (small teams, ≤ 50 users)
- **Path B — Kubernetes (Helm) with external Grafana** (most enterprise installs)
- **Path C — Bare metal systemd** (regulated environments / air-gapped)

Each path is laid out as: *prereqs → steps → validation → rollback*.

---

## Common prerequisites — all paths

| Item | Detail |
|---|---|
| Target Grafana | 10.0+ (OSS or Enterprise), reachable over HTTPS |
| Three SA tokens | `viewer` / `editor` / `admin` — see [INSTALLATION.md §3](INSTALLATION.md#3-create-grafana-service-account-tokens) |
| DNS names | `o11ybot-chat.<domain>` and `o11ybot-mcp.<domain>` behind your ingress |
| TLS certificates | either ingress-terminated or pass-through to the containers |
| An LLM backend | local Ollama *or* an OpenAI / Anthropic key |
| Logging destination | Loki / CloudWatch / Elastic — anything that can ingest JSON lines |
| Metrics destination | Prometheus or Mimir — scrapes `/metrics` on port 8765 |

---

## Path A — Single-node Docker Compose

**When to pick this:** small teams, one-server deployments, non-production
demos, homelab setups.

### Steps

1. Install Docker + Compose on the target host.
2. Clone the repo and populate `.env` (see [INSTALLATION.md §4](INSTALLATION.md#4-configure-env)).
3. Put a reverse proxy (Caddy / nginx / Traefik) in front of ports 8000 + 8765.
   Sample Caddyfile:

   ```
   o11ybot-chat.example.com {
     reverse_proxy localhost:8000
   }
   o11ybot-mcp.example.com {
     reverse_proxy localhost:8765
     basic_auth {
       o11ybot-scraper <bcrypt hash>    # only used by Prometheus scraper
     }
   }
   ```

4. Boot: `docker compose up -d`
5. Register MCP with orchestrator — [INSTALLATION.md §7](INSTALLATION.md#7-register-the-mcp-server-with-the-orchestrator).

### Validation — Path A

```bash
# Orchestrator up
curl -fsSL https://o11ybot-chat.example.com/api/v1/models | jq '.models | length'

# MCP up + tool count
curl -fsSL https://o11ybot-mcp.example.com/health | jq .

# End-to-end chat via API
curl -s -X POST https://o11ybot-chat.example.com/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Grafana-Role: Admin' \
  -d '{"messages":[{"role":"user","content":"list datasources"}]}' \
  | head -c 300
```

Expected: a streamed SSE response beginning with `data: {"type":"tool_start",…}`.

### Rollback — Path A

```bash
docker compose down
```

State is in two places:
- Grafana itself (dashboards/alerts created via O11yBot) — those remain. Clean
  them up via the Grafana UI or re-run the delete tool calls.
- `dist/` on the Grafana host if you mounted the plugin — `rm -rf` it and
  restart Grafana.

---

## Path B — Kubernetes (Helm) with external Grafana

**When to pick this:** the typical enterprise install — Grafana already runs
somewhere (Grafana Cloud, Helm on EKS / GKE / AKS, on-prem Helm), and you want
to drop O11yBot in front of it.

### Architecture

```
┌──────────────────────────┐         ┌──────────────────────────┐
│ Grafana (OSS or Enterprise)│       │  O11yBot namespace (new)  │
│  - loaded plugin           │◀─HTTPS│  Deployments:             │
│  - SA tokens x3            │       │    o11ybot-orchestrator   │
│  - your existing LGTM      │       │    o11ybot-mcp            │
└──────────────────────────┘         │    o11ybot-ollama (opt.)  │
                                     │  Services + Ingress        │
                                     │  ServiceMonitor (Prom.)    │
                                     └──────────────────────────┘
```

### Steps

1. **Create the namespace + secret for SA tokens:**

   ```bash
   kubectl create namespace o11ybot

   kubectl -n o11ybot create secret generic grafana-tokens \
     --from-literal=GRAFANA_VIEWER_TOKEN=glsa_xxx \
     --from-literal=GRAFANA_EDITOR_TOKEN=glsa_yyy \
     --from-literal=GRAFANA_ADMIN_TOKEN=glsa_zzz
   ```

2. **Apply the MCP Deployment** (`k8s/mcp.yaml` — sample below):

   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata: { name: o11ybot-mcp, namespace: o11ybot }
   spec:
     replicas: 2
     selector: { matchLabels: { app: o11ybot-mcp } }
     template:
       metadata: { labels: { app: o11ybot-mcp } }
       spec:
         containers:
           - name: mcp
             image: ghcr.io/gpadidala/ollychat-mcp:latest
             ports: [ { containerPort: 8765 } ]
             env:
               - name: GRAFANA_URL
                 value: https://grafana.example.com
               - name: GRAFANA_TLS_VERIFY
                 value: "true"
             envFrom:
               - secretRef: { name: grafana-tokens }
             readinessProbe:
               httpGet: { path: /health, port: 8765 }
               periodSeconds: 5
             livenessProbe:
               httpGet: { path: /health, port: 8765 }
               periodSeconds: 20
             resources:
               requests: { cpu: 50m, memory: 128Mi }
               limits:   { cpu: 500m, memory: 512Mi }
   ---
   apiVersion: v1
   kind: Service
   metadata: { name: o11ybot-mcp, namespace: o11ybot }
   spec:
     selector: { app: o11ybot-mcp }
     ports: [ { port: 8765, targetPort: 8765 } ]
   ```

3. **Apply the orchestrator Deployment**. Same pattern — two replicas, env vars
   from `.env.example`, `OLLYCHAT_BIFROST_URL=http://o11ybot-mcp.o11ybot.svc:8765`.

4. **Install the plugin into the target Grafana** — [INSTALLATION.md §5](INSTALLATION.md#5-install-the-plugin).
   For Helm-deployed Grafana, add the init-container snippet in §5d.

5. **Ingress** (sample nginx):

   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: o11ybot
     namespace: o11ybot
     annotations:
       nginx.ingress.kubernetes.io/proxy-buffering: "off"   # SSE needs this
       nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
   spec:
     rules:
       - host: o11ybot-chat.example.com
         http:
           paths:
             - path: /
               pathType: Prefix
               backend: { service: { name: o11ybot-orchestrator, port: { number: 8000 } } }
   ```

6. **ServiceMonitor** for Prometheus:

   ```yaml
   apiVersion: monitoring.coreos.com/v1
   kind: ServiceMonitor
   metadata: { name: o11ybot-mcp, namespace: o11ybot }
   spec:
     selector: { matchLabels: { app: o11ybot-mcp } }
     endpoints: [ { port: http, path: /metrics, interval: 30s } ]
   ```

### Validation — Path B

```bash
# Pods healthy
kubectl -n o11ybot get pods

# Tool catalog reachable inside cluster
kubectl -n o11ybot exec deploy/o11ybot-orchestrator -- \
  curl -s http://o11ybot-mcp.o11ybot.svc:8765/api/tools | jq '.data | length'

# External round-trip
curl -s https://o11ybot-chat.example.com/api/v1/models | jq '.models | length'

# Widget loads in browser: open Grafana → look for the orange FAB bottom-right
```

### Rollback — Path B

```bash
kubectl delete namespace o11ybot
# remove the plugin from Grafana (Helm: re-deploy without the init container)
```

---

## Path C — Bare metal systemd (air-gapped)

**When to pick this:** regulated / air-gapped environments where Docker isn't
allowed and you need repeatable `systemd`-managed services.

### Steps

1. **Install Python 3.12** on the target host.

2. **Package the MCP server + orchestrator as systemd units:**

   `/etc/systemd/system/o11ybot-mcp.service`:

   ```ini
   [Unit]
   Description=O11yBot MCP server
   After=network-online.target

   [Service]
   User=o11ybot
   Group=o11ybot
   EnvironmentFile=/etc/o11ybot/mcp.env
   WorkingDirectory=/opt/o11ybot/mcp-server
   ExecStart=/opt/o11ybot/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8765
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   `/etc/o11ybot/mcp.env`:

   ```env
   GRAFANA_URL=https://grafana.internal.example.com
   GRAFANA_VIEWER_TOKEN=glsa_xxx
   GRAFANA_EDITOR_TOKEN=glsa_yyy
   GRAFANA_ADMIN_TOKEN=glsa_zzz
   GRAFANA_TLS_VERIFY=true
   ```

   Mirror the pattern for `o11ybot-orchestrator.service`.

3. **Ship the plugin bundle** to Grafana's plugin dir — same as
   [INSTALLATION.md §5b](INSTALLATION.md#5b-target-an-existing-oss-grafana).

4. **Enable + start:**

   ```bash
   systemctl daemon-reload
   systemctl enable --now o11ybot-mcp o11ybot-orchestrator
   ```

### Validation — Path C

```bash
systemctl is-active o11ybot-mcp o11ybot-orchestrator
curl -fsSL http://localhost:8765/health
journalctl -u o11ybot-mcp -n 50 --no-pager
```

### Rollback — Path C

```bash
systemctl disable --now o11ybot-mcp o11ybot-orchestrator
rm -rf /opt/o11ybot /etc/o11ybot
```

---

## Grafana OSS vs Grafana Enterprise — what differs

| Concern | OSS | Enterprise |
|---|---|---|
| Plugin signing | Use `allow_loading_unsigned_plugins` | Same; contact Grafana Labs to sign for long-term |
| RBAC | Viewer/Editor/Admin only | Plus fine-grained custom roles — O11yBot honours them automatically |
| Audit log | Basic | Full — every SA-token call is attributed |
| SAML / OAuth SSO | Limited | Widget reads whatever the IdP puts in the session — no extra work |
| Data source plugins | Open-source only | + Enterprise DSes (Splunk, ServiceNow, …) — `list_datasources` shows them all |
| Reporting | Not available | O11yBot can list `/api/reports` (future tool) |

**Nothing in this repo requires Enterprise.** Every capability works on OSS —
Enterprise just gets a richer audit trail and more granular RBAC for free.

---

## Hardening checklist (production)

- [ ] Use **dedicated SA tokens** per role — never reuse a personal admin token.
- [ ] Rotate SA tokens quarterly (Grafana Admin → Service accounts → tokens).
- [ ] Set `GRAFANA_TLS_VERIFY=true` and pin the CA if self-signed.
- [ ] Run orchestrator + MCP **behind the same trust boundary** — expose only
      the orchestrator to users, keep `/api/tools/call` on an internal network.
- [ ] Rate-limit the orchestrator at the ingress (e.g. 60 req/min/user).
- [ ] Scrape `/metrics` from the MCP into your prod Prometheus.
- [ ] Alert on:
      - `rate(ollychat_mcp_tool_calls_total{status!="ok"}[5m]) > 0.1`
      - `histogram_quantile(0.95, rate(ollychat_mcp_tool_duration_seconds_bucket[5m])) > 5`
      - `ollychat_mcp_grafana_requests_total{status_class=~"5.."}` > 0
- [ ] Ship the `tool.call` audit log line into Loki with a `user` label.

---

## Scaling notes

- **MCP server:** stateless, horizontally scalable behind a Service/LB.
  One replica handles ≥ 200 QPS on a single core.
- **Orchestrator:** stateless (client keeps session in localStorage). Scale
  replicas per chat QPS. Heavy LLM traffic benefits from session affinity at
  the LB to reuse SSE connections.
- **Ollama:** single-node. For prod, swap to a managed LLM (`OLLYCHAT_ANTHROPIC_API_KEY`,
  `OLLYCHAT_OPENAI_API_KEY`) and remove the ollama service.
- **Grafana:** unchanged — O11yBot adds read + write load proportional to user
  activity. Budget ~5 API calls per chat turn.

---

## Next steps

- **[VALIDATION.md](VALIDATION.md)** — end-to-end scenarios to run after every
  deploy to prove the install works.
- **[ENTERPRISE.md](ENTERPRISE.md)** — deeper RBAC + hardening + scaling notes.
- **[RBAC.md](RBAC.md)** — how roles map to SA tokens and are enforced.
