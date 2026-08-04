# Tooling and CI conventions

This ruleset uses an opinionated toolchain:

- `uv` for dependency management, environment management, and command execution
- `ruff` for formatting, linting, and import cleanup
- `ty` for type checking
- `pytest` for tests

Run project tooling through `uv run ...`. Keep tool configuration in `pyproject.toml`.
Use the dedicated quality-gate skills for command order and operator workflow:
`format-python-code`, `lint-python-code`, `run-python-tests`, and
`run-local-quality-gate`.

## Dependency groups

- Keep runtime dependencies in the main `dependencies` list under `[project]` and development-only tooling in dependency groups such as `[dependency-groups].dev`.
- Sync the dependency groups required by the project before running validation commands.

## Local quality gate

Use the `run-local-quality-gate` skill to run the full local quality gate.
Use specialized skills when you need only one part of that workflow during iteration.

## Expectations

- Generated code **must** pass `uv run ruff check .`, `uv run ty check .`, and `uv run pytest` with no unapproved failures.
- Code **must** be formatted with `uv run ruff format .`.
- If behavior changes, you **must** add or update tests and run the relevant impacted suites.
- Do not disable lint rules unless explicitly requested; prefer refactoring.
- CI failures must be fixed at the root cause.

## Usage clarifications

- Run the full quality gate before handoff, even if only a single file changed.
- If a change affects only a subset of tests, run focused checks first, then complete the full configured gate before handoff.
- In monorepos, run the same configured gates from the affected package or service root plus any impacted shared gates.
- Pre-commit hooks provide fast feedback, but they do **not** replace the full local quality gate.
- For flaky or slow tests, document the reason and mitigation in the handoff notes.
- Do not bypass `pyproject.toml`-backed tool configuration with ad hoc flags in the final validation run.

## Reproducibility and dependency hygiene

- Dependency changes **must** update `pyproject.toml` and `uv.lock` together.
- CI should validate in a clean environment created with `uv sync --frozen --all-groups`.
- Keep supported Python version(s) documented in `pyproject.toml` and CI so local and remote validation use the same baseline.

## Architecture validation

- If a change crosses layers, include tests that verify boundary adherence, such as ports being invoked and adapters being wired correctly.
- Document any intentional rule exceptions in the PR description and handoff notes.
