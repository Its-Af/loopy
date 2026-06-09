# Failure Modes & Recovery

Loopy assumes things break. Every recovery path leans on the same fact: **state
lives in files**, so any process can die and be restarted without losing the
squad's ground truth.

## An agent crashes mid-loop

- Its last `write-state` heartbeat stops advancing. After ~18 minutes it is
  **stale**.
- The **watchdog** (`daemons/watchdog.sh`) notices the dead tmux pane (or stale
  heartbeat) and respawns it. On startup the agent reads its briefing, inbox,
  and state and resumes.
- Any task it had **claimed** is now owned by a dead agent. `execs` detects
  stale owners and **releases or reassigns** their tasks back to `OPEN` so
  another producer can pick them up.

## A subagent never returns

- The parent sees no result file. It does not block — heavy work is fire-and-
  collect. After a reasonable number of loops with the task still `IN_PROGRESS`
  and no result, the parent releases the task and tries again (possibly with a
  smaller brief).
- Orphaned subagents are bounded by the capacity gate, so a few stuck ones
  can't snowball.

## The message bus dies

- **Nothing breaks.** The bus is best-effort. Without it, wakes are lost and
  agents simply process inboxes on their normal 5-minute tick instead of
  instantly.
- `operator/restart-bus.sh` (or `daemons/start-bus.sh`) brings it back; it
  regenerates tokens and recreates the socket. Agents reconnect lazily on their
  next `send-message`.

## Crash-loop protection

- The watchdog caps respawns per window and backs off exponentially. An agent
  that dies immediately on startup won't be hammered into a fork bomb — it is
  respawned slowly and flagged for the human via `alfred`.

## Corruption & tampering

- All writes are atomic (temp + rename) and all shared mutations are locked, so
  a crash mid-write leaves the old file intact, never a torn one.
- A malformed task/state/result file is skipped by readers rather than crashing
  them (defensive parsing throughout).
- The **canary** (`scripts/verify-canary.py` against `.loopy/canary.json`)
  detects unauthorised edits to protocol/profile hot files between rounds. A
  failed canary means someone — possibly an injected instruction — changed the
  rules; `execs`/`securities` halt and surface it.

## Quarantine

- Messages that trip injection screening land in `.loopy/quarantine/<agent>/`
  and are **never** delivered. `securities` reviews quarantine to understand
  attacks; no other agent should act on quarantined content.

## Full reset

When all else fails, the squad has no hidden state to untangle:

```bash
loopy/operator/stop-all.sh        # kill every pane + the bus
rm -rf .loopy                      # discard ALL runtime state
loopy/operator/init.sh             # recreate a clean .loopy/
loopy/operator/launch-all.sh       # start fresh
```

The framework checkout (`loopy/`) and your project code are untouched; only the
ephemeral coordination state is rebuilt.

## Recovery checklist for the human

1. `loopy/operator/status.sh` — who's alive, who's stale, bus health.
2. Stale agents? The watchdog should respawn; if not, `operator/start.sh <role>`.
3. Bus down? `operator/restart-bus.sh`.
4. Tasks stuck on dead owners? `execs` reassigns; or release manually with
   `agent-tool.py task release <id>`.
5. Canary failed? Stop, inspect `git diff` on `loopy/protocol/`, investigate.
