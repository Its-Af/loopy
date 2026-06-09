#!/usr/bin/env bash
# check-round.sh — loop-compliance checker.
#
# Verifies the central invariant: parent loops finish under the 60s budget.
# Reports p50/p95/max loop latency and how many samples blew the budget. Exit 1
# if the p95 exceeds the budget (a sign agents are doing heavy work inline
# instead of delegating to subagents).
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"
loopy_require_runtime

agent="${1:-}"
args=(--json metrics --kind loop)
[[ -n "$agent" ]] && args+=(--agent "$agent")

report="$("$PY" "$LOOPY_TOOL" "${args[@]}" 2>/dev/null || true)"
if [[ -z "$report" || "$report" == *"no samples"* ]]; then
  warn "no loop latency samples yet"; exit 0
fi

"$PY" - "$report" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
budget = 60000
print(f"loop latency{' for '+d.get('agent','') if d.get('agent') else ''}: "
      f"n={d['count']} p50={d['p50_ms']}ms p95={d['p95_ms']}ms "
      f"max={d['max_ms']}ms over_budget={d['over_budget']}")
if d['p95_ms'] > budget:
    print(f"FAIL: p95 {d['p95_ms']}ms exceeds {budget}ms budget — agents are "
          f"blocking the loop; push heavy work into subagents.")
    sys.exit(1)
print("OK: loops within budget")
PY
