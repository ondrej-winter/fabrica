---
name: run-python-tests
description: Run pytest-based automated tests when a Python project uses uv-managed development tooling.
metadata:
  version: "1.1.0"
  dependencies:
    tools:
      - name: uv
        purpose: Run the project's test tooling in its managed environment.
        required: true
      - name: pytest
        purpose: Run the automated Python test suite.
        required: true
    skills: []
---

# Skill: Run Python Tests

Use this skill when a Python project runs its `pytest` test suite through `uv`.

## Prerequisites

- `uv` is installed and configured for the project.
- `pytest` is installed as a development dependency and configured in
  `pyproject.toml` or another supported pytest configuration file.

## Steps

### 1. Discover the project command and targets

Inspect `pyproject.toml`, project documentation, and existing task definitions.
Use the project's test command when one is defined. Otherwise, use the fallback
commands below.

### 2. Run all tests

```bash
uv run pytest
```

This command executes all tests defined in the project.

### 3. Run focused tests (optional)

```bash
uv run pytest tests/<path_to_test_file>
uv run pytest -k "<pattern>"
```

Use these commands to run a subset of tests during development.

### 4. Verify and report the result

After resolving any failures, re-run the full project-configured test suite. Report
the command and targets used, whether the suite passed, and any tests that could not
run with the reason.

## When tests fail

- Read the test output to identify the failing test and the assertion or exception that caused the failure.
- Fix the root cause in the source code or test rather than skipping or deleting the test.
- Use `uv run pytest -x` to stop at the first failure during iterative debugging.
- For flaky or slow tests, document the reason and mitigation in the handoff notes rather than silently ignoring them.
- After fixes, re-run the full test suite with `uv run pytest` before handoff.
