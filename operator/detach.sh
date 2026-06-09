#!/usr/bin/env bash
# detach.sh — detach any client attached to the squad session (panes keep running).
# Normally you just press Ctrl-b d; this is for scripting / detaching remotely.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"
loopy_session_exists || die "no running session '$LOOPY_SESSION'"
"$LOOPY_TMUX" detach-client -s "$LOOPY_SESSION" 2>/dev/null || \
  "$LOOPY_TMUX" detach-client -t "$LOOPY_SESSION"
ok "detached all clients from '$LOOPY_SESSION'"
