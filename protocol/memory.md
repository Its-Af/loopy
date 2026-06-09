# Memory Protocol

An agent process is ephemeral — it crashes, restarts, and loses its working
context regularly. Memory is how an agent stays *itself* across those gaps.
Two artifacts, both under `.loopy/memory/<agent>/`:

## Briefing — your living self-summary

`briefing.md` answers: *what do I know and what am I in the middle of?* It is
the first thing you read on startup and the thing that lets a restarted you pick
up where you left off.

- **Read** at startup and whenever you need orientation.
- **Rewrite** it whenever it goes stale (older than 24 h) — LOOP step 3 checks
  this for you:

  ```bash
  if python3 loopy/scripts/agent-tool.py briefing-stale; then
      python3 loopy/scripts/agent-tool.py write-briefing "$(compose_briefing)"
  fi
  ```

A good briefing is a tight paragraph or two: what you own, what's in flight,
known blockers, who you're waiting on, and any decision you must not forget. Not
a journal — a snapshot you'd hand your replacement.

## Decisions — append-only reasoning log

`decisions.jsonl` answers: *why did we do it this way?* Record any consequential
choice so a reviewer (or future you) can reconstruct the reasoning:

```bash
python3 loopy/scripts/agent-tool.py record-decision \
    "Used optimistic locking for cart updates" \
    --rationale "writes are rare and conflicts cheaper to retry than to lock" \
    --task 01ARZ3NDEKTSV4RRFFQ69G5FAV
```

The log is **rotated automatically** — only the most recent entries are kept
(default 500, trimmed to 400) so memory stays bounded. Don't log trivia; log
the choices someone might later question.

## What memory is *not*

- Not a place for secrets. Never write credentials or tokens into memory.
- Not shared. Your memory is private; coordinate with teammates through the
  inbox, not by reading their briefings.
- Not the task store. Status of *work* lives in `.loopy/tasks/`; memory is your
  private understanding, not the squad's shared ground truth.

## Rhythm

| When | Do |
|------|-----|
| Startup | read briefing + recent decisions to rebuild context |
| Each loop | if briefing stale → rewrite it |
| After a real decision | `record-decision` with a rationale |
| Before a risky/irreversible step | record the intent and the why first |

Memory is cheap insurance against amnesia. Keep it current and honest, just
like everything else in Loopy.
