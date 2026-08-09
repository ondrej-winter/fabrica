# Project documentation

This directory contains durable project documentation and current reference notes.

## Documentation lifecycle

- `ideas/` is temporary. Delete an idea after it is promoted into a spec,
  implementation, or decision record.
- `plans/` is temporary. Delete a plan after the planned work is complete.
- `specs/` and `adr/` are durable records. Keep them when they explain current
  behavior, historical context, or decisions that future work still needs to
  understand.
- Prefer a short status note over rewriting historical spec content when later
  implementation evidence changes an earlier assumption.

## Current map

### Specs

- `specs/README.md` explains the concern-oriented spec taxonomy.
- `specs/agent-runtime.md` defines the local Python agent runtime direction and
  its provider-agnostic boundaries.
- `specs/codex-transport.md` defines the subscription-backed Codex transport
  support path and preserves private-backend errata.
- `specs/model-usage-and-cost-evidence.md` defines the generic usage and pricing
  evidence model for model-call results.
- `specs/git-context-tools.md` defines broader read-only git context capabilities
  for worktree, staged, commit-history, and ref/range inspection.
- `specs/commit-workflows.md` defines read-only commit-message generation and the
  interactive `fabrica commit` workflow that creates commits only after explicit
  approval.
