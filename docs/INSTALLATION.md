# O11yBot — Installation Guide

Two installs: the **bundled demo** (everything inside this repo, one command)
and **production** (point the plugin at an existing Grafana).

> Bundled install: **3 minutes**. Production install: **15–30 minutes**.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker Engine | ≥ 24 | — |
| Docker Compose | ≥ v2.20 | compose v2 syntax + `!override` tag |
| 4 GB free RAM | — | Ollama + Grafana + LGTM comfortably |
| Open ports | 3002, 8000, 8765, 11434 | all bindable to other host ports in `.env` |

**Optional:**
- `curl` + `jq` for CLI validation
- An OpenAI / Anthropic / Gemini / Bedrock key if you don't want to use local Ollama
- Node 20+ **only** if you want to rebuild the widget source (it ships pre-built in `dist/`)

---

## Install A — Bundled demo (one command)

```bash
git clone https://github.com/gpadidala/ollychat-app.git
cd ollychat-app
make up
```

That's the whole install. No manual SA-token creation, no `curl -X POST /mcp/servers`.
On first run, `make up` boots **10 services**, mints three service-account tokens
in the bundled Grafana via `scripts/bootstrap-tokens.sh`, writes them back to `.env`,
and the orchestrator auto-registers the MCP on startup (see `orchestrator/main.py`
lifespan hook).

**When it's done:**
- Grafana UI — **http://localhost:3002** (admin / admin)
- Orchestrator API — **http://localhost:8000**
- MCP server — **http://localhost:8765/health**
- Ollama — **http://localhost:11434**

Open Grafana → click the orange bubble bottom-right → type `list all dashboards`.

### Make targets

| Command | What it does |
|---|---|
| `make up` | Boot everything + auto-bootstrap tokens (idempotent) |
| `make down` | Stop all services, keep data volumes |
| `make restart` | `make down && make up` |
| `make rebuild` | Rebuild images without cache, then boot |
| `make reset` | **DANGER** — drop all data volumes, then rebuild + boot |
| `make logs` | Tail every service |
| `make status` | Service health at a glance |
| `make test` | Full 160-test suite |

---

## Install B — Production (against your own Grafana)

Use this when you already have a Grafana and just want to drop O11yBot's
**widget + plugin + orchestrator + MCP** in front of it.

### B.1 — Create 3 service-account tokens in the target Grafana

O11yBot enforces RBAC at the MCP layer with per-role tokens. Create them in the
Grafana you're targeting.

**Via UI:** Administration → Users and access → Service accounts → Add service account.
Create three: `o11ybot-viewer` (Viewer), `o11ybot-editor` (Editor), `o11ybot-admin` (Admin).
For each, **Add token** → copy the `glsa_…` value.

**Via CLI:**

```bash
export GF_URL=https://grafana.yourco.com
export GF_ADMIN_AUTH=admin:<password>

for role in Viewer Editor Admin; do
  sa=$(curl -sS -u "$GF_ADMIN_AUTH" -H 'Content-Type: application/json' \
        -d "{\"name\":\"o11ybot-${role,,}\",\"role\":\"$role\"}" \
        "$GF_URL/api/serviceaccounts")
  sa_id=$(echo "$sa" | jq -r .id)
  tok=$(curl -sS -u "$GF_ADMIN_AUTH" -H 'Content-Type: application/json' \
        -d "{\"name\":\"o11ybot-${role,,}-token\"}" \
        "$GF_URL/api/serviceaccounts/$sa_id/tokens" | jq -r .key)
  echo "${role^^}_TOKEN=$tok"
done
```

Save the three `glsa_…` values — they go into `.env` next.

**Grafana Enterprise note:** if you use fine-grained RBAC roles, attach them to
the three service accounts. The plugin honours whatever role Grafana puts in the
session (`X-Grafana-Role` header) — Enterprise SSO / SAML flows through unchanged.

### B.2 — Configure `.env`

```bash
cp .env.example .env
$EDITOR .env
```

Fill in:

```env
GRAFANA_URL=https://grafana.yourco.com
GRAFANA_VIEWER_TOKEN=glsa_xxx
GRAFANA_EDITOR_TOKEN=glsa_yyy
GRAFANA_ADMIN_TOKEN=glsa_zzz
GRAFANA_TLS_VERIFY=true       # set false only for self-signed dev certs
OLLYCHAT_DEFAULT_MODEL=qwen2.5:0.5b   # or gpt-4o / claude-sonnet-4-6 / etc.
```

### B.3 — Install the widget + plugin into your Grafana host

Two files need to land on the Grafana host:

```bash
sudo cp -r dist /var/lib/grafana/plugins/gopal-ollychat-app
sudo cp grafana-index.html /usr/share/grafana/public/views/index.html
```

Allow unsigned plugins and restart Grafana:

```ini
# /etc/grafana/grafana.ini
[plugins]
allow_loading_unsigned_plugins = gopal-ollychat-app
```

Or via env: `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=gopal-ollychat-app`.
Then `systemctl restart grafana-server`.

**Helm-deployed Grafana:** add an init-container that downloads
`gopal-ollychat-app.zip` into the plugins volume — sample in
[DEPLOYMENT.md §Path B](DEPLOYMENT.md).

### B.4 — Boot the orchestrator + MCP

```bash
docker compose up -d ollychat-orchestrator ollychat-mcp ollama otel-collector
```

The orchestrator auto-registers with the MCP on startup. No manual curl.

Confirm:

```bash
curl -s http://localhost:8000/api/v1/mcp/servers | jq '.servers[0] | {status, toolCount}'
# expect: {"status":"connected","toolCount":53}
```

---

## Corporate-laptop builds (TLS interception, pypi blocked)

Both Dockerfiles accept build-time args that activate through `.env`:

```env
HTTP_PROXY=http://proxy.corp:3128
HTTPS_PROXY=http://proxy.corp:3128
NO_PROXY=localhost,127.0.0.1,.corp
PIP_INDEX_URL=https://artifactory.corp/api/pypi/pypi/simple
PIP_TRUSTED_HOST=artifactory.corp
CA_CERT_PATH=corp-ca.crt       # drop your CA at repo root, point at it
```

Compose forwards these to every Python image. When `CA_CERT_PATH` is a valid PEM,
the Dockerfile installs `ca-certificates` and runs `update-ca-certificates`.
When it's not, the step is a no-op — normal installs aren't forced to install extras.

Then just `make up` as usual.

---

## First smoke test

After `make up`:

```bash
# 1. Grafana health
curl -fsSL http://localhost:3002/api/health | jq .database
# → "ok"

# 2. MCP tool catalog
curl -fsSL http://localhost:8765/api/tools | jq '.data | length'
# → 53

# 3. Orchestrator sees MCP
curl -fsSL http://localhost:8000/api/v1/mcp/servers | jq '.servers[0].toolCount'
# → 53

# 4. End-to-end chat
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Grafana-Role: Admin' \
  -d '{"messages":[{"role":"user","content":"list all dashboards"}]}' \
  --max-time 15 | grep -oE '"delta": "[^"]{1,80}' | head -1
# → "**Found 100 dashboards:**\n\n- **Advanced PostgreSQL..."
```

The full 9-command post-deploy check is in [VALIDATION.md](VALIDATION.md).

---

## Run the automated suite

```bash
make test
# or:
cd tests && ./preflight.sh && ./run-all-tests.sh
```

**Expected tail:** `RESULT: ALL SUITES PASSED` — 160/160 across 8 suites.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Widget doesn't appear | Confirm `grafana-index.html` is mounted at `/usr/share/grafana/public/views/index.html`, restart Grafana |
| `MCP server not connected` in UI | Hit `POST /api/v1/mcp/servers/bifrost-grafana/reconnect` or `make restart ollychat-orchestrator` |
| `HTTP 401` from Grafana | Wrong / expired SA token in `.env` — re-run §B.1 |
| `HTTP 403` on a tool | Caller role below `TOOL_MINIMUM_ROLE` — hit with a higher-role SA or relax the role map in `mcp-server/rbac.py` |
| Panels show "No data" | Real metrics don't match the topic regex — the MCP already auto-discovers; if empty, your datasource genuinely has no matching series |
| `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS` not honoured | Upgrade Grafana to ≥ 8.0 |
| Ollama OOM | Use `qwen2.5:0.5b` (500 MB) or swap to a cloud model |
| `pip install` fails during build | Corporate CA / proxy — set `HTTPS_PROXY`, `PIP_INDEX_URL`, `CA_CERT_PATH` in `.env` (see above) |
| Bundled Grafana port 3002 collides | Change `GRAFANA_EXTERNAL_PORT` in `.env` |

---

## Uninstall

```bash
# Data volumes too (DANGER):
make reset && make down

# Just stop, keep volumes:
make down

# Remove plugin from an existing Grafana host:
sudo rm -rf /var/lib/grafana/plugins/gopal-ollychat-app
sudo cp /usr/share/grafana/public/views/index.html.bak \
        /usr/share/grafana/public/views/index.html
systemctl restart grafana-server
```

Revoke the three SA tokens in Grafana → Service accounts.

---

## Next

- **[VALIDATION.md](VALIDATION.md)** — 9-command smoke test + 20 end-to-end scenarios
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — production paths (Docker Compose / K8s Helm / systemd)
- **[USE_CASES.md](USE_CASES.md)** — the full 53-tool capability matrix
- **[ENTERPRISE.md](ENTERPRISE.md)** — RBAC, self-observability, hardening
