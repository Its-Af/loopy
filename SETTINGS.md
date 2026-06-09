# Settings

Two layers of configuration, doing different jobs.

## 1. `.loopy/config.md` — what the squad *is*

Seeded from [`config.sample.md`](../config.sample.md) by `init.sh`. Plain
markdown; only the `Roster` and `Settings` lines are parsed.

- **Roster** — `- <role>: <count>` sets how many of each role to launch. Change
  counts, not role names. `0` disables a role. `tools/roster.sh` reads this.
- **Settings** — `key: value` knobs read by the operator scripts:

  | Key | Default | Meaning |
  |-----|---------|---------|
  | `session` | `loopy` | tmux session name |
  | `loop_interval` | `5m` | how often each parent loop fires |
  | `max_claude_procs` | `12` | capacity gate: max concurrent claude processes |
  | `max_inflight` | `2` | capacity gate: max pending subagent results per agent |
  | `max_load_per_cpu` | `2.5` | capacity gate: 1-min load ceiling per CPU |
  | `wake_keys` | `Enter` | tmux send-keys sequence used to wake a pane |
  | `auto_approve` | `off` | `on` enables the YOLO auto-approver (sandbox only!) |

- **Project goal** — free text the squad reads at startup to know what to build.

## 2. `.claude/settings.json` — what the squad is *allowed to do*

Seeded from [`settings.reference.json`](settings.reference.json). This is the
**hard** permission boundary the Claude Code harness enforces, complementing the
soft conventions in [`protocol/sandbox.md`](protocol/sandbox.md). When the two
disagree, the stricter wins.

### `permissions.allow`
Operations agents may run without asking. The reference pre-allows the Loopy CLI,
the read-only health scripts, and common safe git/inspection commands. **Widen
deliberately** — every entry is power you're granting an autonomous agent.

### `permissions.deny`
Hard blocks. The reference denies reading secrets (`.env`, keys, `*.pem`,
`id_rsa*`), destructive `rm -rf /`, force-push, and raw network fetches. Keep
these; add your project's own sensitive paths.

### `permissions.ask`
Operations that prompt for confirmation: commits, pushes, `rm`. In a fully
autonomous run with no human present these will block — either move them to
`allow` (knowing the risk) or run with the auto-approver in a disposable sandbox.

### `env`
Environment variables injected into every agent. The reference sets the capacity
-gate ceilings; override per host.

## Environment variables (advanced)

These override config at runtime, useful for containers and tests:

| Var | Effect |
|-----|--------|
| `LOOPY_PROJECT_ROOT` | force the project root (else auto-detected) |
| `LOOPY_AGENT_ID` | the identity of the current agent (set by launchers) |
| `LOOPY_BUS_SOCK` | bus socket path — set a short path if your project path is deep (macOS caps AF_UNIX at ~104 chars) |
| `LOOPY_SESSION` | tmux session name |
| `LOOPY_AGENT_CMD` | override the command used to launch an agent |
| `LOOPY_MAX_CLAUDE_PROCS`, `LOOPY_MAX_INFLIGHT`, `LOOPY_MAX_LOAD_PER_CPU` | capacity-gate ceilings |
| `LOOPY_WAKE_KEYS` | keystrokes the bus sends to wake a pane |
| `LOOPY_PYTHON` | python interpreter to use |

## Credentials

Never put keys in `config.md` or `settings.json`. Put them in `.loopy/keys.env`
(git-ignored) and `source loopy/tools/load-keys.sh`, which loads only an
allow-list of known key names and never echoes their values.
