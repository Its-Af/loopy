#!/usr/bin/env bash
# watchdog-headless.sh — background wrapper around daemons/watchdog.sh.
#
# Records a pidfile and runs the watchdog detached, restarting it if it ever
# exits unexpectedly (with a short delay to avoid a tight loop).
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

PIDFILE="$LOOPY_RUNTIME/watchdog-headless.pid"
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

log "headless watchdog supervisor up (pid $$)"
while true; do
  "$LOOPY_FRAMEWORK_DIR/daemons/watchdog.sh" || warn "watchdog exited ($?); restarting in 5s"
  sleep 5
done
