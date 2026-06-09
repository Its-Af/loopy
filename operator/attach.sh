#!/usr/bin/env bash
# attach.sh — attach your terminal to the running squad.
#   loopy/operator/attach.sh [agent-id]   # optionally jump to one agent's window
# Detach again with Ctrl-b d (your panes keep running).
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"
loopy_session_exists || die "no running session '$LOOPY_SESSION' (launch-all.sh first)"
if [[ -n "${1:-}" ]]; then
  "$LOOPY_TMUX" select-window -t "$(loopy_pane_target "$1")" 2>/dev/null \
    || warn "no window for $1; attaching to session"
fi
exec "$LOOPY_TMUX" attach -t "$LOOPY_SESSION"
