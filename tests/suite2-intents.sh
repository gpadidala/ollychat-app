#!/bin/bash
# Suite 2: Intent Matcher (19 tests)
# Run: ./suite2-intents.sh

PASS=0; FAIL=0

test_intent() {
  local NAME="$1"; local QUERY="$2"; local EXPECTED_TOOL="$3"
  local RESP=$(curl -s --max-time 15 -X POST http://localhost:8000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$QUERY\"}],\"stream\":true}" 2>&1)
  local TOOL=$(echo "$RESP" | grep '"type": "tool_start"' | head -1 | sed 's/.*"name": "\([^"]*\)".*/\1/')
  if [ "$TOOL" = "$EXPECTED_TOOL" ]; then
    echo "  PASS: $NAME → $TOOL"; PASS=$((PASS+1))
  else
    echo "  FAIL: $NAME → expected '$EXPECTED_TOOL', got '$TOOL'"; FAIL=$((FAIL+1))
  fi
}

echo "═══ SUITE 2: INTENT MATCHER ═══"
echo ""

test_intent "list all Grafana dashboards" "list all Grafana dashboards" "list_dashboards"
test_intent "show dashboards" "show dashboards" "list_dashboards"
test_intent "all dashboards" "all dashboards" "list_dashboards"
test_intent "list datasources" "list datasources" "list_datasources"
test_intent "show all data sources" "show all data sources" "list_datasources"
test_intent "check datasource health" "check datasource health" "list_datasources"
test_intent "list all alerts" "list all alerts" "list_alert_rules"
test_intent "show firing alerts" "show firing alerts" "list_alert_instances"
test_intent "active alerts" "active alerts" "list_alert_instances"
test_intent "alert instances" "alert instances" "list_alert_instances"
test_intent "list all folders" "list all folders" "list_folders"
test_intent "check grafana health" "check grafana health" "health_check"
test_intent "grafana status" "grafana status" "health_check"
test_intent "grafana version" "grafana version" "health_check"
test_intent "health check" "health check" "health_check"
test_intent "mcp server info" "mcp server info" "get_server_info"
test_intent "bifrost info" "bifrost info" "get_server_info"
test_intent "search dashboards aks" "search dashboards aks" "search_dashboards"
test_intent "list users" "list users" "list_users"

echo ""
echo "─────────────────────────"
echo "Suite 2 Results: $PASS passed, $FAIL failed"
echo "─────────────────────────"
[ "$FAIL" = "0" ] && exit 0 || exit 1
