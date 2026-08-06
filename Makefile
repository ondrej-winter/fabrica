.PHONY: help test test-live-codex test-live-runtime run-live-cli commit-message commit deps-tree deps-outdated deps-audit

PROMPT ?= Reply with the single word: pong
FABRICA_GLOBAL_OPTIONS ?=

help:
	@echo "Available targets:"
	@echo "  make test             Run default offline test suite"
	@echo "  make test-live-codex  Run opt-in live Codex backend test"
	@echo "  make test-live-runtime Run opt-in live Codex-backed runtime test"
	@echo "  make run-live-cli     Run explicit live CLI prompt via Codex-backed runtime"
	@echo "  make commit-message   Propose a Conventional Commit message from staged changes"
	@echo "  make commit           Interactively commit staged changes after confirmation"
	@echo "  make deps-tree        Show the full dependency tree"
	@echo "  make deps-outdated    Show outdated top-level dependencies"
	@echo "  make deps-audit       Audit dependencies for known vulnerabilities"

test:
	uv run pytest

test-live-codex:
	FABRICA_RUN_LIVE_CODEX_TESTS=1 uv run pytest -m live_codex tests/integration/features/codex_transport/test_live_codex_backend.py

test-live-runtime:
	FABRICA_RUN_LIVE_CODEX_TESTS=1 uv run pytest -m live_codex tests/integration/features/agent_runtime/test_live_local_agent_runtime.py

run-live-cli:
	uv run fabrica $(FABRICA_GLOBAL_OPTIONS) run --prompt "$(PROMPT)"

commit-message:
	uv run fabrica $(FABRICA_GLOBAL_OPTIONS) commit-message \
	  --skill conventional-commits \
	  --skill-root .agents/skills

commit:
	uv run fabrica $(FABRICA_GLOBAL_OPTIONS) commit \
	  --skill conventional-commits \
	  --skill-root .agents/skills

deps-tree:
	uv tree --frozen

deps-outdated:
	uv tree --frozen --depth 1 --outdated

deps-audit:
	mkdir -p .tmp
	uv export --frozen --no-hashes --format requirements.txt -o .tmp/requirements-audit.txt
	uvx --from pip-audit pip-audit -r .tmp/requirements-audit.txt
