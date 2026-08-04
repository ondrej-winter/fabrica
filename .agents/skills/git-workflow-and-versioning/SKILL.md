---
name: git-workflow-and-versioning
description: Use version control intentionally with small changes, clear branches, atomic commits, safe history operations, useful summaries, and validation before merge or handoff.
metadata:
  version: "1.2.0"
  dependencies:
    tools:
      - name: git
        purpose: Inspect repository status, diffs, branches, history, remotes, tags, and commit metadata.
        required: true
    skills: []
---

# Git Workflow and Versioning

Use this skill when organizing changes in version control, preparing commits,
working across branches, resolving conflicts, or summarizing work for review. The
goal is to keep changes reviewable, reversible, and easy to understand later.

This skill assumes Git concepts but does not require a specific hosting provider,
branching model, commit convention, CI platform, or package manager.

## When to use this skill

Use this skill when:

- making a code, documentation, configuration, or asset change
- deciding how to split work into commits or branches
- preparing a review or handoff summary
- checking whether a diff contains unrelated changes
- resolving conflicts or coordinating parallel work
- using history to debug or audit behavior

## Principles

- Keep changes small and logical.
- Separate behavior changes from mechanical formatting or generated output.
- Commit only after relevant validation passes.
- Treat commit messages as durable documentation.
- Avoid destructive history operations unless explicitly requested and scoped.
- Do not create commits, tags, branches, or pushes unless the user requested them
  or the project workflow clearly requires them.
- Prefer clear recovery points over large uncommitted work.

## Steps

### 1. Inspect repository state

Before editing, committing, or handing off, check the working tree and understand
what changed.

Useful commands include:

```sh
git --no-pager status --short
git --no-pager diff --stat
git --no-pager diff
```

Use non-interactive Git commands and disable pagers when possible.

Distinguish staged, unstaged, and untracked changes. If the working tree already
contains changes you did not make, preserve them unless the user explicitly asks
you to modify, stage, discard, or commit them.

### 2. Keep work scoped

Each change should do one logical thing. Split work when it combines:

- feature behavior and refactoring
- formatting and behavior
- generated output and hand-written changes
- unrelated modules or domains
- dependency updates and product behavior

Small incidental cleanups can be acceptable when they are local, obvious, and do
not obscure the requested change.

### 3. Use branches as isolation when needed

Use the project’s branching model. Short-lived branches are useful for isolating
work, but the exact branch naming convention should match the repository.

Good branch names are short, descriptive, and scoped, such as:

```text
feature/<short-description>
fix/<short-description>
docs/<short-description>
refactor/<short-description>
```

Prefer feature flags, staged rollout, or small mergeable slices over long-lived
branches that diverge for weeks.

### 4. Commit atomic increments

Create commits that are self-contained and meaningful. A reviewer should be able
to understand and, if needed, revert one commit without unraveling unrelated work.

Before each commit:

```sh
git --no-pager diff --staged
<relevant_validation_command>
```

Do not commit secrets, local environment files, build artifacts, or unrelated
temporary files.

### 5. Write useful messages

Follow the project’s commit-message convention when one exists. Otherwise use a
short imperative summary and an optional body explaining why.

Portable shape:

```text
<type-or-area>: <short summary>

<why this changed, important context, validation, or trade-offs>
```

Avoid messages such as `fix`, `update`, `misc`, or `changes` because they do not
help future maintainers understand history.

### 6. Use history safely for debugging

Git history can help locate regressions and understand context.

Useful read-only commands include:

```sh
git --no-pager log --oneline -n 20
git --no-pager diff <from_ref>..<to_ref>
git --no-pager blame <path>
git --no-pager log --grep=<keyword> --oneline
```

Use destructive commands such as reset, clean, rebase, or force-push only when the
target is explicit and the user has approved the risk.

### 7. Resolve conflicts deliberately

Before resolving a conflict, inspect both sides and determine the intended final
behavior. Do not automatically choose all of one side unless that outcome is
explicitly correct.

For each conflicted file:

1. identify the purpose of the incoming and current changes
2. combine compatible changes or choose the behavior required by the task
3. remove conflict markers and inspect the resulting diff
4. run validation that covers the affected behavior
5. stage the file only after confirming the resolution is complete

If intent is unclear or the conflict involves changes owned by someone else,
pause and ask for context rather than guessing. Do not abort, continue, or commit
a merge or rebase unless the operation is understood and within the requested
scope.

### 8. Summarize changes for review

Before handoff, provide:

```text
Changed:
- <path>: <what changed and why>

Not changed:
- <related scope intentionally left alone>

Validation:
- <command or manual check>: <result>

Risks or follow-ups:
- <none or specific item>
```

Call out assumptions, skipped validation, and potential follow-up work rather than
silently expanding scope.

## Parallel work and worktrees

When multiple streams of work need separate working directories, Git worktrees can
be useful. Use them only when the project workflow supports them and the target
paths are explicit.

Example shape:

```sh
git worktree add <worktree_path> <branch_name>
```

Clean up worktrees after merge or abandonment using the project’s normal Git
workflow.

## Red flags

- large uncommitted work accumulates without checkpoints
- commit mixes unrelated concerns
- formatting-only churn hides behavior changes
- generated files are committed without project convention requiring them
- local secrets or environment files appear in the diff
- branch diverges for a long time without integration
- history is rewritten on shared branches without explicit approval
- handoff omits validation evidence

## Output checklist

- working tree state was inspected
- change is scoped and reviewable
- commit or handoff summary explains why, not only what
- relevant validation passed or skipped validation is documented
- secrets and local artifacts are absent from the diff
- risky Git operations were avoided or explicitly approved
