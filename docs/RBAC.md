# O11yBot RBAC — Single MCP Server, Multi-Role Tokens

## Design Decision: One MCP Server, Multiple Role Tokens

**We recommend running ONE Bifröst MCP server** with three Grafana service account tokens (viewer / editor / admin), **not multiple MCP servers per role**.

### Why?

| Concern | One MCP + role tokens | Multiple MCPs per role |
|---|---|---|
| **Security** | Grafana enforces RBAC via tokens — same guarantee | Same |
| **Infra** | 1 process, 1 port | 3 processes, 3 ports, 3 configs |
| **Token rotation** | 1 `.env`, 3 fields | 3 `.env` files, 1 each |
| **Debugging** | Single log stream | 3 to correlate |
| **Grafana API load** | Same (1 request per query) | Same |
| **Cost** | Lower (1 MCP) | Higher (3x) |

Only split MCPs if they target **different Grafana instances** (dev/staging/prod).

---

## Architecture

```
Browser (User: Jane, Role: Editor)
     │
     │ X-Grafana-Role: Editor
     ▼
Orchestrator (:8000)
     │  maps Grafana role → O11yBot MCP role
     │  → role = "editor"
     ▼
MCP Client Manager
     │  call_tool(..., role="editor")
     │  POST /api/tools/call with arguments.role = "editor"
     ▼
O11yBot MCP Server (:8765)
     │  picks the EDITOR token from config
     │  GET /api/v1/dashboards  (Authorization: Bearer glsa_editor_...)
     ▼
Grafana API
     │  enforces RBAC on the Editor token
     ▼
Response (with only what Editor can see)
```

---

## Setting Up the 3 Service Account Tokens

Run these commands **once** against your production Grafana to create the three role-based SA tokens O11yBot MCP needs.

### 1. Viewer token (read-only)

```bash
SA_V=$(curl -s -X POST http://admin:admin@your-grafana:3000/api/serviceaccounts \
  -H "Content-Type: application/json" \
  -d '{"name":"ollybot-viewer","role":"Viewer"}')
SA_V_ID=$(echo "$SA_V" | jq -r '.id')

VIEWER_TOKEN=$(curl -s -X POST "http://admin:admin@your-grafana:3000/api/serviceaccounts/$SA_V_ID/tokens" \
  -H "Content-Type: application/json" \
  -d '{"name":"ollybot-viewer-token"}' | jq -r '.key')

echo "VIEWER: $VIEWER_TOKEN"
```

### 2. Editor token (read + modify dashboards, silence alerts)

```bash
SA_E=$(curl -s -X POST http://admin:admin@your-grafana:3000/api/serviceaccounts \
  -H "Content-Type: application/json" \
  -d '{"name":"ollybot-editor","role":"Editor"}')
SA_E_ID=$(echo "$SA_E" | jq -r '.id')

EDITOR_TOKEN=$(curl -s -X POST "http://admin:admin@your-grafana:3000/api/serviceaccounts/$SA_E_ID/tokens" \
  -H "Content-Type: application/json" \
  -d '{"name":"ollybot-editor-token"}' | jq -r '.key')

echo "EDITOR: $EDITOR_TOKEN"
```

### 3. Admin token (read everything, list users, create datasources)

```bash
SA_A=$(curl -s -X POST http://admin:admin@your-grafana:3000/api/serviceaccounts \
  -H "Content-Type: application/json" \
  -d '{"name":"ollybot-admin","role":"Admin"}')
SA_A_ID=$(echo "$SA_A" | jq -r '.id')

ADMIN_TOKEN=$(curl -s -X POST "http://admin:admin@your-grafana:3000/api/serviceaccounts/$SA_A_ID/tokens" \
  -H "Content-Type: application/json" \
  -d '{"name":"ollybot-admin-token"}' | jq -r '.key')

echo "ADMIN: $ADMIN_TOKEN"
```

### 4. Wire tokens into O11yBot MCP `.env`

```bash
cat >> O11yBot MCP/.env <<EOF
GRAFANA_MCP_ENVIRONMENTS__DEV__SERVICE_ACCOUNTS__VIEWER=$VIEWER_TOKEN
GRAFANA_MCP_ENVIRONMENTS__DEV__SERVICE_ACCOUNTS__EDITOR=$EDITOR_TOKEN
GRAFANA_MCP_ENVIRONMENTS__DEV__SERVICE_ACCOUNTS__ADMIN=$ADMIN_TOKEN
EOF
```

Restart O11yBot MCP:
```bash
pkill -f grafana-mcp
.venv/bin/grafana-mcp serve --transport sse --port 8765 &
```

---

## Verifying RBAC

Run the RBAC test suite:
```bash
cd tests && ./suite8-rbac.sh
```

Manual verification:

```bash
# As Viewer — listing users should fail
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Viewer" \
  -d '{"messages":[{"role":"user","content":"list users"}],"stream":true}' \
  | grep -c PermissionError
# Expected: ≥1 (permission denied)

# As Admin — should succeed
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Admin" \
  -d '{"messages":[{"role":"user","content":"list users"}],"stream":true}' \
  | grep -c PermissionError
# Expected: 0 (allowed)
```

---

## Tool → Required Role Matrix

| Tool | viewer | editor | admin |
|---|---|---|---|
| `list_dashboards` | ✓ | ✓ | ✓ |
| `search_dashboards` | ✓ | ✓ | ✓ |
| `get_dashboard` | ✓ | ✓ | ✓ |
| `get_dashboard_panels` | ✓ | ✓ | ✓ |
| `list_datasources` | ✓ | ✓ | ✓ |
| `get_datasource` | ✓ | ✓ | ✓ |
| `query_datasource` | ✓ | ✓ | ✓ |
| `list_folders` | ✓ | ✓ | ✓ |
| `list_alert_rules` | ✓ | ✓ | ✓ |
| `get_alert_rule` | ✓ | ✓ | ✓ |
| `list_alert_instances` | ✓ | ✓ | ✓ |
| `silence_alert` | ✗ | ✓ | ✓ |
| `health_check` | ✓ | ✓ | ✓ |
| `get_server_info` | ✓ | ✓ | ✓ |
| `list_users` | ✗ | ✗ | ✓ |
| `list_service_accounts` | ✗ | ✗ | ✓ |

Enforced by O11yBot MCP's `TOOL_MINIMUM_ROLE` map in `packages/core/src/grafana_mcp/rbac.py`.

---

## Role Mapping (Grafana → O11yBot MCP)

The orchestrator normalizes Grafana's role headers to O11yBot MCP's role names:

| `X-Grafana-Role` header value | Mapped O11yBot MCP role |
|---|---|
| `Admin` | `admin` |
| `Grafana Admin` | `admin` |
| `Editor` | `editor` |
| `Viewer` | `viewer` |
| (missing / unknown) | `viewer` (safest default) |

Implementation: `orchestrator/routers/chat.py` lines 64-75.

---

## Grafana Enterprise RBAC Integration

For Grafana Enterprise with fine-grained RBAC (role assignments like "dashboards:read"), the tokens above still work — they inherit the permissions of the Role (Viewer/Editor/Admin) assigned at creation.

To use **custom Enterprise roles** (e.g., a "Dashboard Creator" role without admin):
1. Create the custom role in Grafana Enterprise Admin → Users → Service Accounts
2. Assign it to a new SA (instead of Viewer/Editor/Admin)
3. Generate a token from that SA
4. Add to O11yBot MCP `.env` as one of the 3 slots (or extend O11yBot MCP to support more)

Note: O11yBot MCP's `TOOL_MINIMUM_ROLE` model has **exactly 3 roles**. For 4+ custom roles, the cleanest path is to run **multiple O11yBot MCP instances**, one per role bucket — that's the legitimate multi-MCP use case.

---

## Troubleshooting

### "Tool X requires role 'admin', but caller has role 'viewer'"

Working as intended — the user's Grafana role doesn't allow this tool. Options:
1. Promote the user in Grafana (Admin → Users)
2. Assign a Grafana Enterprise role that permits the action

### "HTTP 401: Unauthorized" when calling O11yBot MCP

The SA token is invalid or expired. Regenerate with the steps above and update `.env`.

### Bot answers "I don't have access to Grafana" even after setup

This happens when the LLM fallback kicks in (not an MCP tool call). Fixed in v1.7: there's now a `help` intent that answers capabilities questions with real tool info, bypassing the LLM.

### All tools fail with "MCP server ollychat-mcp-grafana not connected"

Re-register after container restart:
```bash
curl -X POST http://localhost:8000/api/v1/mcp/servers \
  -H "Content-Type: application/json" \
  -d '{"name":"ollychat-mcp-grafana","url":"http://host.docker.internal:8765","transport":"sse","auth_method":"none"}'
```

This is in-memory state — will go away on orchestrator rebuild. For production, persist to Postgres (on roadmap).

---

## Summary

- **One** O11yBot MCP server — easier, same security
- **Three** role-based tokens (viewer/editor/admin) in `.env`
- Orchestrator reads `X-Grafana-Role` → passes to O11yBot MCP → uses right token
- O11yBot MCP's `TOOL_MINIMUM_ROLE` enforces what each role can do
- 13 automated RBAC tests verify the whole flow
