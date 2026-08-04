# PR and commit hygiene

Use these rules to keep reviews fast, changesets focused, and CI reliable.

## PR size limits

- **Should** keep PRs under about 400 changed lines when practical.
- **Must** split large refactors into sequenced PRs unless explicitly approved.
- **Should** include a concise summary and test evidence in the PR description.
- **Should** call out rollout, migration, rollback, or feature-flag considerations when operational risk is meaningful.

## Commit message style

- **Must** use imperative, present tense (e.g., "Add user repository adapter").
- **Should** include a scope prefix when useful (e.g., `docs:`, `tests:`, `adapters:`).
- **Must** keep commits focused; avoid mixing unrelated changes.
- **Must not** leave `WIP`, `fixup!`, or `squash!` commits in shared history unless the team workflow explicitly relies on autosquash later.

## Review checklist

- **Must** verify boundary compliance (ports/adapters separation).
- **Must** ensure tests are updated for behavior changes.
- **Should** confirm docs are updated when configuration or usage changes.
- **Should** check for logging/observability coverage on new I/O paths.
- **Should** verify dependency and lockfile changes are intentional and explained.
- **Must** check that secrets, credentials, and unnecessary sensitive artifacts are not introduced in the change set.

## CI expectations

- **Must** run the local quality gate before handoff (see `011-tooling-and-ci.md`).
- **Must** fix CI failures at the root cause instead of bypassing checks.
