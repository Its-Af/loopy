# Deployment

Three ways to run Loopy, from simplest to most isolated.

## 1. tmux (default, local)

The squad runs as one tmux window per agent on your machine.

```bash
loopy/operator/init.sh          # once: create .loopy/ + config + settings
loopy/operator/launch-all.sh    # start everyone + the bus + watchdog, then attach
loopy/operator/status.sh --watch
loopy/operator/stop-all.sh
```

- **Attach/detach:** `attach.sh [agent]`, then `Ctrl-b d` to detach (agents keep
  running). `attach.sh producers.1` jumps straight to one agent.
- **Single agent:** `start.sh producers.2` (re)launches just that one.
- **Resilience:** the watchdog respawns dead panes with exponential backoff; the
  bus auto-restarts if its socket disappears.

Best for development and watching the squad work.

## 2. launchd (macOS, 24/7)

Keep the squad running across logouts and reboots.

```bash
loopy/operator/install-daemon.sh        # generates + loads ~/Library/LaunchAgents/com.loopy.squad.plist
loopy/operator/install-daemon.sh --uninstall
```

This runs `operator/forever.sh`, which supervises the headless squad and
relaunches it if the session ever dies. Logs land in `.loopy/logs/daemon.*.log`.

### Linux (systemd)
There's no `install-daemon.sh` for Linux, but the pattern is the same — point a
unit at `forever.sh`:

```ini
# ~/.config/systemd/user/loopy.service
[Unit]
Description=Loopy squad
[Service]
Environment=LOOPY_PROJECT_ROOT=%h/your-project
ExecStart=/bin/bash %h/your-project/loopy/operator/forever.sh
Restart=always
[Install]
WantedBy=default.target
```
`systemctl --user enable --now loopy`.

## 3. Docker (isolated, no tmux)

Each role is its own container; they share the project (and `.loopy/`) through a
bind mount and coordinate exactly as panes do. The special roles `bus` and
`watchdog` run the broker and the health monitor.

```bash
# Build + run the default roster:
ANTHROPIC_API_KEY=sk-... docker compose -f loopy/docker-compose.yml up -d --build
docker compose -f loopy/docker-compose.yml ps      # healthchecks per role
docker compose -f loopy/docker-compose.yml logs -f execs
docker compose -f loopy/docker-compose.yml down

# Custom roster? Generate a compose file from .loopy/config.md:
loopy/scripts/generate-compose.sh > docker-compose.loopy.yml
```

Each container's `LOOPY_AGENT_ID` selects what it runs (an agent id, `bus`, or
`watchdog`) via `operator/docker-start.sh`. Health is reported by
`operator/docker-status.sh` (HEALTHCHECK in the image). This is the right choice
for servers and for running the squad with strong isolation from the host.

## Operational notes

- **Capacity:** tune `max_claude_procs` / `max_inflight` / `max_load_per_cpu` in
  `.loopy/config.md` to your host. Too high risks crashing the machine; the gate
  is conservative by default.
- **Deep paths (macOS):** if your project path is long, the bus socket may exceed
  the ~104-char AF_UNIX limit. Set `LOOPY_BUS_SOCK=/tmp/loopy.sock`.
- **Secrets:** provide `ANTHROPIC_API_KEY` via the environment or `.loopy/keys.env`
  (loaded by `tools/load-keys.sh`). Never bake keys into the image or config.
- **Reset:** `stop-all.sh` preserves state; `rm -rf .loopy` then `init.sh` is a
  clean slate. Your project code is never touched.
- **Autonomous runs:** with no human to answer permission prompts, either curate
  `.claude/settings.json` `allow`/`ask` carefully or run the YOLO auto-approver —
  **only inside a disposable sandbox/container.**
