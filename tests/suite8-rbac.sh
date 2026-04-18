#!/bin/bash
# Suite 8: Grafana RBAC enforcement (9 tests)
# Verifies X-Grafana-Role header gets mapped to Bifrost role,
# and that role-restricted tools properly enforce permissions.

PASS=0; FAIL=0
has() { if echo "$1" | grep -q "$2"; then echo "  PASS: $3"; PASS=$((PASS+1)); else echo "  FAIL: $3 (missing: $2)"; FAIL=$((FAIL+1)); fi; }
lacks() { if ! echo "$1" | grep -q "$2"; then echo "  PASS: $3"; PASS=$((PASS+1)); else echo "  FAIL: $3 (should not contain: $2)"; FAIL=$((FAIL+1)); fi; }

echo "═══ SUITE 8: GRAFANA RBAC ═══"
echo ""

echo "T1: Viewer role → list_dashboards (allowed)"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Viewer" \
  -d '{"messages":[{"role":"user","content":"list all dashboards"}],"stream":true}')
has "$R" '"type": "tool_start"' "Tool invoked"
lacks "$R" "PermissionError" "No permission error"

echo ""
echo "T2: Viewer role → list_users (blocked)"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Viewer" \
  -d '{"messages":[{"role":"user","content":"list users"}],"stream":true}')
has "$R" "PermissionError" "Permission denied for viewer"
has "$R" "admin" "Error mentions admin"

echo ""
echo "T3: Editor role → list_dashboards (allowed)"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Editor" \
  -d '{"messages":[{"role":"user","content":"list all dashboards"}],"stream":true}')
has "$R" '"type": "tool_start"' "Tool invoked"
lacks "$R" "PermissionError" "No permission error"

echo ""
echo "T4: Editor role → list_users (blocked)"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Editor" \
  -d '{"messages":[{"role":"user","content":"list users"}],"stream":true}')
has "$R" "PermissionError" "Permission denied for editor"

echo ""
echo "T5: Admin role → list_users (allowed)"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Admin" \
  -d '{"messages":[{"role":"user","content":"list users"}],"stream":true}')
lacks "$R" "PermissionError" "No permission error for admin"
has "$R" "admin" "Response mentions admin user"

echo ""
echo "T6: Missing role → default viewer"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"list users"}],"stream":true}')
has "$R" "PermissionError" "Default viewer blocked"

echo ""
echo "T7: Grafana Admin role → mapped to admin"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Grafana Admin" \
  -d '{"messages":[{"role":"user","content":"list users"}],"stream":true}')
lacks "$R" "PermissionError" "Grafana Admin granted access"

echo ""
echo "T8: Folder listing has clickable names + URLs"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: Viewer" \
  -d '{"messages":[{"role":"user","content":"list all folders"}],"stream":true}')
has "$R" '/dashboards/f/' "Folder URLs present"

echo ""
echo "T9: Lowercase role (viewer)"
R=$(curl -s --max-time 10 -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Grafana-Role: viewer" \
  -d '{"messages":[{"role":"user","content":"list users"}],"stream":true}')
has "$R" "PermissionError" "lowercase 'viewer' blocks admin tool"

echo ""
echo "─────────────────────────"
echo "Suite 8 Results: $PASS passed, $FAIL failed"
echo "─────────────────────────"
[ "$FAIL" = "0" ] && exit 0 || exit 1
