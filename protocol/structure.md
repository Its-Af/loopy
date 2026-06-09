# Directory Layout & File Formats

Loopy separates **code** from **state**:

- `loopy/` — the framework (this submodule). Read-only at runtime.
- `.loopy/` — all mutable runtime state, a sibling at the project root. Created
  by `operator/init.sh`. Safe to delete to fully reset the squad.

## `.loopy/` runtime tree

```
.loopy/
├── config.md                 # squad roster + settings (from config.sample.md)
├── bus.sock                  # message-bus Unix socket (ephemeral)
├── bus-status.json           # broker health snapshot
├── panes.json                # agent-id -> tmux pane map (written by launcher)
├── bus/tokens/<role>.token   # per-role bus auth tokens (0600, regenerated)
├── inbox/
│   ├── <agent>/              # private inbox, drained by exactly one reader
│   ├── <role>.shared/        # shared inbox, fanned out to every instance
│   ├── <agent>.seen          # per-instance seen-set for the shared inbox
│   └── .ratelimit/<sender>.json
├── quarantine/<agent>/       # messages rejected by injection screening
├── wake/<agent>              # bus wake markers (fallback signal)
├── state/<agent>.json        # one-line heartbeat per agent
├── tasks/<ulid>.json         # the task store (source of truth)
├── memory/<agent>/
│   ├── briefing.md           # living self-summary
│   └── decisions.jsonl       # append-only decision log (rotated)
├── results/<agent>/<ulid>.json   # subagent results awaiting the parent
├── metrics/latency.jsonl     # loop + operation timings
├── intents/<hash>.json       # intent locks on source files
└── locks/                    # flock sidecar files
```

`#TODO` lives at the **project root** (not in `.loopy/`) — it is the
human-facing board, a regenerated projection of `.loopy/tasks/`.

## Key file formats

### Task — `.loopy/tasks/<ulid>.json`
```json
{
  "id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "title": "Implement login", "description": "...",
  "state": "CLAIMED", "priority": "P0", "owner": "producers.1",
  "created_by": "execs", "created_at": 1780000000.0, "updated_at": 1780000100.0,
  "blocked_by": [], "tags": ["auth"], "history": [ {"event": "claimed", ...} ]
}
```
States: `OPEN · REOPENED · CLAIMED · IN_PROGRESS · BLOCKED · REVIEW · DONE`.
Priorities: `P0 · P1 · P2 · P3`. IDs are ULIDs, so a directory listing is
time-ordered.

### Inbox message — `.loopy/inbox/<agent>/{epoch_us}-{nonce}-{sender}.md`
```
---
from: producers.1
to: execs
ts_us: 1780000000000000
---
⟦UNTRUSTED-MESSAGE⟧
Login form is 80% done, blocked on the session-store decision.
⟦END-UNTRUSTED-MESSAGE⟧
```
The filename is lexically time-sortable. The body is always fenced as untrusted
data. Max 2 KB; sender-rate-limited to 5 / 5 min.

### Agent state — `.loopy/state/<agent>.json`
```json
{"agent": "producers.1", "status": "implementing login", "loop": 42,
 "pid": 12345, "task": "01ARZ...", "updated_at": 1780000100.0, "detail": ""}
```
An agent with no update for ~18 min is considered **stale** (possibly dead).

### Result — `.loopy/results/<parent>/<ulid>.json`
```json
{"id": "01ARZ...", "parent": "execs", "kind": "build", "ok": true,
 "summary": "build green, 0 warnings", "subagent": "bg-build", "payload": null}
```

## Hot (protected) files

These may only be edited when doing so is *explicitly the task*. Producers must
not casually rewrite them:

- `loopy/protocol/**` — the rules themselves
- `loopy/agents/**` — agent profiles
- `.loopy/canary.json` — integrity manifest (see `scripts/verify-canary.py`)
- `.git/**` — never touched directly

`scripts/hot-files-check.sh` enforces this; the canary verifies the protocol
hasn't been tampered with between rounds.
