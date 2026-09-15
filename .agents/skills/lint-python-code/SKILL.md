---
name: lint-python-code
description: Run project-configured Python linting, type checking, and architecture checks when a Python project uses uv-managed development tooling.
metadata:
  version: "1.2.0"
  dependencies:
    tools:
      - name: uv
        purpose: Run the project's development tools in its managed environment.
        required: true
      - name: ruff
        purpose: Check Python code for lint violations.
        required: true
      - name: type-checker
        purpose: Run the static type checker configured by the target project, such as ty or mypy.
        required: true
    skills: []
---

# Lint Python Code

Use this skill when a Python project needs its configured lint, type-check, and
optional import-boundary or architecture checks run through `uv`.

## Prerequisites

- `uv` is installed and configured for the project.
- Ruff and the project's selected type checker are installed as development
  dependencies.
- The project includes configuration for its lint, type-check, and any
  architecture-validation tools.

## Steps

### 1. Discover the project commands and targets

Inspect `pyproject.toml`, project documentation, and existing task definitions.
Use the project's documented or task-runner commands when they are defined. Do
not replace an established type checker or architecture check with a generic
fallback. If no command is documented, inspect `pyproject.toml` and tool-specific
configuration to identify the selected tools and targets.

### 2. Run Ruff linting

```bash
uv run ruff check .
```

This command checks for linting errors without applying auto-fixes.

### 3. Run the configured type checker

Use the configured project command. Common examples are:

```bash
uv run ty check src tests
uv run mypy .
```

Use only the command for the tool selected by the project. Prefer `ty` when the
project has not selected a type checker and its supported Python version is
compatible.

### 4. Run configured architecture checks

If the project defines import-boundary or architecture validation, run it as part
of linting. For example:

```bash
uv run lint-imports
```

Do not weaken architecture contracts to make the check pass.

### 5. Verify and report the result

After fixing any failures, re-run all project-configured checks. Report the
commands and targets used, whether each check passed, and any check that could not
run with the reason.

## When linting or type checking fails

- Read the `ruff check` output carefully. Each violation includes a rule code,
  file path, and line number. Fix the underlying code rather than adding `# noqa`
  comments unless the suppression is explicitly justified.
- Do not disable lint rules to silence violations. Prefer refactoring the code to
  satisfy the rule.
- Read type-checker errors and fix the annotations or logic that caused them. Use
  the selected tool's narrowly scoped suppression syntax only at genuine untyped
  boundaries, and document the reason.
- If a type error reflects a design issue, such as a wrong return type or missing
  protocol method, fix the design rather than suppressing the error.
- Read architecture-check failures as dependency-boundary violations. Fix the
  import direction or ownership issue rather than deleting or loosening a
  contract without an explicit architectural decision.
