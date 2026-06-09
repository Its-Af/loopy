#!/usr/bin/env bash
# hot-files-check.sh — guard the protocol + agent-profile "hot" files.
#
# Two checks:
#   1. Canary: do the hot files still match the trusted manifest?
#   2. Git (if available): are there *staged* edits to hot paths? Editing the
#      rules should be a deliberate, reviewed act — this flags accidental ones.
#
# Exit non-zero if either check trips. Used by the pre-commit hook and by
# execs/securities each round.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

rc=0

# 1. Canary.
if "$PY" "$LOOPY_FRAMEWORK_DIR/scripts/verify-canary.py"; then
  :
else
  rc=1
fi

# 2. Staged edits to hot paths.
if command -v git >/dev/null 2>&1 && git -C "$LOOPY_ROOT" rev-parse >/dev/null 2>&1; then
  staged="$(git -C "$LOOPY_ROOT" diff --cached --name-only 2>/dev/null \
            | grep -E '(^|/)loopy/(protocol|agents)/' || true)"
  if [[ -n "$staged" ]]; then
    warn "staged changes to hot files (intended? these define the rules):"
    echo "$staged" | sed 's/^/    /'
    rc=1
  fi
fi

(( rc == 0 )) && ok "hot files intact" || err "hot-files check failed"
exit $rc
