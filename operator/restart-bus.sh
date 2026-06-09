#!/usr/bin/env bash
# restart-bus.sh — cleanly restart the message bus broker.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

if [[ -f "$LOOPY_RUNTIME/bus.pid" ]]; then
  kill -TERM "$(cat "$LOOPY_RUNTIME/bus.pid")" 2>/dev/null || true
  rm -f "$LOOPY_RUNTIME/bus.pid"
  log "stopped old bus"
  sleep 0.5
fi
rm -f "$LOOPY_BUS_SOCK_PATH"
exec "$LOOPY_FRAMEWORK_DIR/daemons/start-bus.sh"
