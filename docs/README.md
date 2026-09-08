# Project documentation

This directory contains durable project documentation and current reference notes.

## Documentation lifecycle

- Temporary ideas and implementation plans should be deleted after promotion
  into a spec, implementation, or decision record.
- `specs/` and `adr/` are durable records. Keep them when they explain current
  behavior, historical context, or decisions that future work still needs to
  understand.
- Prefer a short status note over rewriting historical spec content when later
  implementation evidence changes an earlier assumption.

## Current map

### Architecture decision records

- `adr/README.md` indexes accepted architecture decisions.

### Future work

- `future-work/descriptor-rooted-search-helper.md` records the deferred
  native-helper option for restoring stronger supported-platform workspace-search containment
  without an external container runtime.

### Specs

- `specs/README.md` explains the concern-oriented spec taxonomy.
- `specs/agent-runtime-spec.md` defines the local Python agent runtime direction and
  its provider-agnostic boundaries.
- `specs/coding-agent-session-spec.md` defines the accepted, planned terminal-hosted
  workspace coding-agent session and its tool/approval composition contract.
- `specs/codex-transport-spec.md` defines the subscription-backed Codex transport
  support path and preserves private-backend errata.
- `specs/model-usage-and-cost-evidence-spec.md` defines the generic usage and pricing
  evidence model for model-call results.
- `specs/tools-git-workflow-tools-spec.md` defines git-related developer workflow tools and
  adapters, including read-only git context, approved commit creation, and
  explicitly composed pre-commit execution.
- `specs/commit-workflows-spec.md` defines read-only commit-message generation and the
  interactive `fabrica commit` workflow that creates commits only after explicit
  approval.
- `specs/tools-read-files-tool-spec.md` defines bounded workspace file inspection for
  model-callable coding-agent workflows.
- `specs/tools-search-codebase-tool-spec.md` defines read-only regex-based workspace source
  discovery for model-callable coding-agent workflows.
- `specs/tools-fetch-web-content-tool-spec.md` defines bounded, SSRF-safe public HTTPS
  retrieval for model-callable coding-agent workflows.
- `specs/tools-apply-patch-tool-spec.md` defines context-based workspace file mutation,
  including capability-gated POSIX production enablement, fail-closed unsupported
  environments, and its recovery contract.
- `specs/tools-skills-tool-spec.md` defines Version 1 model-callable Agent Skill
  activation, including canonical `SKILL.md` parsing, global/workspace snapshots,
  revision-bound trust, bounded activation content, and active-skill compaction.
