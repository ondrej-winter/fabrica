---
name: run-python-quality-gate
description: Run the project-defined Python quality gate with formatting, linting, type checking, architecture checks, and tests before handoff or a pull request.
metadata:
  version: "3.0.0"
  dependencies:
    tools:
      - name: uv
        purpose: Run the project's development tools in its managed environment.
        required: true
      - name: ruff
        purpose: Apply formatting and safe fixes, then verify Python lint rules.
        required: true
      - name: type-checker
        purpose: Run the static type checker configured by the target project, such as ty or mypy.
        required: true
      - name: pytest
        purpose: Run the automated test suite.
        required: true
    skills:
      - name: run-local-quality-gate
        purpose: Discover and run the complete repository-defined validation sequence.
        required: true
---

# Run Python Quality Gate

Use this skill as the Python-specific entry point for a complete local quality
gate. Delegate command discovery, sequencing, failure handling, and reporting to
`run-local-quality-gate` so the repository's selected tools remain authoritative.

## Prerequisites

- `uv` is installed and configured for the project.
- The repository documents or configures its formatting, linting, type-checking,
  architecture, and test commands.
- The same skill root provides `run-local-quality-gate`.

## Steps

### 1. Discover the Python quality gate

Inspect repository instructions, `pyproject.toml`, task definitions, and CI. The
project may use `ty`, `mypy`, or another type checker and may include
import-boundary, build, documentation, or packaging checks.

Do not substitute a generic tool for an established project command.

### 2. Delegate the complete run

Use `run-local-quality-gate` to execute focused checks during iteration and the
broadest practical repository-defined gate before handoff.

For a typical `uv` project this may include:

```bash
uv run ruff check . --fix
uv run ruff format .
uv run ty check src tests
uv run lint-imports
uv run pytest
```

These are examples, not replacements for repository instructions.

### 3. Verify and report the result

After resolving any failures, run the complete quality gate again. Report the
commands and targets used, whether each check passed, and any check that could not
run with the reason.

## When a step fails

- If any step fails, stop and fix the underlying issue before proceeding to the next step.
- Do not bypass `pyproject.toml`-backed tool configuration with ad hoc flags in the final validation run.
- Run the full quality gate before handoff, even if only a single file changed.
- Pre-commit hooks provide helpful fast feedback, but they do not replace the full local quality gate.
- Do not omit configured import-boundary or architecture checks from the final
  result.
