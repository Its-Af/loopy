#!/usr/bin/env bash
# plist-gen.sh — print a macOS launchd plist that runs forever.sh at login.
#
#   loopy/operator/plist-gen.sh > ~/Library/LaunchAgents/com.loopy.squad.plist
#
# install-daemon.sh does this for you and loads it. Label is com.loopy.squad.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

LABEL="${LOOPY_DAEMON_LABEL:-com.loopy.squad}"
FOREVER="$LOOPY_FRAMEWORK_DIR/operator/forever.sh"

cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>            <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${FOREVER}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LOOPY_PROJECT_ROOT</key> <string>${LOOPY_ROOT}</string>
    </dict>
    <key>WorkingDirectory</key>  <string>${LOOPY_ROOT}</string>
    <key>RunAtLoad</key>         <true/>
    <key>KeepAlive</key>         <true/>
    <key>StandardOutPath</key>   <string>${LOOPY_RUNTIME}/logs/daemon.out.log</string>
    <key>StandardErrorPath</key> <string>${LOOPY_RUNTIME}/logs/daemon.err.log</string>
</dict>
</plist>
PLIST
