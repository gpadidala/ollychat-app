#!/bin/bash
# Suite 7: Category-filtered dashboard queries (20+ tests)
# Run: ./suite7-categories.sh

PASS=0; FAIL=0

# Test category: query → expected tool + expected tag in args
test_category() {
  local NAME="$1"; local QUERY="$2"; local EXPECTED_TAG="$3"
  local RESP=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$QUERY\"}],\"stream\":true}" 2>&1)
  local TOOL=$(echo "$RESP" | grep '"type": "tool_start"' | head -1 | sed 's/.*"name": "\([^"]*\)".*/\1/')
  local ARGS=$(echo "$RESP" | grep '"type": "tool_start"' | head -1 | sed 's/.*"input": \({[^}]*}\).*/\1/')

  if [ "$TOOL" = "list_dashboards" ] && echo "$ARGS" | grep -q "$EXPECTED_TAG"; then
    echo "  PASS: $NAME → tag=$EXPECTED_TAG"
    PASS=$((PASS+1))
  else
    echo "  FAIL: $NAME → got tool=$TOOL args=$ARGS (expected tag=$EXPECTED_TAG)"
    FAIL=$((FAIL+1))
  fi
}

# Test service-specific search
test_service() {
  local NAME="$1"; local QUERY="$2"; local EXPECTED_QUERY="$3"
  local RESP=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$QUERY\"}],\"stream\":true}" 2>&1)
  local TOOL=$(echo "$RESP" | grep '"type": "tool_start"' | head -1 | sed 's/.*"name": "\([^"]*\)".*/\1/')
  local ARGS=$(echo "$RESP" | grep '"type": "tool_start"' | head -1 | sed 's/.*"input": \({[^}]*}\).*/\1/')

  if [ "$TOOL" = "search_dashboards" ] && echo "$ARGS" | grep -q "$EXPECTED_QUERY"; then
    echo "  PASS: $NAME → query=$EXPECTED_QUERY"
    PASS=$((PASS+1))
  else
    echo "  FAIL: $NAME → got tool=$TOOL args=$ARGS"
    FAIL=$((FAIL+1))
  fi
}

echo "═══ SUITE 7: CATEGORY INTENTS ═══"
echo ""

echo "── Cloud Providers ──"
test_category "AKS"   "list AKS dashboards"   "aks"
test_category "Azure" "show Azure dashboards" "azure"
test_category "OCI"   "list OCI dashboards"   "oci"
test_category "GCP"   "GCP dashboards"        "gcp"
test_category "AWS"   "AWS dashboards"        "aws"

echo ""
echo "── Kubernetes / Containers ──"
test_category "Kubernetes" "kubernetes dashboards" "kubernetes"

echo ""
echo "── Databases ──"
test_category "Database"   "database dashboards"   "database"
test_category "PostgreSQL" "postgres dashboards"   "postgresql"
test_category "Redis"      "redis dashboards"      "redis"

echo ""
echo "── Observability signals ──"
test_category "Loki"      "show loki dashboards"    "loki"
test_category "Mimir"     "mimir dashboards"        "mimir"
test_category "Tempo"     "tempo dashboards"        "tempo"
test_category "Pyroscope" "pyroscope dashboards"    "pyroscope"

echo ""
echo "── SRE patterns ──"
test_category "SLO"         "SLO dashboards"         "slo"
test_category "Performance" "performance dashboards" "performance"
test_category "Errors"      "error dashboards"       "errors"

echo ""
echo "── Compliance / Security ──"
test_category "Security" "security dashboards" "security"
test_category "PCI"      "PCI dashboards"      "pci"

echo ""
echo "── Levels ──"
test_category "L0 executive" "show executive dashboards" "executive"
test_category "L3 deep-dive" "L3 dashboards"             "l3"

echo ""
echo "── Cost / Capacity ──"
test_category "Cost"     "cost dashboards"     "cost"
test_category "Capacity" "capacity dashboards" "capacity"

echo ""
echo "── Network / Storage ──"
test_category "Network" "network dashboards" "network"
test_category "Storage" "storage dashboards" "storage"

echo ""
echo "── Service-specific ──"
test_service "payment-service" "payment-service dashboards"        "payment-service"
test_service "api-gateway"     "dashboards for api-gateway"        "api-gateway"
test_service "user-svc"        "dashboards for user-svc"           "user-svc"

echo ""
echo "── Regression: existing intents still work ──"
test_category_or_service() {
  local NAME="$1"; local QUERY="$2"; local EXPECTED_TOOL="$3"
  local TOOL=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
    -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$QUERY\"}],\"stream\":true}" 2>&1 \
    | grep '"type": "tool_start"' | head -1 | sed 's/.*"name": "\([^"]*\)".*/\1/')
  if [ "$TOOL" = "$EXPECTED_TOOL" ]; then
    echo "  PASS: $NAME → $TOOL"; PASS=$((PASS+1))
  else
    echo "  FAIL: $NAME → got '$TOOL', expected '$EXPECTED_TOOL'"; FAIL=$((FAIL+1))
  fi
}

test_category_or_service "list all dashboards (plain)" "list all dashboards"     "list_dashboards"
test_category_or_service "search dashboards aks"       "search dashboards aks"   "search_dashboards"
test_category_or_service "list datasources"            "list datasources"        "list_datasources"
test_category_or_service "grafana health"              "check grafana health"    "health_check"

echo ""
echo "─────────────────────────"
echo "Suite 7 Results: $PASS passed, $FAIL failed"
echo "─────────────────────────"
[ "$FAIL" = "0" ] && exit 0 || exit 1
