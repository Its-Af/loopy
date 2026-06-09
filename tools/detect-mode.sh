#!/usr/bin/env bash
# detect-mode.sh — print "dev" or "user".
#
#   dev  : you are developing Loopy itself (the framework has its own .git, or
#          the project root *is* the framework checkout). Tests + canary baseline
#          are expected to be regenerated freely.
#   user : Loopy is vendored into a host project (a git submodule or copy). The
#          framework is treated as read-only.
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # loopy/tools
FRAMEWORK_DIR="$(cd "$SELF_DIR/.." && pwd)"               # loopy/

if [[ -d "$FRAMEWORK_DIR/.git" ]] || [[ -f "$FRAMEWORK_DIR/.git" ]]; then
  echo dev          # framework has its own git -> developing Loopy
elif [[ "$(basename "$FRAMEWORK_DIR")" != "loopy" ]]; then
  echo dev          # not vendored under a loopy/ dir -> standalone dev checkout
else
  echo user         # loopy/ submodule inside a host project
fi
