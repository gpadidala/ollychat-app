# O11yBot — Installation Guide

End-to-end install for **Grafana OSS** and **Grafana Enterprise**. Both paths land
you at the same runtime — the differences are where the plugin lives and how the
service-account tokens are created.

> Expected time: **15 minutes** for the local dev stack, **30–45 minutes** for a
> production install against an existing Grafana.

---

## 1. Prerequisites

| Requirement | Version | Why |
|---|---|---|
| Docker Engine | ≥ 24 | runs the orchestrator + MCP + LLM |
| Docker Compose | ≥ v2.20 | one-shot stack boot |
| Grafana | 10.0+ (OSS or Enterprise) | the host you're deploying the plugin into |
| Admin access to Grafana | yes | to create service accounts + tokens |
| 4 GB free RAM | — | Ollama + Grafana + LGTM comfortably |
| Open ports | 3002, 8000, 8765, 11434 | local dev; all bindable to any host port |

Optional:

- `curl` + `jq` for command-line validation
- Node 18+ if you want to rebuild the widget source
- An OpenAI / Anthropic key for non-local LLMs

---

## 2. Clone the repo

```bash
git clone https://github.com/gpadidala/ollychat-app.git
cd ollychat-app
```

All artefacts — plugin, MCP server, orchestrator, tests — are in this one repo.

---

## 3. Create Grafana service-account tokens

O11yBot uses **three** service accounts with distinct roles so RBAC can be
enforced at the MCP layer. Create them in the Grafana you're deploying against.

### 3a. OSS Grafana (admin → service accounts UI)

1. Sign in as an org admin.
2. **Administration → Users and access → Service accounts → Add service account**.
3. Create three accounts:

   | Name | Role |
   |---|---|
   | `o11ybot-viewer` | Viewer |
   | `o11ybot-editor` | Editor |
   | `o11ybot-admin`  | Admin |

4. For each, click the account → **Add token** → copy the `glsa_…` value.

### 3b. Grafana Enterprise — same UI + fine-grained RBAC (optional)

Enterprise lets you attach custom RBAC roles to each SA. If you want to lock
things down further than viewer/editor/admin, do it *after* the basic setup
works — add scoped roles via **Administration → Users and access → RBAC**.
Suggested scopes per role:

| SA | Scoped permissions that are safe to grant |
|---|---|
| viewer  | `dashboards:read`, `datasources:read`, `alert.rules:read`, `folders:read`, `plugins:read` |
| editor  | viewer + `dashboards:write`, `folders:write`, `alert.rules:write`, `alert.silences:write`, `annotations:write` |
| admin   | editor + `users:read`, `serviceaccounts:read`, `dashboards:delete`, `folders:delete`, `alert.rules:delete` |

Enterprise also supports **SAML / OAuth SSO**; the plugin honours whatever
Grafana puts in `X-Grafana-User` / `X-Grafana-Role`, so SSO just works.

### 3c. CLI shortcut (OSS + Enterprise, Grafana API)

```bash
export GF_URL=http://localhost:3200
export GF_ADMIN_AUTH=admin:admin   # replace with your own admin creds

for role in Viewer Editor Admin; do
  SA=$(curl -s -u "$GF_ADMIN_AUTH" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"o11ybot-${role,,}\",\"role\":\"$role\"}" \
    $GF_URL/api/serviceaccounts)
  SA_ID=$(echo "$SA" | jq -r .id)
  TOKEN=$(curl -s -u "$GF_ADMIN_AUTH" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"o11ybot-${role,,}-token\"}" \
    $GF_URL/api/serviceaccounts/$SA_ID/tokens | jq -r .key)
  echo "${role^^}_TOKEN=$TOKEN"
done
```

Save the three `glsa_…` tokens — they go into `.env` next.

---

## 4. Configure `.env`

```bash
cp .env.example .env
$EDITOR .env
```

Fill in:

```env
# Target Grafana (any OSS or Enterprise instance)
GRAFANA_URL=http://host.docker.internal:3000

# Role-based service-account tokens — from step 3
GRAFANA_VIEWER_TOKEN=glsa_xxx
GRAFANA_EDITOR_TOKEN=glsa_yyy
GRAFANA_ADMIN_TOKEN=glsa_zzz

# TLS (set to false for self-signed dev certs)
GRAFANA_TLS_VERIFY=true

# LLM — local Ollama is the default
OLLYCHAT_DEFAULT_MODEL=qwen2.5:0.5b

# Optional cloud LLMs
OLLYCHAT_ANTHROPIC_API_KEY=
OLLYCHAT_OPENAI_API_KEY=
```

If you only have **one** token, set `GRAFANA_TOKEN=glsa_xxx` and all three roles
use the same credential — fine for a single-tenant demo, not for prod.

---

## 5. Install the plugin

### 5a. Local dev — skip the install, use the bundled Grafana

```bash
docker compose up -d
```

This boots a Grafana on **:3002** that already has the plugin mounted from
`dist/`. The rest of this section is only for installing into *your own*
existing Grafana.

### 5b. Target an existing OSS Grafana

1. Copy `dist/` into Grafana's plugin directory:

   ```bash
   sudo cp -r dist /var/lib/grafana/plugins/gopal-ollychat-app
   sudo chown -R grafana:grafana /var/lib/grafana/plugins/gopal-ollychat-app
   ```

2. Allow unsigned plugins (dev-only). Edit `/etc/grafana/grafana.ini`:

   ```ini
   [plugins]
   allow_loading_unsigned_plugins = gopal-ollychat-app
   ```

   Or set the env var: `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=gopal-ollychat-app`

3. Mount the widget into Grafana's index template so it appears on every page:

   ```bash
   sudo cp grafana-index.html /usr/share/grafana/public/views/index.html
   ```

4. `systemctl restart grafana-server`

### 5c. Target Grafana Enterprise

Same as OSS, **plus**:

1. Have the plugin **signed** by Grafana for production. Until then, the
   `allow_loading_unsigned_plugins` setting works. Contact Grafana Labs to get
   the plugin signed or keep the unsigned flag in a locked-down environment.

2. If your Enterprise Grafana runs behind an IdP (Okta / Azure AD / etc.), the
   SSO session is passed through automatically — no extra work required. The
   widget reads `window.grafanaBootData.user` to identify the caller.

3. Enterprise features the plugin respects automatically:
   - **RBAC custom roles** — enforced at the Grafana API level per token
   - **Audit log** — every MCP call shows up in Enterprise's audit trail
     (each SA token is a distinct principal)
   - **Fine-grained SAML mapping** — pass through without code changes

### 5d. Kubernetes / helm-based Grafana

If you run Grafana via the official Helm chart, add the plugin as an extra
volume and mount:

```yaml
# values.yaml
extraInitContainers:
  - name: load-o11ybot
    image: busybox:1.36
    command: ['sh', '-c', 'wget -O /plugins/o11ybot.zip https://github.com/gpadidala/ollychat-app/releases/latest/download/gopal-ollychat-app.zip && unzip -d /plugins /plugins/o11ybot.zip']
    volumeMounts:
      - name: plugins
        mountPath: /plugins

extraVolumeMounts:
  - name: plugins
    mountPath: /var/lib/grafana/plugins

env:
  GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS: gopal-ollychat-app
```

---

## 6. Boot the backend

```bash
docker compose up -d
```

Wait ~20 seconds, then confirm:

```bash
docker compose ps
# all services should show "Up (healthy)" or "Up"

curl http://localhost:8000/api/v1/models   # orchestrator
curl http://localhost:8765/health          # MCP server
curl http://localhost:11434/api/tags       # Ollama
```

---

## 7. Register the MCP server with the orchestrator

The orchestrator discovers MCP servers over HTTP. One-time registration:

```bash
curl -X POST http://localhost:8000/api/v1/mcp/servers \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "bifrost-grafana",
    "url": "http://ollychat-mcp:8765",
    "enabled": true
  }'
```

Expected response:

```json
{"ok": true, "server": {"name": "bifrost-grafana", "status": "connected", "toolCount": 53}}
```

> If you're deploying the orchestrator *outside* Docker (bare metal / pod), use
> `http://localhost:8765` or whatever DNS name resolves the MCP server.

---

## 8. First smoke test — "list dashboards"

With your own Grafana open in the browser, hit the O11yBot FAB (bottom-right
orange dot) and type:

```
list all dashboards
```

Expected:

```
Found N dashboards:
 • <Title> — folder: <Folder> [tags]
   UID: <uid> · [Open dashboard](<url>)
 …
```

If you see that, the full chain works:

```
browser → widget → orchestrator → MCP → Grafana → ...back
```

If it fails, see the [validation walkthrough](VALIDATION.md) — the first two
scenarios cover every common failure mode.

---

## 9. Run the automated suite

```bash
cd tests
./preflight.sh          # service health
./run-all-tests.sh      # 160 assertions across 8 suites
```

Expected tail:

```
Suite 1 Results: 17 passed, 0 failed
…
Suite 8 Results: 13 passed, 0 failed
║   RESULT: ALL SUITES PASSED
```

If a suite fails, the output names the exact assertion — start there. The full
breakdown lives in [TESTING.md](TESTING.md).

---

## 10. Troubleshooting — common issues

| Symptom | Root cause | Fix |
|---|---|---|
| Widget doesn't appear | Index template not replaced | Confirm `grafana-index.html` is in `/usr/share/grafana/public/views/index.html`, restart Grafana |
| `MCP server bifrost-grafana not connected` | Orchestrator lost the registration | Repeat step 7 |
| `HTTP 401` from Grafana | Wrong / expired SA token | Re-check `.env`, re-run step 3 |
| `HTTP 403` on a tool | Caller role below `TOOL_MINIMUM_ROLE` | Hit the tool with a higher-role SA or relax the role map in `mcp-server/rbac.py` |
| Panels show "No data" | Metric name doesn't exist in the datasource | O11yBot auto-discovers; if still empty, the datasource genuinely has no matching series |
| `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS` not honoured | Grafana version older than 8.0 | Upgrade Grafana |
| Ollama OOM | Local LLM too large | Use `qwen2.5:0.5b` (500 MB) or switch to a cloud model |
| CORS error in DevTools | Browser hitting orchestrator on wrong origin | Orchestrator allows `*` by default; check your reverse proxy doesn't strip the header |

---

## 11. Uninstall

```bash
docker compose down -v
sudo rm -rf /var/lib/grafana/plugins/gopal-ollychat-app
sudo cp /usr/share/grafana/public/views/index.html.bak \
        /usr/share/grafana/public/views/index.html
systemctl restart grafana-server
```

Revoke the service-account tokens in Grafana → Service accounts.

---

## Next steps

- **[DEPLOYMENT.md](DEPLOYMENT.md)** — production hardening (TLS, scaling, metrics)
- **[VALIDATION.md](VALIDATION.md)** — 20 end-to-end scenarios covering every use case
- **[USE_CASES.md](USE_CASES.md)** — the full 53-tool capability matrix
- **[RBAC.md](RBAC.md)** — how role enforcement works under the hood
