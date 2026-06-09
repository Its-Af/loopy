# The TDD Cycle (in depth)

A longer treatment of the five phases in `/wizard`, with the failure modes each
phase guards against.

## 1. Red — write a failing test first
- The test encodes *what the task asked for*, in executable form. If you can't
  write the test, you don't yet understand the task — go ask `execs`.
- Run it and watch it fail. A test that passes before you've written any code is
  testing the wrong thing.
- One behaviour per test. A test that asserts five things tells you little when
  it goes red.

## 2. Green — minimum to pass
- Write the least code that makes the red test green. Resist building the
  general case before a second test demands it.
- Hard-coding a return value to get green is *allowed* here — the next test will
  force you to generalise. This keeps steps tiny and reversible.

## 3. Refactor — clean with the net up
- Now improve names, remove duplication, handle the edge cases you spotted —
  re-running the suite after each change. The green tests are your safety net.
- Refactor production *and* test code. Ugly tests rot fastest.

## 4. Verify — the whole suite
- Run everything, not just your new test. The bug you introduced is usually
  somewhere you weren't looking.
- Flaky? A test that sometimes fails is a failing test. File it (QA cares) — do
  not retry until it's green and call it done.

## 5. Report — honestly
- **Green:** `task done <id>` with a note: what changed, which tests cover it.
- **Red / blocked:** keep the task, summarise the exact failure, and either fix
  it or `task release <id>` and message `execs`. Never round a red up to done.

## Why the order matters
Writing the test first is the whole point: it proves the test can fail, pins the
behaviour before the implementation can bias it, and leaves behind exactly the
regression guard the next change will need. Tests written after the fact tend to
assert what the code *does*, not what it *should* do.
