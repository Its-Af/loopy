# Parallelism & Anti-Crash Rules

Running many Claude Code instances plus their subagents is the fastest way to
take down the host machine: memory exhaustion, CPU thrash, fork storms. These
rules keep the squad alive.

## The spawn gate

**Never spawn a subagent without passing the capacity gate first.** Every loop,
before delegating heavy work:

```bash
if python3 loopy/scripts/capacity-check.py >/dev/null; then
    # CLEAR — safe to spawn one subagent
else
    # WAIT — do not spawn this round; try again next loop
fi
```

The gate (`tools/capacity.py`) returns `WAIT` when any of these trip:

- **Too many `claude` processes** — more than `LOOPY_MAX_CLAUDE_PROCS`
  (default 12) are already running.
- **Already busy** — you have `LOOPY_MAX_INFLIGHT` (default 2) subagent results
  still pending; finish those before starting more.
- **System under load** — 1-minute load average exceeds
  `LOOPY_MAX_LOAD_PER_CPU` × CPUs (default 2.5/CPU).

Raise these limits in `.loopy/config.md` only on hosts you know can take it.

## Spawn discipline

- **One heavy subagent per loop, per parent.** Don't fan out five at once;
  stagger them across loops. The gate enforces the ceiling, but intent matters.
- **Stagger, don't stampede.** If the whole squad wakes at once (e.g. after a
  broadcast), the gate will naturally serialise spawns — trust it, don't busy-
  retry in a tight loop.
- **Subagents don't spawn subagents.** Keep the tree one level deep. A subagent
  does its job and returns a result; it does not recurse.
- **Bounded work.** Give each subagent a finite, well-scoped brief ("run the
  test suite", "implement this function") — never "keep improving things".

## Backpressure

The system self-limits through pending results: a parent with 2 results waiting
is told `WAIT` until it collects them. This means a slow consumer automatically
stops producing more load — backpressure for free, no central coordinator
needed.

## Why 60-second loops matter here too

A parent that blocks inline is invisible to the gate (its work isn't counted as
a subagent) yet still consumes a full Claude instance's resources for minutes.
Delegating heavy work to *gated* subagents is what makes total load
controllable. The 60-second rule and the spawn gate are two halves of the same
safety mechanism.

## If things still melt

The watchdog (`daemons/watchdog.sh`) caps respawns and backs off exponentially
when panes crash repeatedly, so a crash-loop can't itself become a fork bomb.
See `recovery.md`.
