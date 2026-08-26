# Specs

This directory contains durable product and architecture specifications organized
by concern rather than by the original end-to-end idea that introduced the work.

Use these specs to understand current intent, safety boundaries, implementation
ownership, validation expectations, and preserved historical decisions.

## Current specs

- `agent-runtime.md` defines the local Python agent runtime direction and its
  provider-agnostic runtime boundaries.
- `codex-transport.md` defines the subscription-backed Codex transport support
  path, private-backend constraints, credential safety, and opt-in live
  validation rules.
- `model-usage-and-cost-evidence.md` defines provider-neutral usage and pricing
  evidence for model-call results.
- `git-workflow-tools.md` defines git-related developer workflow tools and
  adapters, including read-only git context, approved commit creation, and
  explicitly composed pre-commit execution.
- `commit-workflows.md` defines developer-facing commit workflows, including the
  read-only `fabrica commit-message` preview and the explicitly confirmed
  mutating `fabrica commit` flow.
- `read-files-tool.md` defines the read-only workspace file inspection primitive
  for model-callable coding-agent workflows.
- `search-codebase-tool.md` defines the read-only textual regex discovery
  primitive for locating relevant workspace file contents before reading files.
- `apply-patch-tool.md` defines the context-based workspace file mutation
  primitive for model-callable coding-agent workflows.

## Placement guidance

- Add a new spec only when the work introduces a durable concern that does not
  fit an existing spec.
- Prefer adding a section to an existing concern spec when a new workflow extends
  the same product or architectural surface.
- Keep provider-specific volatility in provider-owned specs, such as
  `codex-transport.md`, instead of hiding it inside generic runtime or usage
  specifications.
- Keep mutating workflows separate from read-only tool or preview concerns unless
  one spec explicitly owns the relevant safety categories.
