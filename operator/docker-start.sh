#!/usr/bin/env bash
# docker-start.sh — container entrypoint for one Loopy process.
#
# In Docker, each container runs a single role (no tmux). The role is taken from
# LOOPY_AGENT_ID. The special id "bus" runs the message broker; "watchdog" runs
# the watchdog; anything else runs that agent's loop.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

[[ -d "$LOOPY_RUNTIME" ]] || "$LOOPY_FRAMEWORK_DIR/operator/init.sh"
agent="${LOOPY_AGENT_ID:-}"
[[ -z "$agent" ]] && die "LOOPY_AGENT_ID must be set (role, 'bus', or 'watchdog')"

case "$agent" in
  bus)
    log "container role: message bus"
    exec "$PY" "$LOOPY_FRAMEWORK_DIR/daemons/bus_broker.py" ;;
  watchdog)
    log "container role: watchdog"
    exec "$LOOPY_FRAMEWORK_DIR/daemons/watchdog.sh" ;;
  *)
    role="${agent%%.*}"
    log "container role: agent $agent"
    "$PY" "$LOOPY_FRAMEWORK_DIR/scripts/scan-project.py" >/dev/null 2>&1 || true
    exec bash -lc "$(loopy_agent_cmd "$role")" ;;
esac
