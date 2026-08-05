# Project documentation

This directory contains durable project documentation plus active planning notes.

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
- `observations/codex-runtime-viability-template.md` is the template for future
  redacted manual observations.

### Specs

- `specs/subscription-backed-python-agent-runtime-spec.md` defines the original
  transport spike target and preserves later errata.
- `specs/selected-skill-commit-message-spec.md` is historical MVP background for
  the first `commit-message` command surface.
- `specs/evidence-first-commit-message-generation-spec.md` defines the current
  multi-call evidence-first commit-message target.
- `specs/model-callable-staged-git-tools-spec.md` defines optional read-only
  staged git tools for explicit agent/tool-loop workflows.

### Active plans

- `plans/multi-call-evidence-first-commit-message-generation-plan.md` tracks the
  unfinished implementation plan for the current evidence-first commit-message
  architecture.
