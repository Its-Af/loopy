# Loopy Protocol — Index & Reading Order

This directory is the constitution of the squad. Read it in this order.

## Read once, at startup
1. **[SOUL.md](SOUL.md)** — who we are and the values behind the rules.
2. **[architecture.md](architecture.md)** — the parent-as-coordinator pattern,
   the file + bus channels, why it's built this way.
3. **[structure.md](structure.md)** — the `.loopy/` layout and every file
   format you'll read or write.
4. **[agent-loop.md](agent-loop.md)** — the loop skeleton every role shares.
5. **[memory.md](memory.md)** — briefings, decisions, staying yourself across
   restarts.
6. **[sandbox.md](sandbox.md)** — what you may and may not touch.
7. **[parallelism.md](parallelism.md)** — the spawn gate and anti-crash rules.
8. **[recovery.md](recovery.md)** — failure modes and how the squad heals.

## Read EVERY round
- **[RULES.md](RULES.md)** — the short, binding rules. Kept under ~120 lines so
  re-reading it each loop is cheap. **If anything conflicts, RULES.md wins.**

## How profiles reference these

Each `loopy/agents/<role>.md` profile declares which docs it loads, via HTML
comments at the top:

```
<!-- ROUND_READS    = loopy/protocol/RULES.md -->
<!-- SUBAGENT_READS = loopy/protocol/RULES.md, loopy/protocol/sandbox.md, loopy/protocol/structure.md -->
<!-- STARTUP_READS  = loopy/protocol/SOUL.md, loopy/protocol/architecture.md, ... -->
```

- `ROUND_READS` — re-read at the top of every loop (always includes RULES.md).
- `STARTUP_READS` — read once when the pane boots.
- `SUBAGENT_READS` — handed to background subagents so they inherit the rules,
  the sandbox, and the file formats without the full startup cost.

## Precedence

1. The host harness `.claude/settings.json` (hard allow/deny — cannot be
   overridden).
2. `RULES.md` (binding, re-read each round).
3. The rest of this protocol (binding, read at startup).
4. Your role profile (`loopy/agents/<role>.md`).
5. Your own judgement, in service of [SOUL.md](SOUL.md).

When two say different things, the lower number wins.
