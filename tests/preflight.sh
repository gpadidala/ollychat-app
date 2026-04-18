#!/bin/bash
# Pre-flight: verify all required services are up before running tests

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

chk "Orchestrator (:8000)"    "curl -s --max-time 3 http://localhost:8000/api/v1/health | grep -q healthy"
chk "Grafana (:3200)"          "curl -s --max-time 3 -o /dev/null -w '%{http_code}' http://localhost:3200/api/health | grep -q 200"
chk "Bifrost MCP (:8765)"      "curl -s --max-time 3 http://localhost:8765/api/tools | grep -q list_dashboards"
chk "Ollama (:11434)"          "curl -s --max-time 3 http://localhost:11434/api/tags | grep -q models"
chk "OllyChat plugin enabled"  "curl -s http://admin:admin@localhost:3200/api/plugins/gopal-ollychat-app/settings | grep -q '\"enabled\":true'"
chk "MCP registered w/ orch."  "curl -s http://localhost:8000/api/v1/mcp/servers | grep -q 'connected'"
chk "Node.js installed"        "which node"
chk "Python3 installed"        "which python3"

echo ""
echo "Pre-flight: $ok/$((ok+fail)) OK"

if [ $fail -gt 0 ]; then
  echo ""
  echo "To fix:"
  echo "  cd /Volumes/Gopalmac/Gopal-aiops/ollychat-app"
  echo "  docker compose up -d                                # main stack"
  echo "  cd ../Bifrost && .venv/bin/grafana-mcp serve --port 8765 &  # MCP"
  echo "  cd ../Grafana-Dashbords && docker compose up -d     # main Grafana"
  echo ""
  echo "  # Re-register MCP with orchestrator:"
  echo '  curl -s -X POST http://localhost:8000/api/v1/mcp/servers \'
  echo '    -H "Content-Type: application/json" \'
  echo '    -d "{\"name\":\"bifrost-grafana\",\"url\":\"http://host.docker.internal:8765\",\"transport\":\"sse\",\"auth_method\":\"none\"}"'
  exit 1
fi
exit 0
