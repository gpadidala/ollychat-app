#!/usr/bin/env bash
# Zero-config SA-token bootstrap for the bundled Grafana.
#
# - Waits for the bundled Grafana to be healthy.
# - Creates three service accounts (viewer / editor / admin) if absent.
# - Writes the resulting tokens into .env so the MCP picks them up
#   on its next restart.
# - Idempotent: safe to run every `make up`.
set -euo pipefail

GRAFANA_URL="${GRAFANA_HOST_URL:-http://localhost:3002}"
ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
ADMIN_PASS="${GRAFANA_ADMIN_PASSWORD:-admin}"
ENV_FILE="${ENV_FILE:-.env}"

# Already bootstrapped? Skip.
if grep -qE '^GRAFANA_VIEWER_TOKEN=glsa_' "$ENV_FILE" 2>/dev/null &&
   grep -qE '^GRAFANA_EDITOR_TOKEN=glsa_' "$ENV_FILE" 2>/dev/null &&
   grep -qE '^GRAFANA_ADMIN_TOKEN=glsa_'  "$ENV_FILE" 2>/dev/null; then
  # Sanity: verify the viewer token is still valid against this Grafana
  TOK=$(grep -E '^GRAFANA_VIEWER_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2-)
  if curl -fsSL -H "Authorization: Bearer $TOK" "$GRAFANA_URL/api/user" >/dev/null 2>&1; then
    echo "  ✓ SA tokens already bootstrapped in $ENV_FILE"
    exit 0
  fi
  echo "  · existing tokens are stale; re-bootstrapping"
fi

# Wait for Grafana
printf "  · waiting for Grafana at %s" "$GRAFANA_URL"
for _ in $(seq 1 60); do
  if curl -fsSL -o /dev/null "$GRAFANA_URL/api/health"; then
    echo " — up"
    break
  fi
  printf "."
  sleep 2
done

mint_token() {
  local name="$1" role="$2"
  # Create or find the SA
  SA_ID=$(curl -fsSL -u "$ADMIN_USER:$ADMIN_PASS" \
    "$GRAFANA_URL/api/serviceaccounts/search?query=$name" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); a=d.get('serviceAccounts',[]); print(a[0]['id'] if a else '')")

  if [ -z "$SA_ID" ]; then
    SA_ID=$(curl -fsSL -X POST -u "$ADMIN_USER:$ADMIN_PASS" \
      -H 'Content-Type: application/json' \
      -d "{\"name\":\"$name\",\"role\":\"$role\"}" \
      "$GRAFANA_URL/api/serviceaccounts" \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  fi

  # Delete any existing tokens on this SA (so we get a fresh key) and mint one
  OLD=$(curl -fsSL -u "$ADMIN_USER:$ADMIN_PASS" \
        "$GRAFANA_URL/api/serviceaccounts/$SA_ID/tokens" \
        | python3 -c "import sys,json; [print(t['id']) for t in json.load(sys.stdin)]")
  for tid in $OLD; do
    curl -fsSL -X DELETE -u "$ADMIN_USER:$ADMIN_PASS" \
      "$GRAFANA_URL/api/serviceaccounts/$SA_ID/tokens/$tid" >/dev/null
  done

  curl -fsSL -X POST -u "$ADMIN_USER:$ADMIN_PASS" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"${name}-token\"}" \
    "$GRAFANA_URL/api/serviceaccounts/$SA_ID/tokens" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])"
}

echo "  · minting SA tokens"
VIEWER=$(mint_token o11ybot-viewer Viewer)
EDITOR=$(mint_token o11ybot-editor Editor)
ADMIN=$(mint_token  o11ybot-admin  Admin)

# Patch .env
python3 - <<PY
from pathlib import Path
p = Path("$ENV_FILE")
lines = p.read_text().splitlines() if p.exists() else []
want = {
    "GRAFANA_VIEWER_TOKEN": "$VIEWER",
    "GRAFANA_EDITOR_TOKEN": "$EDITOR",
    "GRAFANA_ADMIN_TOKEN":  "$ADMIN",
}
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in want:
        out.append(f"{key}={want[key]}")
        seen.add(key)
    else:
        out.append(line)
for k, v in want.items():
    if k not in seen:
        out.append(f"{k}={v}")
p.write_text("\n".join(out) + "\n")
print("  ✓ Wrote viewer / editor / admin tokens to", p)
PY

echo "  · restarting MCP so it picks up the new tokens"
docker compose up -d --force-recreate ollychat-mcp >/dev/null 2>&1 || true
echo "  ✓ bootstrap complete"
