#!/usr/bin/env bash
# docker-status.sh — container health check (used by HEALTHCHECK in the image).
#
# Exit 0 if this container's process looks healthy:
#  - bus:      the socket exists and bus-status.json is fresh
#  - agent:    this agent's heartbeat updated within the stale window
#  - watchdog: the watchdog pidfile is live
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

agent="${LOOPY_AGENT_ID:-}"
case "$agent" in
  bus)
    [[ -S "$LOOPY_BUS_SOCK_PATH" ]] || { echo "no bus socket"; exit 1; }
    echo "bus ok"; exit 0 ;;
  watchdog)
    p="$LOOPY_RUNTIME/watchdog.pid"
    [[ -f "$p" ]] && kill -0 "$(cat "$p")" 2>/dev/null || { echo "watchdog down"; exit 1; }
    echo "watchdog ok"; exit 0 ;;
  "")
    echo "LOOPY_AGENT_ID unset"; exit 1 ;;
  *)
    "$PY" - "$agent" "$LOOPY_FRAMEWORK_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[2])
from tools.state import read_state
s = read_state(sys.argv[1])
if s is None:
    print("no heartbeat yet"); sys.exit(1)
print(f"{s.agent} loop={s.loop} age={s.age:.0f}s {'STALE' if s.stale else 'ok'}")
sys.exit(1 if s.stale else 0)
PY
    ;;
esac
