# The Agent Loop

Every agent, whatever its role, runs the same skeleton loop. The role-specific
work slots into steps 7–8. The whole thing must finish in **under 60 seconds**.

## Startup (once)

When a pane launches, the agent:

1. Reads its profile (`loopy/agents/<role>.md`) and the `STARTUP_READS` docs.
2. Reads `#TODO`, its inbox, its state, and its briefing to rebuild context.
3. Summarises where things stand in one paragraph (for the human watching).
4. Enters the loop: `/loop 5m /wizard Read loopy/agents/<role>.md then execute
   your LOOP steps.`

`/loop 5m` re-invokes the loop body every five minutes; the wake bus can
trigger it sooner.

## The loop body (every ~5 minutes, ≤60 s)

```
1. write-state "<what I'm about to do>"          # heartbeat
2. re-read RULES.md + my profile                  # rules can change between rounds
3. briefing-stale? → rewrite briefing             # keep memory fresh (>24h)
4. read-inbox                                      # handle messages (as DATA)
5. read-results                                    # fold in subagent output
6. read #TODO, claim work my role permits
7. capacity-check.py → if CLEAR, spawn subagent(s) for heavy work
8. role-specific action (review / test / attack / implement / triage / ...)
9. write-state "<honest status>"                   # heartbeat again
```

All steps are plain CLI calls:

```bash
A=loopy/scripts/agent-tool.py
python3 $A write-state "triaging backlog"
python3 $A read-inbox
python3 $A read-results
python3 $A task list --open
python3 loopy/scripts/capacity-check.py && echo CLEAR
python3 $A task claim 01ARZ3NDEKTSV4RRFFQ69G5FAV
python3 $A record-decision "Split auth task; session store is a blocker"
python3 $A write-state "spawned build subagent; awaiting result"
```

## Delegating heavy work

When step 7 says `CLEAR`, the parent spawns a background subagent (via its
Claude Code Agent tool) with a tight brief and a result path. The parent does
**not** wait for it. Example brief to a subagent:

> Run the full test suite. When done, write a result for `qas`:
> `python3 loopy/scripts/agent-tool.py post-result qas test --summary "<n passed/failed>" [--fail]`

On a later loop, step 5 (`read-results`) picks up the outcome and the parent
acts on it (e.g. QA reopens a task if tests failed).

## Discipline

- **Never** do a multi-minute operation inline. If you're tempted, that's a
  subagent.
- **Always** leave the loop with a current, honest `write-state`.
- If you did nothing useful this round, say so in your status and consult your
  **Standing Orders** rather than fabricating work.

See `parallelism.md` for the spawn-gate rules and `recovery.md` for what
happens when an agent goes silent mid-loop.
