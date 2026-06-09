#!/usr/bin/env bash
# install-daemon.sh — install + load the launchd agent (macOS) for 24/7 mode.
#
# Generates the plist via plist-gen.sh, writes it to ~/Library/LaunchAgents,
# and loads it. Use `--uninstall` to unload + remove. Linux users: adapt
# forever.sh into a systemd unit instead (see DEPLOYMENT.md).
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

[[ "$(uname)" == "Darwin" ]] || die "install-daemon.sh is macOS-only; see DEPLOYMENT.md for Linux/systemd"

LABEL="${LOOPY_DAEMON_LABEL:-com.loopy.squad}"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [[ "${1:-}" == "--uninstall" ]]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  ok "uninstalled $LABEL"
  exit 0
fi

mkdir -p "$(dirname "$PLIST")"
"$LOOPY_FRAMEWORK_DIR/operator/plist-gen.sh" > "$PLIST"
ok "wrote $PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
ok "loaded $LABEL — the squad will now start at login and stay up."
log "logs: $LOOPY_RUNTIME/logs/daemon.{out,err}.log"
log "uninstall: $0 --uninstall"
