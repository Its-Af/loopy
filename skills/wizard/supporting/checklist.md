# Pre-"done" checklist

Before you mark a task `done`, every box must be true. If any is false, the task
stays open.

- [ ] There is a test that **fails without my change** and passes with it.
- [ ] The **full** suite is green locally (not just my new test).
- [ ] I ran it myself this loop — I'm not trusting a stale or remembered run.
- [ ] The change actually does **what the task asked**, not a near-miss.
- [ ] Edge cases I can think of are covered (empty, large, malformed, concurrent).
- [ ] No secrets, debug prints, or commented-out code left behind.
- [ ] Public behaviour changes are reflected in docs/help where relevant.
- [ ] I recorded any non-obvious decision (`agent-tool.py record-decision`).
- [ ] My `done` note says what changed and which tests cover it.

If a critic or QA can reopen this in thirty seconds by reading the diff, it
wasn't done. Better to leave it open and honest.
