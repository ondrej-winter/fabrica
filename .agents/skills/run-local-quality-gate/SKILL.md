---
name: run-local-quality-gate
description: Discover and run the project's local formatting, linting, static analysis, test, and build checks before handoff.
metadata:
  version: "1.2.1"
  dependencies:
    tools:
      - name: shell
        purpose: Discover and run the project's configured quality commands.
        required: true
    skills: []
---

# Run Local Quality Gate

Use this skill when work is ready for validation or when the user asks to run the
project's local quality checks. Discover and use the commands already defined by
the project rather than inventing a new toolchain.

## Steps

### 1. Discover the project commands

Inspect the repository for documented or configured checks, such as:

- README or contributor instructions
- package, build, task, or make files
- continuous integration configuration
- pre-commit or hook configuration
- test, lint, format, type-check, static-analysis, or build scripts
- documented prerequisite or environment setup commands

Prefer documented aggregate commands when they exist. Also identify narrower
checks for the files or behavior changed so iteration can start with fast,
relevant feedback before expanding to the full gate.

For Python projects, use the project's configured `ty` command for type checking
when present. If type checking is required but the project has not selected a
tool, prefer `ty` rather than `mypy`, and expose it through the project's normal
package, task, or environment runner instead of assuming a global installation.
Do not silently replace an established project command as part of unrelated work;
report the mismatch and keep migration explicit.

Do not install dependencies, update lockfiles, or modify the runtime environment
unless the project documents that step as part of the local gate or the user has
approved it. If required setup is unavailable or out of scope, report the
limitation before running dependent checks.

### 2. Decide the validation sequence

Use a sequence that gives fast feedback and avoids hiding failures. A typical
order is:

1. formatting or safe auto-fixes
2. linting or style checks
3. type checking or static analysis
4. focused tests for touched behavior
5. broader test suite
6. build, packaging, documentation, or integration checks when relevant

If a project documents a different required order, follow the project order.
Prefer non-interactive commands and avoid flags that would open pagers, watchers,
editors, or prompts unless the user explicitly requests an interactive workflow.

### 3. Run safe auto-fixes deliberately

Only run auto-fix commands that are established in the project. After auto-fixes,
inspect the resulting changes and ensure they are related to the task. Do not
run broad cleanup commands when a narrower project-approved command validates the
touched area.

Do not use ad hoc flags to bypass the project's configured rules in the final
validation run.

### 4. Stop on failures and fix root causes

When a step fails:

- read the failure output before rerunning
- identify whether the failure is caused by the current change or existing drift
- fix the underlying issue when it is in scope
- rerun the failing command after the fix
- avoid moving to later checks when earlier failures invalidate the result

If a failure is unrelated or cannot be fixed within scope, report it clearly with
the command and relevant output.

### 5. Run the final gate before handoff

Before handoff, run the broadest practical project-approved quality gate after
any focused checks have passed. If the full gate is expensive or unavailable,
run the strongest available subset and state the limitation.

### 6. Summarize validation results

Record the commands that passed, failed, or were skipped. Include enough detail
for the next maintainer to reproduce the result.

## Output checklist

- project-defined commands were discovered before running checks
- validation commands were non-interactive or any interactive requirement was explained
- safe auto-fixes were inspected when run
- failures were fixed or explicitly reported
- final validation command set is documented
- no checks were bypassed with unsupported flags in the final run
