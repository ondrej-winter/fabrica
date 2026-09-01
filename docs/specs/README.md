# Specs

This directory contains durable product and architecture specifications organized
by concern rather than by the original end-to-end idea that introduced the work.

Use these specs to understand current intent, safety boundaries, implementation
ownership, validation expectations, and preserved historical decisions.

## Specification governance

Every `*-spec.md` is a canonical requirements artifact and follows the local
`spec-driven-development` template. Each specification must record its status,
acceptance evidence, revision, assumptions, desired behavior, explicit scope,
validation, structure, constraints, execution boundaries, success criteria, and
open-question ownership.

- **Accepted** specifications may be handed to planning. A derived plan belongs
  under `docs/plans/` by default and must not redefine the specification.
- **Draft — unconfirmed** specifications are useful design records but are not
  implementation-ready. Resolve blocking questions and record a human acceptance
  in the spec's **Status** section before planning.
- Do not infer acceptance from implementation, a merged change, or the absence
  of questions. Record the accepting person or role and date explicitly.
- Update and re-confirm a specification when its accepted objective, scope,
  behavior, constraints, boundaries, or success criteria changes materially.

Existing detailed sections such as **Non-goals**, **Boundaries**, and **Resolved
decisions** remain part of their specification. The template's normalized
governance sections make their planning and acceptance state explicit rather than
replacing those technical details.

## Current specs

- `agent-runtime-spec.md` defines the local Python agent runtime direction and its
  provider-agnostic runtime boundaries.
- `codex-transport-spec.md` defines the subscription-backed Codex transport support
  path, private-backend constraints, credential safety, and opt-in live
  validation rules.
- `model-usage-and-cost-evidence-spec.md` defines provider-neutral usage and pricing
  evidence for model-call results.
- `tools-git-workflow-tools-spec.md` defines git-related developer workflow tools and
  adapters, including read-only git context, approved commit creation, and
  explicitly composed pre-commit execution.
- `commit-workflows-spec.md` defines developer-facing commit workflows, including the
  read-only `fabrica commit-message` preview and the explicitly confirmed
  mutating `fabrica commit` flow.
- `tools-read-files-tool-spec.md` defines the read-only workspace file inspection primitive
  for model-callable coding-agent workflows.
- `tools-search-codebase-tool-spec.md` defines the read-only textual regex discovery
  primitive for locating relevant workspace file contents before reading files.
- `tools-apply-patch-tool-spec.md` defines the context-based workspace file mutation
  primitive for model-callable coding-agent workflows.
- `tools-run-commands-tool-spec.md` defines the accepted non-interactive process
  execution primitive for coding-agent verification and project-tooling workflows,
  including parallel-by-default batching, per-command result isolation, bounded
  separate-stream output, workspace-contained context, and host-managed
  default-deny safety policy.
- `tools-fetch-web-content-tool-spec.md` defines the implemented read-only public-web
  retrieval primitive for known URLs, including SSRF-safe destination and redirect
  validation, bounded textual-content extraction, structured result metadata, and
  explicit untrusted-content handling.

## Naming convention

- General specifications must use `<name>-spec.md`.
- Tool-owned specifications must use `tools-<tool-name>-tool-spec.md`, for
  example `tools-read-files-tool-spec.md`.

## Placement guidance

- Add a new spec only when the work introduces a durable concern that does not
  fit an existing spec.
- Prefer adding a section to an existing concern spec when a new workflow extends
  the same product or architectural surface.
- Keep provider-specific volatility in provider-owned specs, such as
  `codex-transport-spec.md`, instead of hiding it inside generic runtime or usage
  specifications.
- Keep mutating workflows separate from read-only tool or preview concerns unless
  one spec explicitly owns the relevant safety categories.
