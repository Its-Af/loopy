# Changelog

All notable changes to Loopy are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow
[SemVer](https://semver.org/).

## [0.1.0] — 2026-06-08

Initial release. A complete, tested coordination core plus the full operator,
documentation, and deployment surface.

### Added — coordination core (stdlib only, 123 passing tests)
- **Identity & roots** — `LOOPY_AGENT_ID` parsing, project-root / `.loopy/`
  discovery with env override.
- **ULIDs** — time-sortable ids with a strictly-monotonic variant.
- **Validation** — roster, agent-id, ULID, status, and slug validators.
- **File primitives** — atomic write (temp + rename + fsync), `O_EXCL` create,
  `fcntl.flock` advisory locks, and TTL'd intent locks for source-file edits.
- **Inbox** — atomic delivery, prompt-injection screening (incl. Cyrillic/Greek
  homoglyph folding and zero-width stripping), quarantine, per-sender rate
  limiting, 2 KB cap, untrusted-data fencing, and shared-inbox fan-out with
  per-instance seen-sets.
- **Tasks** — JSON task store with a race-free `flock` compare-and-set claim
  (verified under a 12-process race), dependency gating, reopen, and a
  regenerated `#TODO` projection.
- **State, memory, results, metrics** — heartbeats with staleness, briefings +
  rotated decision log, the subagent result channel, and loop-latency tracking
  against the 60 s budget.
- **Capacity gate** — process/in-flight/load spawn gate to prevent host
  overload.

### Added — surfaces
- **CLI** — `agent-tool.py` with ~17 commands (human + `--json` output) and
  meaningful exit codes; `capacity-check.py`.
- **Message bus** — asyncio Unix-socket broker: per-role token auth,
  unicast/multicast/broadcast wire protocol, 5 s per-pane debounce, 10 frame/s
  rate limit, tmux `send-keys` dispatch with a wake-marker fallback,
  `bus-status.json`, and graceful shutdown.
- **MCP servers** — self-contained stdio JSON-RPC servers (`inbox`, `tmux`,
  `registry`) with no SDK dependency.
- **Skills** — `/wake` (instant loop trigger) and `/wizard` (TDD methodology).
- **Canary** — hot-file integrity manifest + verifier; git pre-commit hook.

### Added — operations & docs
- **Operator scripts** — init, launch-all/headless, start, stop-all, status,
  attach/detach, chat, restart-bus, forever, launchd install + plist, VS Code
  setup, Docker start/status. All bash-3.2 compatible (macOS default).
- **Daemons** — bus startup wrapper, watchdog with exponential-backoff respawn,
  YOLO auto-approver, shared `common.sh`.
- **Docs** — README, SYSTEM (plain English), full `protocol/` (RULES, SOUL,
  architecture, agent-loop, structure, sandbox, memory, parallelism, recovery),
  seven agent profiles + template, SETTINGS, DEPLOYMENT, CONTRIBUTING.
- **Deployment** — Dockerfile, docker-compose (default roster) + generator,
  reference `.claude/settings.json`, sample `config.md`.

### Notes
- Loopy requires no third-party runtime packages; pytest is the only dev
  dependency.
- The optional Slack bridge (`daemons/slack_*.py`, `token_refresh.py`) is
  included as a starting point and is inert unless configured with tokens.
