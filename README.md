# Loopy

**A file-based multi-agent coordination framework.** Loopy runs a "virtual
squad" of N+ Claude Code instances in parallel — coding, reviewing, testing,
attacking, and using your software — coordinating entirely through shared files
and a lightweight wake bus. It drops into any project as a git submodule.

```
                 ┌──────────┐   files + bus    ┌──────────┐
   human ◀──────▶│  alfred  │◀───────────────▶│  execs   │  owns #TODO
                 └──────────┘                  └────┬─────┘
                                                    │ tasks
        ┌───────────────┬───────────────┬───────────┼───────────┬───────────┐
        ▼               ▼               ▼           ▼           ▼           ▼
   producers.1    producers.2    producers.3      qas        critics   securities   users
     (code)         (code)         (code)       (tests)     (review)   (attack)    (UAT)
```

Every agent runs the same fast loop, delegates heavy work to background
subagents, and never blocks for more than ~60 seconds. Correctness lives in the
filesystem; the bus only makes things faster. Kill any agent and restart it — it
reads its files and carries on.

---

## Why Loopy

- **Self-coordinating.** No central scheduler. Agents claim work cooperatively
  (a `flock`-backed compare-and-set — proven race-free under a 12-process test),
  message each other, and heal around failures.
- **Honest by construction.** "DONE" means *verified*: producers must pass tests,
  critics independently re-review, QA re-runs the suite, the `users` agent scores
  the experience harshly. A green lie gets reopened.
- **Hardened against itself.** The inbox screens every message for prompt
  injection (incl. Unicode homoglyphs), quarantines attacks, rate-limits senders,
  and fences delivered text as untrusted data. A canary detects tampering with
  the rules themselves.
- **Zero runtime dependencies.** The whole framework is Python standard library
  plus bash. pytest is the only dev dependency.
- **Crash-proof + inspectable.** All state is atomic files under `.loopy/` you
  can `cat`. Delete `.loopy/` to fully reset; your code is never touched.

## The squad

| Role | Count | Job |
|------|-------|-----|
| `execs` | 1 | Project manager — owns `#TODO`, prioritises, unblocks, reassigns dead agents' work, guards the canary. |
| `alfred` | 1 | Butler — the human's interface. Monitors health, never writes code. |
| `producers` | 3 | Coders — implement features/fixes via TDD, one task at a time. |
| `qas` | 1 | Test engineer — runs suites, files coverage gaps as bugs. |
| `critics` | 1 | Reviewer — verifies every `done`, reopens what isn't real. |
| `securities` | 1 | Attacker — finds vulns, writes PoCs, watches quarantine + canary. |
| `users` | 1 | Impatient user — UAT and UX friction, scores 1–9 (10 doesn't exist). |

Counts are configurable in `.loopy/config.md`.

## Installation

Loopy is designed to be **vendored into your project as a git submodule** and
driven by a single command. Three steps:

```bash
# 1. Add Loopy to your repo (lives at ./loopy, runtime state at ./.loopy)
cd your-project
git submodule add https://github.com/your-org/loopy.git loopy

# 2. Install — checks prerequisites, sets up .loopy/, scans your repo for
#    context, installs git hooks, and pulls the Claude Code CLI.
cd loopy && npm install        # equivalently:  make install   |   ./bin/loopy install
cd ..

# 3. Start the squad (uses tmux if installed, else background processes)
loopy/bin/loopy start
```

That's it. On first run, `install` creates the `.loopy/` runtime in **your
repo's** root and scans the whole project (languages, README, `CLAUDE.md`,
layout) into `.loopy/project-context.md`, which every agent reads at startup —
so the squad understands the codebase it was dropped into.

> **No npm?** Use `make install` or `loopy/bin/loopy install` — they do the same
> thing. Loopy's runtime is pure Python standard library; the only external tool
> is the Claude Code CLI, which `npm install` pulls automatically (or install it
> globally: `npm i -g @anthropic-ai/claude-code`).

Check readiness any time with `loopy/bin/loopy doctor`. Then tell the squad what
to build by editing the **Project goal** section of `.loopy/config.md` (or just
`loopy/bin/loopy chat alfred "build me X"`).

Optional — wire up the skills and MCP servers for richer agent capabilities by
adding to your `.claude/settings.json`:

```jsonc
{
  "mcpServers": {
    "loopy-inbox":    { "command": "python3", "args": ["loopy/mcp/inbox.py"] },
    "loopy-tmux":     { "command": "python3", "args": ["loopy/mcp/tmux.py"] },
    "loopy-registry": { "command": "python3", "args": ["loopy/mcp/registry.py"] }
  }
}
```

### Requirements
- Python 3.10+ (3.13 tested)
- bash (3.2+ — macOS default is fine)
- tmux (for the host/tmux deployment; not needed for Docker)
- The Claude Code CLI on `PATH` (`@anthropic-ai/claude-code`)
- `ANTHROPIC_API_KEY` in the environment (or `.loopy/keys.env`)

## Usage

One command does everything via `loopy/bin/loopy` (run from your repo root):

```bash
loopy/bin/loopy start            # launch the squad (tmux UI, or background if no tmux)
loopy/bin/loopy status           # health dashboard (add --watch to live-refresh)
loopy/bin/loopy chat alfred "build me a REST API for todos"
loopy/bin/loopy attach producers.1   # jump to one agent's pane (tmux mode)
loopy/bin/loopy logs             # tail agent logs (background mode)
loopy/bin/loopy stop             # stop everything (state preserved)
```

`loopy start` picks the best terminal interface available: a **tmux** session
(one pane per agent) when tmux is installed, otherwise a **background process**
mode you observe with `loopy logs` / `loopy status`. `npm start` / `make start`
do the same.

Talk to the squad through **alfred**; alfred relays goals to **execs**, who
breaks them into tasks the **producers** pick up. **critics**, **qas**,
**securities**, and **users** keep them honest.

Drive the coordination layer directly any time:

```bash
A=loopy/scripts/agent-tool.py
python3 $A status
python3 $A task create "Add /health endpoint" --priority P1
python3 $A read-inbox --agent execs
```

See [`tools/REGISTRY.md`](tools/REGISTRY.md) for the full command surface.

## How it works (the 30-second version)

1. Each agent runs `/loop 5m` — a loop that re-reads the rules, drains its
   inbox, collects subagent results, claims work, and delegates anything heavy
   to a **background subagent** (gated by `capacity-check.py` so the host never
   melts). The parent loop stays under 60 seconds.
2. Heavy work runs in subagents and drops a **result file**; the parent collects
   it on a later loop.
3. Messages are atomic files in the recipient's inbox; a **wake** over the Unix
   socket bus nudges them to loop *now*. Bus down? Messages still arrive next
   tick.
4. The board (`#TODO`) is a regenerated projection of the `.loopy/tasks/` JSON
   store — the source of truth.

Read [`protocol/PROTOCOL.md`](protocol/PROTOCOL.md) for the full design, and
[`SYSTEM.md`](SYSTEM.md) for a plain-English tour.

## Testing

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
cd loopy && ../.venv/bin/python -m pytest          # 123 tests, incl. a live-bus
                                                    # and 12-process race test
```

## Documentation

| Doc | What |
|-----|------|
| [SYSTEM.md](SYSTEM.md) | Plain-English system guide (no code) |
| [protocol/](protocol/) | The squad's constitution (RULES, SOUL, architecture…) |
| [agents/](agents/) | The seven role profiles |
| [SETTINGS.md](SETTINGS.md) | Companion to `settings.reference.json` |
| [DEPLOYMENT.md](DEPLOYMENT.md) | tmux, launchd, and Docker deployment |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup and conventions |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## License

MIT — see [LICENSE](LICENSE).
