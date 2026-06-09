#!/usr/bin/env bash
# roster.sh — print the configured squad as a flat list of agent ids.
#
# Reads `.loopy/config.md` "Roster" lines (`- <role>: <count>`) and expands
# them: a count of 1 emits the bare role (`execs`), a count >1 emits
# `<role>.1 .. <role>.N` (`producers.1`, `producers.2`, ...), a count of 0
# emits nothing. With no config file, falls back to the framework default.
#
# Output: one agent id per line, in roster order.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"      # loopy/tools
FRAMEWORK_DIR="$(cd "$SELF_DIR/.." && pwd)"                    # loopy/

# Locate the project root / config without sourcing common.sh (avoid cycles).
root="${LOOPY_PROJECT_ROOT:-}"
if [[ -z "$root" ]]; then
  d="$FRAMEWORK_DIR"
  while [[ "$d" != "/" ]]; do
    [[ -d "$d/.loopy" || -d "$d/.git" ]] && { root="$d"; break; }
    d="$(dirname "$d")"
  done
  [[ -z "$root" ]] && root="$(dirname "$FRAMEWORK_DIR")"
fi
config="$root/.loopy/config.md"

# Valid roles, in stable order (must match tools/validation/constants.py).
# NOTE: macOS ships bash 3.2, which has no associative arrays — so the roster
# and its defaults are kept as a plain list + case function, not `declare -A`.
ROLES="execs alfred producers qas critics securities users"

default_count() {
  case "$1" in
    producers) echo 3 ;;
    execs|alfred|qas|critics|securities|users) echo 1 ;;
    *) echo 0 ;;
  esac
}

# Pull a count for a role from config (first matching "- role: N" line).
count_for() {
  role="$1"; n=""
  if [[ -f "$config" ]]; then
    n="$(grep -iE "^[[:space:]]*-[[:space:]]*${role}[[:space:]]*:[[:space:]]*[0-9]+" "$config" \
         | head -1 | grep -oE '[0-9]+' | head -1 || true)"
  fi
  [[ -z "$n" ]] && n="$(default_count "$role")"
  echo "$n"
}

for role in $ROLES; do
  n="$(count_for "$role")"
  (( n <= 0 )) && continue
  if (( n == 1 )); then
    echo "$role"
  else
    for i in $(seq 1 "$n"); do echo "${role}.${i}"; done
  fi
done
