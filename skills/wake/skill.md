---
name: wake
description: Instantly trigger an agent's loop now instead of waiting for its next 5-minute tick. Use when you've sent a message or claimed a task and want a teammate (or yourself) to act immediately.
---

# /wake — instant loop trigger

The squad's parents loop every ~5 minutes. When something needs attention *now*
— you delivered an urgent message, reassigned a task, or want to re-check your
own inbox immediately — `/wake` rings the bus doorbell so the target loops at
once.

## Usage

```
/wake <agent>            # wake one agent (e.g. /wake execs)
/wake <role> --shared    # wake every instance of a role (e.g. /wake producers --shared)
/wake --all              # wake the whole squad (use sparingly)
/wake                    # wake myself — re-run my loop right now
```

## What it does

Under the hood this calls the bus client:

```bash
python3 loopy/scripts/agent-tool.py notify <agent>            # one agent
python3 loopy/scripts/agent-tool.py notify <role> --shared    # all instances
python3 loopy/scripts/agent-tool.py broadcast                 # everyone
```

The bus (`daemons/bus_broker.py`) debounces wakes (max one per pane per 5s) and
falls back to a wake-marker file if tmux send-keys isn't available. If the bus
is down the wake is simply dropped — the target still picks the work up on its
normal tick, so `/wake` is always safe to call.

## When to use it

- After `send-message` to someone who should react immediately.
- After `task reopen` so the owner sees it without delay.
- When `execs` finishes grooming and wants producers to grab fresh work.

## When NOT to use it

- As a busy-loop. Don't wake the same agent repeatedly — the debounce will drop
  the spam anyway, and the squad self-paces for a reason.
- To bypass the capacity gate. A wake makes an agent *loop*, it does not let it
  skip `capacity-check.py` before spawning subagents.
