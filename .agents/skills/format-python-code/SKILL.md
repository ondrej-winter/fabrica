---
name: format-python-code
description: Format Python code with ruff and apply safe auto-fixes when a Python project needs consistent style before linting, testing, or handoff.
metadata:
  version: "1.1.0"
  dependencies:
    tools:
      - name: uv
        purpose: Run the project-managed Ruff installation.
        required: true
      - name: ruff
        purpose: Apply Python lint fixes and formatting.
        required: true
    skills:
      - name: lint-python-code
        purpose: Continue with linting and type checking when required.
        required: false
---

# Format Python Code

Use this skill to format Python code and apply safe auto-fixes using `ruff` before
linting, testing, or handing off changes.

## Prerequisites

- `uv` is installed and configured for the project.
- `ruff` is installed as a development dependency and configured in
  `pyproject.toml` or a supported Ruff configuration file.

## Steps

### 1. Apply auto-fixes and format

```bash
uv run ruff check . --fix
uv run ruff format .
```

These commands reformat Python code and apply lint fixes that Ruff considers safe
under the project's configuration. If the project defines narrower source or test
paths, use those paths instead of `.`.

### 2. Review and validate the result

Review the changed files and confirm that formatting and auto-fixes preserved the
intended behavior. Then run Ruff in check mode against the same target:

```bash
uv run ruff check .
uv run ruff format . --check
```

Replace `.` consistently when narrower paths were formatted. Both commands must
pass before handoff. Continue with the `lint-python-code` skill when broader
linting or type checking is required.

## When formatting fails

- If `ruff format` produces unexpected changes, verify the project's Ruff
  configuration before overriding the formatter.
- If `ruff check --fix` leaves violations, review and resolve them with the
  `lint-python-code` skill rather than enabling unsafe fixes without justification.
- Record any command that could not run and its error in the handoff notes.
