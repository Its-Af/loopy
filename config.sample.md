# Loopy Squad Configuration

Copy this file to `.loopy/config.md` (the `init.sh` script does this for you)
and edit to taste. Only the `Roster` and `Settings` lines below are parsed; the
prose is for humans.

## Roster

Each line `- <role>: <count>` sets how many instances of a role to launch.
Roles are fixed by the framework (you can change counts, not names). Set a count
to `0` to disable a role.

- execs: 1
- alfred: 1
- producers: 3
- qas: 1
- critics: 1
- securities: 1
- users: 1

## Settings

`key: value` pairs read by the operator scripts. Unset keys use the defaults
shown.

- session: loopy          # tmux session name
- loop_interval: 5m       # how often each parent loop fires
- max_claude_procs: 12    # capacity gate: max concurrent claude processes
- max_inflight: 2         # capacity gate: max pending subagent results per agent
- max_load_per_cpu: 2.5   # capacity gate: 1-min load average ceiling per CPU
- wake_keys: Enter        # tmux send-keys sequence used to wake a pane
- auto_approve: off       # 'on' enables the YOLO auto-approver daemon (danger)

## Project goal (free text — read by alfred + execs at startup)

> Describe what you want the squad to build or maintain. This is the human's
> standing instruction; agents read it to orient. For example:
>
> "Build and maintain the REST API in `src/api/`. Keep the test suite green,
>  document every endpoint, and treat p95 latency under 100ms as a hard
>  requirement."
