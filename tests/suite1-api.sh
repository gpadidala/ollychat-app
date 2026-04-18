#!/bin/bash
# Suite 1: API Endpoints (14 tests)
# Run: ./suite1-api.sh

PASS=0; FAIL=0
check() { if [ "$1" = "$2" ]; then echo "  PASS: $3"; PASS=$((PASS+1)); else echo "  FAIL: $3 (expected '$1', got '$2')"; FAIL=$((FAIL+1)); fi; }
has() { if echo "$1" | grep -q "$2"; then echo "  PASS: $3"; PASS=$((PASS+1)); else echo "  FAIL: $3 (missing: $2)"; FAIL=$((FAIL+1)); fi; }

echo "═══ SUITE 1: API ENDPOINTS ═══"
echo ""

# T1: Orchestrator health
echo "T1: GET /api/v1/health"
R=$(curl -s http://localhost:8000/api/v1/health)
has "$R" "healthy" "Orchestrator healthy"
has "$R" "ollychat-orchestrator" "Service name correct"

# T2: Models
echo ""
echo "T2: GET /api/v1/models"
COUNT=$(curl -s http://localhost:8000/api/v1/models | python3 -c "import sys,json;d=json.loads(sys.stdin.read(),strict=False);print(len(d['models']))")
[ "$COUNT" -ge 1 ] && echo "  PASS: Models available ($COUNT)" && PASS=$((PASS+1)) || { echo "  FAIL: No models"; FAIL=$((FAIL+1)); }

# T3: MCP servers
echo ""
echo "T3: GET /api/v1/mcp/servers"
R=$(curl -s http://localhost:8000/api/v1/mcp/servers)
STATUS=$(echo "$R" | python3 -c "import sys,json;s=json.loads(sys.stdin.read(),strict=False)['servers'];print(s[0]['status'] if s else 'none')")
check "connected" "$STATUS" "Bifrost MCP connected"
TOOLS=$(echo "$R" | python3 -c "import sys,json;s=json.loads(sys.stdin.read(),strict=False)['servers'];print(s[0]['toolCount'] if s else 0)")
check "16" "$TOOLS" "16 tools discovered"

# T4: MCP tools
echo ""
echo "T4: GET /api/v1/mcp/tools"
COUNT=$(curl -s http://localhost:8000/api/v1/mcp/tools | python3 -c "import sys,json;d=json.loads(sys.stdin.read(),strict=False);print(len(d['tools']))")
check "16" "$COUNT" "16 tools registered"

# T5: Skills
echo ""
echo "T5: GET /api/v1/skills"
COUNT=$(curl -s http://localhost:8000/api/v1/skills | python3 -c "import sys,json;d=json.loads(sys.stdin.read(),strict=False);print(len(d['skills']))")
check "3" "$COUNT" "3 default skills"

# T6: Rules
echo ""
echo "T6: GET /api/v1/rules"
COUNT=$(curl -s http://localhost:8000/api/v1/rules | python3 -c "import sys,json;d=json.loads(sys.stdin.read(),strict=False);print(len(d['rules']))")
check "3" "$COUNT" "3 default rules"

# T7: PII scan
echo ""
echo "T7: POST /api/v1/guardrails/scan"
R=$(curl -s -X POST http://localhost:8000/api/v1/guardrails/scan \
  -H "Content-Type: application/json" \
  -d '{"text":"Email: user@test.com, SSN: 123-45-6789"}')
HAS_PII=$(echo "$R" | python3 -c "import sys,json;print(json.loads(sys.stdin.read(),strict=False).get('has_pii',False))")
check "True" "$HAS_PII" "PII detected"
MATCHES=$(echo "$R" | python3 -c "import sys,json;print(len(json.loads(sys.stdin.read(),strict=False).get('matches',[])))")
check "2" "$MATCHES" "2 PII matches"

# T8: Tool call
echo ""
echo "T8: POST /api/v1/mcp/tools/call (list_dashboards)"
R=$(curl -s -X POST http://localhost:8000/api/v1/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{"server_name":"bifrost-grafana","tool_name":"list_dashboards","arguments":{}}')
OK=$(echo "$R" | python3 -c "import sys,json;print(json.loads(sys.stdin.read(),strict=False).get('ok',False))")
check "True" "$OK" "Tool call succeeded"

# T9: CORS
echo ""
echo "T9: CORS preflight"
CORS=$(curl -s -I -X OPTIONS http://localhost:8000/api/v1/chat \
  -H "Origin: http://localhost:3200" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" 2>&1 \
  | grep -i "access-control-allow-origin" | tr -d '\r' | cut -d' ' -f2)
check "http://localhost:3200" "$CORS" "CORS allows Grafana origin"

# T10: Grafana health
echo ""
echo "T10: GET :3200/api/health"
check "200" "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3200/api/health)" "Grafana healthy"

# T11: Widget JS served
echo ""
echo "T11: Widget JS served"
check "200" "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3200/public/plugins/gopal-ollychat-app/o11ybot-widget.js)" "Widget JS accessible"

# T12: Plugin enabled
echo ""
echo "T12: OllyChat plugin enabled"
ENABLED=$(curl -s http://admin:admin@localhost:3200/api/plugins/gopal-ollychat-app/settings | python3 -c "import sys,json;print(json.loads(sys.stdin.read(),strict=False).get('enabled'))")
check "True" "$ENABLED" "Plugin enabled"

# T13: Bifrost direct
echo ""
echo "T13: Bifrost MCP direct"
BIFROST=$(curl -s --max-time 3 http://localhost:8765/api/tools | python3 -c "import sys,json;d=json.loads(sys.stdin.read(),strict=False);tools=d.get('data',d);print(len(tools))" 2>/dev/null)
check "16" "$BIFROST" "Bifrost returns 16 tools"

# T14: Widget injection (authenticated)
echo ""
echo "T14: Widget injected in HTML"
rm -f /tmp/gcookies.txt
curl -s -c /tmp/gcookies.txt -X POST http://localhost:3200/login \
  -H "Content-Type: application/json" \
  -d '{"user":"admin","password":"admin"}' > /dev/null
COUNT=$(curl -s -b /tmp/gcookies.txt http://localhost:3200/ | grep -c "o11ybot-widget")
check "1" "$COUNT" "Widget script injected in HTML"

echo ""
echo "─────────────────────────"
echo "Suite 1 Results: $PASS passed, $FAIL failed"
echo "─────────────────────────"
[ "$FAIL" = "0" ] && exit 0 || exit 1
