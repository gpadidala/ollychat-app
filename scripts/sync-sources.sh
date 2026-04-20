#!/usr/bin/env bash
# Sync the bundled O11yBot copies with your canonical source repos.
#
# Layout expected (sibling folders of ollychat-app):
#   ../Grafana-Dashbords/   ← dashboards master
#   ../Bifrost/             ← MCP server master (optional)
#
# Override either path with env vars:
#   DASHBOARDS_SRC=/path/to/Grafana-Dashbords
#   BIFROST_SRC=/path/to/Bifrost
#
# Safe to run on every `make up` — skips sources that don't exist.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARDS_SRC="${DASHBOARDS_SRC:-$HERE/../Grafana-Dashbords}"
BIFROST_SRC="${BIFROST_SRC:-$HERE/../Bifrost}"

DASHBOARDS_DST="$HERE/dashboards"
PROVISIONING_DST="$HERE/provisioning"

changed=0

# ── Dashboards ──────────────────────────────────────────────
if [ -d "$DASHBOARDS_SRC" ]; then
  echo "  · syncing dashboards   $DASHBOARDS_SRC → $DASHBOARDS_DST"
  mkdir -p "$DASHBOARDS_DST"
  for folder in L0-executive L1-domain L2-service L3-deepdive azure grafana loki mimir observability-kpi oci platform pyroscope tempo volume; do
    if [ -d "$DASHBOARDS_SRC/$folder" ]; then
      mkdir -p "$DASHBOARDS_DST/$folder"
      cp -u "$DASHBOARDS_SRC/$folder/"*.json "$DASHBOARDS_DST/$folder/" 2>/dev/null || true
    fi
  done
  cp -u "$DASHBOARDS_SRC/"*.json "$DASHBOARDS_DST/" 2>/dev/null || true
  # Provisioning: datasources + dashboard providers + prometheus stub
  if [ -d "$DASHBOARDS_SRC/provisioning" ]; then
    mkdir -p "$PROVISIONING_DST/dashboards" "$PROVISIONING_DST/datasources"
    cp -u "$DASHBOARDS_SRC/provisioning/dashboards/"*.y*ml "$PROVISIONING_DST/dashboards/" 2>/dev/null || true
    cp -u "$DASHBOARDS_SRC/provisioning/datasources/"*.y*ml "$PROVISIONING_DST/datasources/" 2>/dev/null || true
    cp -u "$DASHBOARDS_SRC/provisioning/prometheus.yml"      "$PROVISIONING_DST/" 2>/dev/null || true
  fi
  echo "    $(find "$DASHBOARDS_DST" -name '*.json' | wc -l | tr -d ' ') dashboards now bundled"
  changed=1
else
  echo "  · (skip dashboards)     $DASHBOARDS_SRC not present"
fi

# ── Bifrost MCP tools ──────────────────────────────────────
# We don't wholesale replace the bundled mcp-server — ollychat-app's
# version has extras (create_smart_dashboard, workflows, wizards,
# self-observability).  Sync only the primitive tools that match
# upstream so Bifrost stays the canonical source for read paths.
BIFROST_TOOLS="$BIFROST_SRC/packages/core/src/grafana_mcp/tools"
if [ -d "$BIFROST_TOOLS" ]; then
  echo "  · syncing Bifrost primitives"
  # Map: upstream file → bundled file.  Only the read-heavy primitives.
  # Skip files that exist only in ollychat-app (workflows.py, plugins.py, etc.).
  for f in alerts.py folders.py users.py utility.py datasources.py; do
    if [ -f "$BIFROST_TOOLS/$f" ] && [ -f "$HERE/mcp-server/tools/$f" ]; then
      # Only log which Bifrost tool fns changed vs bundled — we don't overwrite
      # because the two trees have diverged intentionally.  This is advisory.
      bifrost_fns=$(grep -c "^async def " "$BIFROST_TOOLS/$f" || echo 0)
      bundled_fns=$(grep -c "^async def " "$HERE/mcp-server/tools/$f" || echo 0)
      echo "    $f: bifrost=$bifrost_fns fns · bundled=$bundled_fns fns"
    fi
  done
  changed=1
else
  echo "  · (skip Bifrost)        $BIFROST_SRC not present"
fi

if [ "$changed" = "0" ]; then
  echo "  · nothing to sync — both source repos absent, using bundled copies as-is"
  exit 0
fi

echo "  ✓ sync complete"
