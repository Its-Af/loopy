---
name: wizard
description: Test-driven development methodology wrapper for Loopy agents. Use when implementing a feature or fixing a bug so the work is driven by a failing test first, verified green, and reported honestly. Producers wrap their LOOP work in this.
---

# /wizard — TDD methodology

`/wizard` is the discipline that turns a task into *verified* code. Every
producer runs its implementation work through these phases; the framework's
honesty guarantee ("DONE means tests pass") depends on it. See
`supporting/tdd-cycle.md` and `supporting/checklist.md` for the detail.

## The cycle

1. **Understand.** Re-read the task and its acceptance criteria. If they're
   ambiguous, message `execs` rather than guessing.
2. **Red.** Write the smallest failing test that captures the desired
   behaviour. Run it; confirm it fails for the *right* reason.
3. **Green.** Write the minimum code to pass that test. Nothing more.
4. **Refactor.** Clean up — names, duplication, edge cases — keeping the suite
   green.
5. **Verify.** Run the *full* suite, not just your new test, to catch
   regressions. This is the step that earns the right to say "done".
6. **Report honestly.** If green, mark the task done with a note on what
   changed and which tests cover it. If red, keep the task and say exactly
   what's failing — never mark a red task done.

## How it fits the LOOP

Heavy work goes to a background subagent (the parent loop stays under 60s). The
parent briefs the subagent with this cycle:

```
Implement <task> using TDD: write a failing test, make it pass, refactor, then
run the full suite. Do not claim success unless the whole suite is green. When
done: python3 loopy/scripts/agent-tool.py post-result producers.<me> implement \
  --summary "<n passed / n failed; files touched>" [--fail]
```

The parent collects the result next loop and only then transitions the task.

## Non-negotiables

- **No green lies.** A passing new test with a broken suite is a failure.
- **Test first.** Code without a test that would have caught its absence isn't
  done — it's a guess.
- **Small steps.** One behaviour, one test, one commit's worth of change.
- **Record decisions.** Non-obvious design choices go in your decision log
  (`agent-tool.py record-decision`).

See:
- [supporting/tdd-cycle.md](supporting/tdd-cycle.md) — the cycle in depth.
- [supporting/checklist.md](supporting/checklist.md) — the pre-"done" checklist.
