# Project documentation

This directory contains durable project documentation and current reference notes.

## Documentation lifecycle

- `ideas/` is temporary. Delete an idea after it is promoted into a spec,
  implementation, or decision record.
- `plans/` is temporary. Delete a plan after the planned work is complete.
- `specs/`, `adr/`, and dated `observations/` are durable records. Keep them when
  they explain current behavior, historical context, or decisions that future work
  still needs to understand.
- Prefer a short status note over rewriting historical spec content when later
  implementation evidence changes an earlier assumption.

## Current map

### Architecture decisions

- `adr/0001-experimental-agent-skill-script-execution.md` records the accepted
  boundary for experimental selected Agent Skill script execution.

### Observations and viability records

- `observations/README.md` is the canonical guide for redacted runtime viability
  observations and source-comparison notes.
- `observations/2026-08-01-codex-runtime-viability-decision.md` records the
  current subscription-backed Codex runtime viability label.
- `observations/2026-08-01-redacted-live-evidence-collection.md` records the
  dated repeated-session live validation evidence behind that label.

### Specs

- `specs/python-agent-runtime-spec.md` defines the local Python agent runtime
  direction and its provider-agnostic boundaries.
- `specs/codex-transport-support-spec.md` defines the subscription-backed Codex
  transport support path and preserves private-backend errata.
- `specs/evidence-first-commit-message-generation-spec.md` defines the current
  multi-call evidence-first commit-message target.
- `specs/interactive-confirmed-commit-flow-spec.md` defines the interactive
  `fabrica commit` workflow that creates commits only after explicit approval.
- `specs/provider-agnostic-usage-cost-evidence-spec.md` defines the generic usage
  and pricing evidence model for model-call results.
- `specs/read-only-git-context-tools-spec.md` defines broader read-only git
  context capabilities for worktree, staged, commit-history, and ref/range
  inspection.
