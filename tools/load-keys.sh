# load-keys.sh — safely load API keys into the environment.
#
#   source loopy/tools/load-keys.sh
#
# POSIX-sh compatible so it works whether sourced from bash (operator scripts)
# or zsh (your interactive shell). Reads, in order of precedence: the existing
# environment, then .loopy/keys.env, then the project .env. Values are exported
# but NEVER echoed or logged. Only an allow-list of key names is honoured, so a
# stray .env can't inject arbitrary variables into agents.
#
# Recognised keys: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL,
# OPENAI_API_KEY, SLACK_BOT_TOKEN, SLACK_APP_TOKEN.

_LOOPY_KEY_ALLOW="ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL OPENAI_API_KEY SLACK_BOT_TOKEN SLACK_APP_TOKEN"

_loopy_find_root() {
  if [ -n "${LOOPY_PROJECT_ROOT:-}" ]; then printf '%s\n' "$LOOPY_PROJECT_ROOT"; return; fi
  _d="$PWD"
  while [ "$_d" != "/" ]; do
    if [ -d "$_d/.loopy" ] || [ -d "$_d/.git" ]; then printf '%s\n' "$_d"; return; fi
    _d="$(dirname "$_d")"
  done
  printf '%s\n' "$PWD"
}

_loopy_load_file() {
  _file="$1"
  [ -f "$_file" ] || return 0
  while IFS= read -r _line || [ -n "$_line" ]; do
    case "$_line" in \#*|'') continue ;; esac
    _line="${_line#export }"
    case "$_line" in *=*) ;; *) continue ;; esac
    _key="${_line%%=*}"
    _key="$(printf '%s' "$_key" | tr -d '[:space:]')"
    case " $_LOOPY_KEY_ALLOW " in *" $_key "*) ;; *) continue ;; esac
    # Don't override a value already present in the real environment.
    eval "_cur=\${$_key:-}"
    [ -n "$_cur" ] && continue
    _val="${_line#*=}"
    _val="${_val%\"}"; _val="${_val#\"}"; _val="${_val%\'}"; _val="${_val#\'}"
    export "$_key=$_val"
  done < "$_file"
}

_loopy_root="$(_loopy_find_root)"
_loopy_load_file "$_loopy_root/.loopy/keys.env"
_loopy_load_file "$_loopy_root/.env"

# Report which credentials are present — without revealing their values.
if [ -n "${ANTHROPIC_API_KEY:-}${ANTHROPIC_AUTH_TOKEN:-}" ]; then
  echo "loopy: Anthropic credentials loaded"
else
  echo "loopy: WARNING — no Anthropic credentials found (set ANTHROPIC_API_KEY)" >&2
fi
unset _loopy_root _d _file _line _key _val _cur _LOOPY_KEY_ALLOW 2>/dev/null || true
