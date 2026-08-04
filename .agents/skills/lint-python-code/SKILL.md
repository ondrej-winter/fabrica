---
name: lint-python-code
description: Run project-configured Python linting and type checking with Ruff and mypy when a project uses uv-managed development tooling.
metadata:
  version: "1.1.0"
  dependencies:
    tools:
      - name: uv
        purpose: Run the project's development tools in its managed environment.
        required: true
      - name: ruff
        purpose: Check Python code for lint violations.
        required: true
      - name: mypy
        purpose: Perform static type checking.
        required: true
    skills: []
---

# Lint Python Code

Use this skill when a Python project is configured to run Ruff for linting and
`mypy` for static type checking through `uv`.

## Prerequisites

- `uv` is installed and configured for the project.
- Ruff and `mypy` are installed as development dependencies.
- The project includes configuration for Ruff and `mypy`, such as in
  `pyproject.toml` or tool-specific configuration files.

## Steps

### 1. Discover the project commands and targets

Inspect `pyproject.toml`, project documentation, and existing task definitions.
Use the project's lint and type-check commands when they are defined. Otherwise,
use the fallback commands below with the narrowest configured source and test
paths.

### 2. Run Ruff linting

```bash
uv run ruff check .
```

This command checks for linting errors without applying auto-fixes.

### 3. Run mypy type checking

```bash
uv run mypy .
```

This command performs static type checking on the Python codebase.

### 4. Verify and report the result

After fixing any failures, re-run both project-configured checks. Report the
commands and targets used, whether each check passed, and any check that could not
run with the reason.

## When linting or type checking fails

- Read the `ruff check` output carefully. Each violation includes a rule code,
  file path, and line number. Fix the underlying code rather than adding `# noqa`
  comments unless the suppression is explicitly justified.
- Do not disable lint rules to silence violations. Prefer refactoring the code to
  satisfy the rule.
- Read `mypy` errors and fix the type annotations or logic that caused them. Use
  `# type: ignore[<code>]` only at narrowly scoped boundaries to genuinely untyped
  third-party code, and document the reason.
- If a `mypy` error reflects a genuine design issue, such as a wrong return type
  or missing protocol method, fix the design rather than suppressing the error.
