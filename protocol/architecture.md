# Architecture

Loopy coordinates N autonomous Claude Code instances through **shared files**
and a **wake bus**. There is no central scheduler and no shared database — just
a directory on disk that every agent can read and write under strict rules.

## The parent-as-coordinator pattern

Each agent runs an endless loop (`/loop 5m`). The process running that loop is
the **parent**. The parent's job is to *decide and delegate*, never to do heavy
work itself, because:

- A parent that blocks for minutes can't read its inbox, update its heartbeat,
  or react to a teammate. The squad appears dead.
- The watchdog treats a silent agent as crashed and may respawn it.

So the parent keeps every loop under 60 seconds (see `RULES.md`) and pushes
anything slow to a **background subagent**:

```
parent loop (≤60s):  claim task ──▶ spawn subagent ──▶ write state ──▶ return
                                         │
background subagent (minutes):  build / test / implement / review
                                         │
                                         ▼
                              .loopy/results/<parent>/<ulid>.json
parent loop (later):  read-results ──▶ act on the outcome
```

The subagent's only contract is: when finished, drop a result file in the
parent's results directory (`tools/results`). The parent collects it on a
subsequent loop. This decouples *thinking fast* from *working slowly*.

## Two communication channels

1. **Durable: the inbox.** `send-message` writes an atomic, sanitised file into
   the recipient's inbox. This is the source of truth — it survives crashes and
   is processed on the next loop even if nothing else works.
2. **Instant: the wake bus.** After delivering a message, the sender rings a
   doorbell over a Unix-domain socket (`daemons/bus_broker.py`). The broker
   nudges the recipient's tmux pane so it loops *now* instead of in five
   minutes. The bus is a pure latency optimisation — **if it is down, nothing
   breaks**, messages just wait for the next tick.

This "durable channel + best-effort notification" split is the key resilience
idea: correctness lives entirely in the filesystem; the socket only makes
things faster.

## Why files

- **Crash-proof.** State lives on disk, not in a process. Kill any agent and
  restart it; it reads its files and continues.
- **Inspectable.** A human can `cat` any inbox, task, or state file to see
  exactly what the squad believes.
- **Atomic.** Every write is temp-file-plus-rename; every delivery and claim is
  `O_CREAT|O_EXCL` or `flock`-guarded. Concurrent agents never corrupt shared
  state or double-claim a task (proven under a 12-process race test).
- **Submodule-friendly.** The framework (`loopy/`) is read-only code; all
  mutable state is a sibling `.loopy/`, so Loopy drops into any repo as a git
  submodule without polluting it.

## The roster

Seven roles, fixed by the framework: `execs` (project manager), `alfred`
(butler / human interface), `producers` (×3 coders), `qas` (tests), `critics`
(review), `securities` (attacker), `users` (impatient UAT). Instance counts are
configurable in `.loopy/config.md`, but the role *set* is stable because the
bus wire protocol assigns each role a fixed index.

See `structure.md` for the on-disk layout and `agent-loop.md` for loop
mechanics.
