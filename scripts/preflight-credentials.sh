#!/usr/bin/env bash
# preflight-credentials.sh — make sure Anthropic credentials are present and
# working before the squad launches. Run automatically by `loopy start`, and
# on demand via `loopy login`.
#
# Behaviour:
#   - loads any stored creds (.loopy/keys.env / .env) without echoing them;
#   - if present, live-verifies them (free GET /v1/models);
#   - if absent and a terminal is attached, prompts for an API key and stores
#     it (chmod 600, .gitignore-protected) for next time;
#   - if you use `claude login` (subscription) instead of an API key, just press
#     Enter at the prompt — that's detected and allowed.
#
# Never blocks the launch hard (exit 0) — but warns clearly when agents would
# fail, so you get a useful message instead of nine silently-broken panes.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"
export LOOPY_PROJECT_ROOT="$LOOPY_ROOT"     # so load-keys resolves the same root

RESET=0; [[ "${1:-}" == "--reset" ]] && RESET=1
KEYS="$LOOPY_RUNTIME/keys.env"

# shellcheck disable=SC1090
source "$LOOPY_FRAMEWORK_DIR/tools/load-keys.sh" >/dev/null 2>&1 || true

have_creds() { [[ -n "${ANTHROPIC_API_KEY:-}${ANTHROPIC_AUTH_TOKEN:-}" ]]; }
verify() { "$PY" "$LOOPY_FRAMEWORK_DIR/scripts/verify-credentials.py" >/dev/null 2>&1; }

store_key() {  # $1 = api key
  mkdir -p "$LOOPY_RUNTIME"
  loopy_ensure_gitignore
  ( umask 077
    if [[ -f "$KEYS" ]]; then grep -v '^ANTHROPIC_API_KEY=' "$KEYS" 2>/dev/null > "$KEYS.tmp" || true; mv -f "$KEYS.tmp" "$KEYS"; fi
    printf 'ANTHROPIC_API_KEY=%s\n' "$1" >> "$KEYS" )
  chmod 600 "$KEYS" 2>/dev/null || true
  export ANTHROPIC_API_KEY="$1"
}

prompt_key() {       # returns 0 if a key was entered+stored, 1 otherwise
  [[ -t 0 ]] || return 1
  echo
  echo "Loopy needs Anthropic credentials to run the agents:"
  echo "  • Already ran 'claude login' (Claude subscription)? Just press Enter."
  echo "  • Otherwise paste an API key — https://console.anthropic.com/settings/keys"
  local key=""
  read -r -s -p "  Anthropic API key (sk-ant-…), or Enter to skip: " key || true
  echo
  [[ -z "$key" ]] && { warn "no key entered — assuming 'claude login' subscription auth."; return 1; }
  case "$key" in sk-ant-*) ;; *) warn "that doesn't look like an sk-ant- key — storing it anyway." ;; esac
  store_key "$key"
  ok "saved to $KEYS (chmod 600, git-ignored)."
  return 0
}

[[ "$RESET" == 1 ]] && prompt_key || true

if have_creds; then
  if verify; then ok "Anthropic credentials verified."; exit 0; fi
  rc_msg="$("$PY" "$LOOPY_FRAMEWORK_DIR/scripts/verify-credentials.py" 2>&1 || true)"
  if grep -qi "reject" <<<"$rc_msg"; then
    warn "stored credentials were REJECTED by the API."
    if prompt_key && verify; then ok "credentials verified."; exit 0; fi
    warn "continuing — agents will fail until credentials are valid ('loopy login')."
  else
    ok "credentials present (couldn't live-verify — offline or non-API auth). Proceeding."
  fi
  exit 0
fi

# No credentials at all.
if prompt_key; then
  verify && ok "credentials verified." || warn "saved, but couldn't verify right now."
  exit 0
fi
if [[ -d "$HOME/.claude" || -f "$HOME/.claude.json" ]]; then
  ok "no API key set, but a 'claude login' session looks present. Proceeding."
else
  warn "no Anthropic credentials found — agents will not be able to start."
  warn "Fix it with:  loopy/bin/loopy login   (or set ANTHROPIC_API_KEY, or 'claude login')"
fi
exit 0
