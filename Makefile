# Loopy — common dev/operator tasks. `make help` lists targets.
# Runtime needs no third-party deps (Python stdlib); `make test` adds pytest in a venv.
SHELL := /bin/bash
LOOPY := ./bin/loopy

.PHONY: help install dev start stop status doctor scan test clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-9s\033[0m %s\n",$$1,$$2}'

install: ## Set up Loopy in the host repo (.loopy/, hooks, host scan)
	@$(LOOPY) install

dev: ## Set up + create a venv with pytest
	@$(LOOPY) install --dev

start: ## Launch the squad (tmux if available, else background)
	@$(LOOPY) start

stop: ## Stop the squad
	@$(LOOPY) stop

status: ## Health dashboard
	@$(LOOPY) status

doctor: ## Environment readiness report
	@$(LOOPY) doctor

scan: ## Re-scan the host repo into .loopy/project-context.md
	@$(LOOPY) scan

test: ## Run the test suite (creates .venv if needed)
	@if [ ! -x .venv/bin/python ]; then python3 -m venv .venv && .venv/bin/pip install -q pytest; fi
	@.venv/bin/python -m pytest

clean: ## Remove caches (keeps the .loopy runtime)
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .coverage
