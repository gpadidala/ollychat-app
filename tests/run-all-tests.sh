#!/bin/bash
# Run all 5 test suites and report combined results
# Run from anywhere: /path/to/ollychat-app/tests/run-all-tests.sh

set -e
cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       O11yBot — Full Test Suite                             ║"
echo "║       94 tests across 5 suites                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

./preflight.sh || { echo "Pre-flight checks failed. Start services first."; exit 1; }

echo ""
echo "Running test suites..."
echo ""

TOTAL_PASS=0; TOTAL_FAIL=0
FAILED_SUITES=()

run_suite() {
  local NUM=$1
  local NAME=$2
  local CMD=$3
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  SUITE $NUM: $NAME"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  if $CMD; then
    return 0
  else
    FAILED_SUITES+=("Suite $NUM")
    return 1
  fi
}

run_suite 1 "API Endpoints"        "./suite1-api.sh"      || true
run_suite 2 "Intent Matcher"       "./suite2-intents.sh"  || true
run_suite 3 "UI Widget / SSE"      "node suite3-widget.js" || true
run_suite 4 "Integration / E2E"    "node suite4-integration.js" || true
run_suite 5 "Negative / Errors"    "node suite5-negative.js" || true

echo ""
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
if [ ${#FAILED_SUITES[@]} -eq 0 ]; then
  echo "║   RESULT: ALL SUITES PASSED                                 ║"
else
  echo "║   RESULT: FAILED — ${FAILED_SUITES[*]}"
fi
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

[ ${#FAILED_SUITES[@]} -eq 0 ] && exit 0 || exit 1
