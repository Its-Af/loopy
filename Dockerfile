# Loopy container image.
#
# One image, many roles: the container's LOOPY_AGENT_ID selects what it runs
# (an agent, the "bus", or the "watchdog") via operator/docker-start.sh. In
# Docker there is no tmux — each role is its own container, coordinating through
# the shared .loopy/ volume exactly as panes do on a host.
FROM python:3.12-slim

# Runtime tools: bash for the operator scripts, git for the project, curl/node
# for the Claude Code CLI.
RUN apt-get update && apt-get install -y --no-install-recommends \
        bash git curl ca-certificates procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# The framework lives at /app/loopy; the host project is bind-mounted at /work.
WORKDIR /work
COPY . /work/loopy
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/work/loopy \
    LOOPY_PROJECT_ROOT=/work \
    LOOPY_AGENT_ID=alfred

# Loopy itself needs no pip packages (stdlib only); install pytest only if you
# intend to run the suite inside the image.
# RUN pip install --no-cache-dir pytest

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD bash /work/loopy/operator/docker-status.sh || exit 1

ENTRYPOINT ["bash", "/work/loopy/operator/docker-start.sh"]
