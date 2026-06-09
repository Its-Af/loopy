# Skills Registry

Slash commands available to Loopy agents. Install them by pointing Claude Code's
skills directory at `loopy/skills/` (see README → Installation).

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `/wake` | [`wake/skill.md`](wake/skill.md) | Ring an agent's bus doorbell so it loops *now* instead of on its next 5-minute tick. `/wake <agent>`, `/wake <role> --shared`, `/wake --all`, or `/wake` for self. |
| `/wizard` | [`wizard/SKILL.md`](wizard/SKILL.md) | Test-driven-development discipline that turns a task into *verified* code: red → green → refactor → verify-full-suite → report honestly. Producers wrap their implementation work in it; it backs the framework's "DONE means tests pass" guarantee. |

## Authoring new skills

Each skill is a directory under `loopy/skills/` containing a `SKILL.md` (or
`skill.md`) with YAML frontmatter:

```markdown
---
name: my-skill
description: One sentence on when to use it — this is what the model matches on.
---
# /my-skill
Instructions...
```

Keep `description` action-oriented (it drives triggering accuracy) and put long
reference material in a `supporting/` subdirectory the SKILL links to, so the
main file stays short.
