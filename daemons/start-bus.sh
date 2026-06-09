#!/usr/bin/env bash
# start-bus.sh — start the message-bus broker as a background daemon.
#
# Writes a pidfile so restart-bus.sh / stop-all.sh can find it. Idempotent:
# if a live broker is already running, does nothing.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

PIDFILE="$LOOPY_RUNTIME/bus.pid"
LOGFILE="$LOOPY_RUNTIME/logs/bus.log"
mkdir -p "$LOOPY_RUNTIME/logs"

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  log "bus already running (pid $(cat "$PIDFILE"))"
  exit 0
fi

log "starting message bus broker"
nohup "$PY" "$LOOPY_FRAMEWORK_DIR/daemons/bus_broker.py" >>"$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"

# Wait briefly for the socket to appear so callers can rely on it.
for _ in $(seq 1 50); do
  [[ -S "$LOOPY_BUS_SOCK_PATH" ]] && { ok "bus up (pid $(cat "$PIDFILE"))"; exit 0; }
  sleep 0.1
done
warn "bus started (pid $(cat "$PIDFILE")) but socket not yet visible; see $LOGFILE"
