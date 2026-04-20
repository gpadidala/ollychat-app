# O11yBot End-to-End Validation Guide

Step-by-step validation scenarios with expected outputs. Use this to:
- Validate a fresh deployment is working
- Reproduce bugs from user reports
- Demo the system to stakeholders
- Train new team members

## Prerequisites
- All services running (see `./tests/preflight.sh`)
- Browser open at http://localhost:3200 (admin/admin)
- O11yBot orange bubble visible in bottom-right

---

## Post-deployment smoke test (run this first)

Run this **immediately after every deploy** — 9 one-line commands cover every
critical code path. If all nine pass + the 160-test suite is green, the deploy
is validated. Only dive into the 20 scenarios below when diagnosing a specific
feature regression.

Set these in your shell once:

```bash
export ORCH=http://localhost:8000          # orchestrator URL
export MCP=http://localhost:8765           # MCP URL
export GRAFANA=http://localhost:3200       # target Grafana
export ROLE=Admin                          # role header for smoke calls
```

### SMOKE 1 — orchestrator responds

```bash
curl -fsSL $ORCH/api/v1/models | jq '.models | length'
```
**Expect:** an integer ≥ 1.

### SMOKE 2 — MCP healthy + tool catalog loaded

```bash
curl -fsSL $MCP/health | jq .
curl -fsSL $MCP/api/tools | jq '.data | length'
```
**Expect:** `{"ok":true,"tools":53,"grafana_url":"…"}` and `53`.

### SMOKE 3 — orchestrator sees the MCP

```bash
curl -fsSL $ORCH/api/v1/mcp/servers | jq '.servers[0] | {status, toolCount}'
```
**Expect:** `{"status":"connected","toolCount":53}`. If `disconnected`, re-run
[INSTALLATION.md §7](INSTALLATION.md#7-register-the-mcp-server-with-the-orchestrator).

### SMOKE 4 — read path (list dashboards)

```bash
curl -s -X POST $ORCH/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H "X-Grafana-Role: $ROLE" \
  -d '{"messages":[{"role":"user","content":"list all dashboards"}]}' \
  --max-time 15 | grep -oE '"tool_start"[^}]+' | head -1
```
**Expect:** `"tool_start", "id": "…", "name": "list_dashboards", …`.

### SMOKE 5 — fuzzy search + judge reranker

```bash
curl -s -X POST $ORCH/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H "X-Grafana-Role: $ROLE" \
  -d '{"messages":[{"role":"user","content":"oracle kpi dashbords"}]}' \
  --max-time 45 | grep -oE '"name": "list_dashboards"|Top \d+' | head -2
```
**Expect:** matches + a `Top N dashboards` line — proves local fuzzy match
+ judge output are flowing.

### SMOKE 6 — write path (smart dashboard with discovered metrics)

```bash
curl -s -X POST $ORCH/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Grafana-Role: Admin' \
  -d '{"messages":[{"role":"user","content":"create a smoke-test dashboard now"}]}' \
  --max-time 30 | grep -oE '"delta": "[^"]{1,90}' | head -3
```
**Expect:** `✅ Smart dashboard 'Smoke-Test' created with N panels from M live metrics`.
Delete it via the Grafana UI afterwards.

### SMOKE 7 — wizard flow (under-specified create)

```bash
curl -s -X POST $ORCH/api/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Grafana-Role: Admin' \
  -d '{"messages":[{"role":"user","content":"create alert for high cpu"}]}' \
  --max-time 15 | grep -oE '"name": "alert_wizard"|Datasources available'
```
**Expect:** both lines — confirms the wizard fires when required inputs are missing.

### SMOKE 8 — RBAC enforcement (viewer blocked from admin-only tool)

```bash
curl -s -X POST $MCP/api/tools/call \
  -H 'Content-Type: application/json' \
  -d '{"name":"list_users","arguments":{"role":"viewer"}}' | jq .
```
**Expect:** `{"ok":false,"error":"PermissionError","message":"Tool 'list_users' requires role 'admin'…"}`.

### SMOKE 9 — self-observability (metrics endpoint)

```bash
curl -s $MCP/metrics | grep -E "^ollychat_mcp_tool_calls_total" | head -3
```
**Expect:** at least one counter line with `{role,status,tool}` labels (any of
the earlier smoke calls populate these).

### All-in-one pass/fail

```bash
./tests/preflight.sh        # service reachability
./tests/run-all-tests.sh    # 160 assertions across 8 suites
```

**Expect:** `RESULT: ALL SUITES PASSED` at the tail.

---

## Scenario 1: Basic Chat Flow

**Goal:** Verify the widget loads, opens, and streams a response.

### Steps
1. Open http://localhost:3200 in a browser
2. See the **orange bubble** in bottom-right corner
3. Click the bubble → chat panel opens with welcome screen
4. You see 4 suggestion buttons and the user greeting "Hey Admin!"
5. Click suggestion: **"List all Grafana dashboards"**

### Expected output
- Tool call indicator appears: `list_dashboards · 114ms · ✓ OK`
- Streaming markdown response:
  ```
  **Found 113 dashboards:**
  
  • Advanced PostgreSQL Monitoring — SAMPLEF Dev
    folder: Grafana · UID: samplef-pg-advanced-v1 · Open dashboard
  • AKS — Cluster Overview & Health
    folder: Azure — Cloud Infrastructure · UID: aks-cluster-overview
  ...
  ```
- Bottom meta: `54 tok · $0.0002`

### Validation
```bash
# Check orchestrator log for the request
docker logs ollychat-orchestrator --tail 20 | grep intent.matched
# Expected: tool=list_dashboards user_msg="List all Grafana dashboards"
```

---

## Scenario 2: Category Filter — AKS Dashboards

**Goal:** Verify category routing filters dashboards by tag.

### Steps
1. Click the O11yBot bubble
2. Type: `list AKS dashboards` and press Enter

### Expected output
- Tool call: `list_dashboards · args={"tags":["aks"]} · ✓ OK`
- Response:
  ```
  Found 6 dashboards in category AKS (Azure Kubernetes Service):
  
  📁 Azure — Cloud Infrastructure
  • AKS — Cluster Overview & Health [aks, azure, cluster, kubernetes, overview]
  • AKS — Network & Service Mesh [aks, azure, kubernetes, network]
  • AKS — Node Resource Deep Dive [aks, azure, deep-dive, kubernetes]
  • AKS — Pod & Workload Analytics [aks, azure, deployment, kubernetes]
  • AKS — Storage & Persistent Volumes [aks, azure, kubernetes, pv, pvc]
  • Azure — AKS Kubernetes Cluster [aks, azure, kubernetes]
  ```

### Validation
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"list AKS dashboards"}],"stream":true}' \
  | grep -o "aks" | head -1
# Expected: "aks" appears multiple times
```

---

## Scenario 3: Service-Specific Search

**Goal:** Verify service name extraction works.

### Steps
1. In O11yBot, type: `payment-service dashboards`
2. Or: `dashboards for api-gateway`

### Expected output
- Tool call: `search_dashboards · args={"query":"payment-service"}`
- Response either shows matching dashboards or "No dashboards found for service payment-service"

### Validation
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"payment-service dashboards"}],"stream":true}' \
  | grep tool_start
# Expected: "name":"search_dashboards","input":{"query":"payment-service"}
```

---

## Scenario 4: Grafana Health Check

**Goal:** Verify the bot can query real Grafana metadata.

### Steps
1. In O11yBot, type: `check grafana health`

### Expected output
- Tool call: `health_check · 42ms · ✓ OK`
- Response:
  ```
  Grafana Health
  • Version: 11.6.4
  • Database: ✅ ok
  • Enterprise: false
  ```

### Validation
```bash
curl -X POST http://localhost:8000/api/v1/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"server_name":"ollychat-mcp-grafana","tool_name":"health_check","arguments":{}}' \
  | python3 -m json.tool
# Expected: "version": "11.6.4", "database": "ok"
```

---

## Scenario 5: Multi-Page Navigation (bot follows)

**Goal:** Verify widget persists across Grafana pages.

### Steps
1. On Grafana Home page, open O11yBot
2. Type a message, see response
3. Navigate to **Dashboards → AKS — Cluster Overview**
4. O11yBot is still visible in bottom-right
5. Previous conversation is still there (same user's localStorage)
6. Navigate to **Explore → Loki**
7. Bot still visible, history preserved

### Expected
- Orange bubble visible on every page
- Chat history persists across navigation (stored in `localStorage["o11ybot-admin"]`)
- Different users get different histories

### Validation
```javascript
// In browser DevTools console:
localStorage.getItem("o11ybot-admin")
// Expected: JSON with msgs array, position, mode
```

---

## Scenario 6: Window Modes

**Goal:** Verify all 4 window modes work.

### Steps
1. Open O11yBot → **Normal mode** (440×600 panel)
2. Click **Maximize (□)** → Overlay 75% of viewport with blur backdrop
3. Click **Fullscreen (⛶)** → Full 100vw × 100vh takeover
4. Press **Esc** → Returns to Normal mode
5. Click **Minimize (−)** → Collapses to orange bubble
6. Click bubble → Re-opens in Normal mode, history preserved

### Validation
- Position can be dragged by header
- Resize from bottom-right corner (Normal only)
- `localStorage["o11ybot-admin"]` stores `mode`, `posX`, `posY`

---

## Scenario 7: PII Detection

**Goal:** Verify PII scanner works.

### Steps

```bash
# Email detection
curl -X POST http://localhost:8000/api/v1/guardrails/scan \
  -H "Content-Type: application/json" \
  -d '{"text":"Contact: user@example.com"}' | jq
```

### Expected
```json
{
  "has_pii": true,
  "redacted_text": "Contact: [EMAIL_REDACTED]",
  "matches": [{"type": "email", "start": 9, "end": 25, "confidence": 0.95}]
}
```

### Multi-type test
```bash
curl -X POST http://localhost:8000/api/v1/guardrails/scan \
  -H "Content-Type: application/json" \
  -d '{"text":"Email: a@b.com, SSN: 123-45-6789, AWS: AKIAIOSFODNN7EXAMPLE"}' | jq
```

### Expected
3 distinct types detected: `email`, `ssn`, `api_key_aws`.

---

## Scenario 8: Per-User History Isolation

**Goal:** Verify different Grafana users get different chat histories.

### Steps
1. Login as `admin` → send 2 messages
2. Logout, create user `jane.doe` with Viewer role
3. Login as `jane.doe` → open O11yBot
4. **Expected:** fresh welcome screen (no admin's messages visible)
5. Send 1 message as jane
6. Check localStorage:

```javascript
localStorage.getItem("o11ybot-admin")     // admin's 2 messages
localStorage.getItem("o11ybot-jane.doe")  // jane's 1 message
```

---

## Scenario 9: RBAC Enforcement

**Goal:** Verify viewer role can't call admin-only tools.

### Steps
```bash
# Try calling list_users (requires admin) as the default viewer-role O11yBot MCP
curl -X POST http://localhost:8000/api/v1/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"server_name":"ollychat-mcp-grafana","tool_name":"list_users","arguments":{}}'
```

### Expected
```json
{
  "ok": false,
  "error": "HTTP 403: {\"ok\":false,\"error\":\"PermissionError\",\"message\":\"Tool 'list_users' requires role 'admin', but caller has role 'viewer'.\"}",
  "duration_ms": 23
}
```

---

## Scenario 10: LLM Fallback (non-intent query)

**Goal:** Verify open-ended questions hit the LLM, not a tool.

### Steps
1. In O11yBot, type: `what is PromQL?`

### Expected
- No `tool_start` event
- Direct LLM streaming response
- Classified as `promql_help` in orchestrator logs
- Response contains code fence:
  ```
  ```promql
  rate(http_requests_total[5m])
  ```
  Replace http_requests_total with your actual metric.
  ```

### Validation
```bash
docker logs ollychat-orchestrator --tail 20 | grep query.classified
# Expected: type=promql_help user_msg="what is PromQL?"
```

---

## Scenario 11: Incident Analysis Prompt

**Goal:** Verify incident queries use the structured RED-methodology prompt.

### Steps
1. Type: `why is payment service slow?`

### Expected
Response uses structured format:
- **Symptom:** one-line description
- **Scope:** services + timeframe
- **Hypothesis:** ranked list
- **Next check:** specific query

Orchestrator logs show `type=incident_analysis`.

---

## Scenario 12: Observability Q&A with Few-Shot

**Goal:** Verify few-shot examples prime the model.

### Steps
1. Type: `what is the RED method?`

### Expected
- Classified as `observability_qa` (T=0.2, max=500)
- Response mentions **R**ate, **E**rrors, **D**uration
- Bullet-pointed, concise

---

## Scenario 13: Concurrent Requests

**Goal:** Verify orchestrator handles parallel requests.

### Steps
```bash
# Fire 5 requests in parallel
for i in 1 2 3 4 5; do
  (curl -s -X POST http://localhost:8000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"list datasources"}],"stream":true}' \
    -o /dev/null -w "Req $i: HTTP %{http_code}\n") &
done
wait
```

### Expected
All 5 requests return HTTP 200, none time out.

---

## Scenario 14: Large Payload

**Goal:** Verify large messages are accepted.

### Steps
```bash
# 10KB message
python3 -c "
import json, urllib.request
big = 'x' * 10000
data = json.dumps({
  'messages': [{'role':'user','content': big}],
  'stream': True,
  'max_tokens': 20
}).encode()
req = urllib.request.Request(
  'http://localhost:8000/api/v1/chat',
  data=data,
  headers={'Content-Type':'application/json'}
)
r = urllib.request.urlopen(req)
print('Status:', r.status)
"
```

### Expected
HTTP 200, graceful handling (either LLM truncates or stream starts normally).

---

## Scenario 15: Unicode + Emoji

**Goal:** Verify international characters work end-to-end.

### Steps
1. Type: `Hello 👋 日本語 🎉`

### Expected
- HTTP 200
- Response is coherent (may or may not use the emoji back)
- No encoding errors in logs

---

## Scenario 16: Browser Cache Busting

**Goal:** Verify widget updates reach the browser.

### Steps
1. Open DevTools → Network tab → filter "widget"
2. Navigate to http://localhost:3200
3. See the script load with URL like: `o11ybot-widget.js?v=1713456789012`

### Expected
Each page load appends fresh `?v=${Date.now()}` → browser always fetches latest.

---

## Scenario 17: Window Drag Persistence

**Goal:** Verify dragged position is remembered.

### Steps
1. Open O11yBot
2. Drag the header to top-left corner
3. Close (×) or minimize
4. Reload the page
5. Re-open O11yBot

### Expected
Widget opens at the same top-left position (from `posX`/`posY` in localStorage).

---

## Scenario 18: Window Controls — All 5

**Goal:** Verify every window control works.

### Steps & Expected

| Button | Click → |
|---|---|
| **Clear (🗑)** | Empties chat history, keeps widget open |
| **Minimize (−)** | Collapses to orange bubble |
| **Maximize (□)** | 75vw × 85vh overlay with blur |
| **Fullscreen (⛶)** | 100vw × 100vh takeover |
| **Close (×)** | Collapses to bubble + resets mode to "normal" |

### Keyboard
- `Enter` → send message (Shift+Enter for newline)
- `Esc` → exit fullscreen / maximized

---

## Scenario 19: MCP Server Reconnection

**Goal:** Verify graceful handling when MCP is down.

### Steps
```bash
# Stop O11yBot MCP
pkill -f "grafana-mcp serve"

# Try to query
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"list dashboards"}]}'

# Response should include error, no crash
```

Then restart and re-register:
```bash
cd ../O11yBot MCP && .venv/bin/grafana-mcp serve --port 8765 &
sleep 3
curl -X POST http://localhost:8000/api/v1/mcp/servers \
  -H "Content-Type: application/json" \
  -d '{"name":"ollychat-mcp-grafana","url":"http://host.docker.internal:8765","transport":"sse","auth_method":"none"}'
```

### Expected
- No orchestrator crash
- After re-register, queries work again immediately

---

## Scenario 20: Dashboard Count Consistency

**Goal:** Verify MCP returns exactly what Grafana has.

### Steps
```bash
# Grafana direct
GRAFANA_COUNT=$(curl -s "http://admin:admin@localhost:3200/api/search?type=dash-db" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))")

# Via MCP
MCP_COUNT=$(curl -s -X POST http://localhost:8000/api/v1/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"server_name":"ollychat-mcp-grafana","tool_name":"list_dashboards","arguments":{"limit":200}}' \
  | python3 -c "import sys,json;d=json.loads(sys.stdin.read(),strict=False);print(len(d['data']))")

echo "Grafana: $GRAFANA_COUNT · MCP: $MCP_COUNT"
```

### Expected
Both numbers equal (113 in the reference environment).

---

## Quick Validation Checklist

Run through in order before declaring "everything works":

- [ ] `./tests/preflight.sh` passes
- [ ] `./tests/run-all-tests.sh` → 147/147 passing
- [ ] Orange bubble visible on http://localhost:3200 (any page)
- [ ] Click bubble → chat opens in < 100ms
- [ ] "list all dashboards" → 113 dashboards in response
- [ ] "list AKS dashboards" → 6 AKS-tagged dashboards
- [ ] "check grafana health" → version 11.6.4 · DB ok
- [ ] Navigate to different Grafana pages → bubble stays
- [ ] Maximize → blur backdrop overlay appears
- [ ] Fullscreen → full takeover, Esc exits
- [ ] Clear button → wipes history
- [ ] Close button → back to bubble
- [ ] Drag header → widget moves, position persists on reload
- [ ] Console log: `[O11yBot] v1.3.x ready. User: admin`
- [ ] Orchestrator logs show `query.classified` or `intent.matched` events

If **any** step fails, check the bug log in [TESTING.md](TESTING.md#bug-fixes-log).

---

## Debugging

### Widget shows empty bubble after asking
Usually a CRLF parsing bug (already fixed). Check widget version in console:
```javascript
// DevTools console
console.log(document.querySelector("#o11ybot-root > *").outerHTML);
```

Hard-refresh with Cmd+Shift+R to bypass browser cache.

### "Failed to fetch" error
CORS issue — orchestrator may have restarted with different CORS config. Check:
```bash
curl -I -X OPTIONS http://localhost:8000/api/v1/chat \
  -H "Origin: http://localhost:3200" \
  -H "Access-Control-Request-Method: POST" | grep access-control
```

Should include `access-control-allow-origin: http://localhost:3200`.

### Intent not matching expected tool
Enable verbose logging:
```bash
docker logs -f ollychat-orchestrator | grep -E "intent|query\.classified"
```

Send query in widget, watch for matching event.

### Tool returns 0 results but data exists
O11yBot MCP uses AND for tag filters. Check the `tags` arg in logs — if it has multiple tags, we might be filtering too strictly. Verify by calling list_dashboards with a single tag manually.
