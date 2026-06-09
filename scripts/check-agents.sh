#!/usr/bin/env bash
# check-agents.sh — quick one-line-per-agent health check (scriptable).
#
# Exit 0 if all roster agents have a fresh heartbeat; exit 1 if any are stale or
# missing. Good for CI gates and cron alerts.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"
loopy_require_runtime

bad=0
while read -r agent; do
  [[ -z "$agent" ]] && continue
  line="$("$PY" - "$agent" "$LOOPY_FRAMEWORK_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[2])
from tools.state import read_state
s = read_state(sys.argv[1])
if s is None:
    print(f"{sys.argv[1]:<14} MISSING (no heartbeat)"); sys.exit(2)
flag = "STALE" if s.stale else "ok"
print(f"{s.agent:<14} {flag:<6} loop={s.loop} age={s.age:.0f}s :: {s.status}")
sys.exit(1 if s.stale else 0)
PY
)" || bad=1
  echo "$line"
done < <(loopy_roster)

if (( bad )); then warn "one or more agents unhealthy"; exit 1; fi
ok "all agents healthy"
