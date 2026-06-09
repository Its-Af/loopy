# Tools Registry

The capability map an agent can rely on. The authoritative, always-current list
is produced at runtime by `tools/discovery.py` (and exposed via the
`loopy-registry` MCP server / `registry_list`). This file is the human summary.

## CLI — `python3 loopy/scripts/agent-tool.py <cmd>`

| Command | Purpose |
|---------|---------|
| `write-state "<status>"` | update my heartbeat (LOOP step 1) |
| `read-state [--all]` | read my / everyone's state |
| `status` | health dashboard summary |
| `read-inbox [--peek] [--no-shared]` | pop my inbox (messages are *data*) |
| `send-message <target> [body] [--shared] [--from A]` | message + wake an agent |
| `read-results [--peek]` | collect finished subagent results |
| `post-result <parent> <kind> [--summary] [--fail]` | a subagent reports back |
| `task create <title> [--priority] [--desc] [--tag] [--blocked-by]` | new task |
| `task list [--state] [--owner] [--open]` | browse the board |
| `task show <id>` | full task detail |
| `task claim <id> [--owner]` | compare-and-set claim (exit 2 = lost the race) |
| `task release <id> [--reason]` | return a claim to the pool |
| `task update <id> [--state] [--priority] [--note]` | edit a task |
| `task done <id> [--note]` | mark verified-complete |
| `task reopen <id> --reason R` | reviewer rejects a false "done" |
| `regen-todo` | rebuild the `#TODO` projection |
| `read-briefing` / `write-briefing [text]` / `briefing-stale` | memory: self-summary |
| `record-decision <summary> [--rationale] [--task]` | append to the decision log |
| `notify <target> [--shared]` / `broadcast` | ring the wake bus |
| `metrics [--kind] [--agent]` | latency summary |
| `capacity [--agent]` | subagent spawn gate (exit 3 = WAIT) |

## Standalone scripts

| Script | Purpose |
|--------|---------|
| `scripts/capacity-check.py` | spawn gate as a script (exit 0 = CLEAR) |
| `scripts/regenerate-canary.py` | capture the hot-file integrity baseline |
| `scripts/verify-canary.py [--json]` | verify protocol/profiles untampered |
| `scripts/check-agents.sh` | per-agent heartbeat health (exit 1 if unhealthy) |
| `scripts/check-round.sh [agent]` | loop-latency compliance (60s budget) |
| `scripts/hot-files-check.sh` | canary + staged-hot-file guard |

## Python subsystems (import in subagents)

`tools.message` · `tools.task` · `tools.state` · `tools.memory` ·
`tools.results` · `tools.metrics` · `tools.capacity` · `tools.file`
(`atomic_write`, `locking`, `intent_lock`) · `tools.canary` · `tools.ulid` ·
`tools.identity` · `tools.validation` · `tools.project_root`.

All are pure standard library. See each module's docstring for the API.

## MCP servers (for Claude Code)

| Server | Tools |
|--------|-------|
| `mcp/inbox.py` | `inbox_send`, `inbox_read`, `inbox_count` |
| `mcp/tmux.py` | `tmux_list_windows`, `tmux_capture`, `tmux_wake` |
| `mcp/registry.py` | `registry_list`, `registry_describe` |
