#!/bin/bash
# Pre-flight: verify all required services are up before running tests.
#
# The O11yBot stack is fully bundled — one docker-compose, one `make up`,
# no external Bifrost, no external Grafana. Ports:
#   3002  — Grafana (bundled)
#   8000  — orchestrator
#   8765  — O11yBot MCP server
#   11434 — Ollama
#

echo "Pre-flight checks:"

ok=0; fail=0
chk() {
  local name="$1"; local cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "  ✓ $name"; ok=$((ok+1))
  else
    echo "  ✗ $name — $cmd"; fail=$((fail+1))
  fi
}

chk "Orchestrator (:8000)"     "curl -s --max-time 3 http://localhost:8000/api/v1/models | grep -q models"
chk "Grafana (:3002)"          "curl -s --max-time 3 -o /dev/null -w '%{http_code}' http://localhost:3002/api/health | grep -q 200"
chk "O11yBot MCP (:8765)"      "curl -s --max-time 3 http://localhost:8765/api/tools | grep -q list_dashboards"
chk "Ollama (:11434)"          "curl -s --max-time 3 http://localhost:11434/api/tags | grep -q models"
chk "O11yBot plugin enabled"   "curl -s http://admin:admin@localhost:3002/api/plugins/gopal-ollychat-app/settings | grep -q '\"enabled\":true'"
chk "MCP registered w/ orch."  "curl -s http://localhost:8000/api/v1/mcp/servers | grep -q 'connected'"
chk "Node.js installed"        "which node"
chk "Python3 installed"        "which python3"

echo ""
echo "Pre-flight: $ok/$((ok+fail)) OK"

if [ $fail -gt 0 ]; then
  echo ""
  echo "To fix:"
  echo "  cd $(cd "$(dirname "$0")/.." && pwd)"
  echo "  make up                          # boots all 10 services + auto-registers MCP"
  echo
  echo "If plugin still shows disabled after boot:"
  echo "  curl -X POST http://admin:admin@localhost:3002/api/plugins/gopal-ollychat-app/settings \\"
  echo "    -H 'Content-Type: application/json' -d '{\"enabled\":true,\"pinned\":true}'"
  exit 1
fi
exit 0
