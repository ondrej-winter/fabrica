# Idea: Mature Agent Product Roadmap

## Status

Not accepted for implementation. This note records a possible direction for maturing Fabrica beyond its implemented Version 1 terminal-hosted, workspace-scoped coding-agent session. It is not a product guarantee, committed roadmap, or authorization to expand the default tool set.

Recorded: September 10, 2026.

## Opportunity

How might Fabrica become a dependable long-running coding-agent product for local developers without weakening explicit workspace scope, per-action approval, containment, privacy, and provider-isolation boundaries?

Fabrica already has a strong safety-conscious core: typed tool-loop contracts, bounded workspace tools, supervised command execution, journaled and approval-gated patch mutation, terminal interaction, deterministic offline coverage, and release automation. The principal gap is not basic tool capability. It is the product and operational layer needed to make longer agent work dependable, measurable, inspectable, and safely extensible.

## Recommended Direction

Prioritize durable, observable, measurable, and contained agent operation before adding broader autonomy or integrations. The first maturity increment should make terminal sessions resumable and auditable, establish a repeatable evaluation baseline, and document and enforce the real level of execution isolation.

New authority such as public web access, Git mutation, Agent Skill scripts, remote hosts, or MCP should be admitted only when it inherits the same session, policy, approval, audit, evaluation, and redaction guarantees.

## Candidate Workstreams

### Durable sessions and safe resume

Persist a redacted append-only event stream and checkpoints for model turns, tool calls and results, approvals, questions and answers, errors, and final outcomes. Add explicit states such as running, waiting for user, waiting for approval, interrupted, completed, and failed.

Resumption must revalidate workspace state and re-enter current policy and approval boundaries. It must never silently replay side effects. Candidate workflows include agent start, status, resume, and history.

### Agent evaluations and regression control

Create a versioned deterministic task corpus covering inspection, scoped edits, validation, denials, cancellation, changed-workspace failures, prompt-injection or malicious-repository cases, and recovery. Keep optional live-model evaluation in disposable workspaces separate from offline CI.

Track task outcome and correctness, validation pass rate, tool-call efficiency, approval-denial recovery, latency, token and cost evidence, and safety-policy violations. Establish regression thresholds for deterministic scenarios.

### Observability and audit evidence

Introduce a session-correlated, privacy-safe event sink. Start with local structured audit records before selecting an external telemetry backend. Propagate correlation through model turns, commands, approvals, subprocesses, and patch lifecycle events.

The event taxonomy should capture durations, dispositions, retries, rate limits, mutation outcomes, and policy decisions without retaining secrets, raw provider payloads, or unbounded repository content.

### Execution isolation and policy administration

Document a threat model and explicit sandbox guarantee levels before expanding authority. Cover malicious repository contents and scripts, prompt injection, secret exfiltration, symlink and concurrent-filesystem attacks, untrusted Skills, and network access.

Move beyond permissive host-preflight assumptions where needed with documented platform-specific containment and explicit versioned policy profiles such as read-only, inspect-and-test, edit-with-approval, and restricted-network. Approval remains distinct from technical containment.

### Human supervision and long-task management

Add a session timeline, current-operation visibility, strong cancellation controls, inspectable prior evidence, and readable unified patch diffs. Consider a two-phase investigate-and-propose-plan workflow followed by execution approval, while retaining separate patch and command approvals.

Add explicit context budgets, provenance-preserving compaction, task progress state, and repository indexing or caching with clear invalidation semantics.

### Product configuration and host strategy

Define supported configuration for model selection, reasoning effort, runtime budgets, policy profiles, and local session and audit storage. Document platform guarantees, persisted-record migrations, diagnostic bundles, and user onboarding.

Only after the session, policy, and audit foundations exist, choose an intentional next host: richer CLI, VS Code, MCP, embedded SDK, or remote service. Any host must preserve workspace scope, approval semantics, event model, and redaction guarantees.

## Suggested Sequencing

1. Define the redacted session-event schema and durable checkpoint model.
2. Build session persistence and safe resume, status, and history workflows.
3. Add deterministic agent evaluations and quality baselines.
4. Export correlated local audit evidence.
5. Improve plan-review and patch-approval user experience.
6. Record the threat model and sandbox guarantee levels.
7. Add context-budget and compaction behavior for long tasks.
8. Only then consider stronger sandboxing and carefully scoped Git, web, Skill, or external-host capability.

## Key Assumptions to Validate

- [ ] Developers will resume interrupted coding sessions often enough to justify durable transcript and checkpoint complexity. Test through dogfooding and an opt-in session-history prototype.
- [ ] A compact deterministic task corpus predicts meaningful real coding-session quality. Compare corpus scores with observed success and failure reports.
- [ ] Local structured audit records provide enough debugging value before an external telemetry backend is introduced. Test against real opt-in failure triage.
- [ ] Stronger technical containment can work on supported macOS and Linux platforms without making local development impractical. Validate with a threat-model spike and a platform guarantee matrix.
- [ ] Users prefer explicit plan review for meaningful changes over a fully linear tool loop. Test terminal workflow prototypes.

## Not Doing and Why

- Immediately enabling web, Git mutation, or Skill scripts by default: this expands authority before durable audit, evaluation, and sandbox guarantees exist.
- Building VS Code, browser, daemon, or multi-user hosting first: current Version 1 intentionally proves terminal composition first, and later hosts should reuse stable session and policy contracts.
- Treating persistent session-wide approval as a shortcut: it conflicts with the action-specific approval model.
- Making live-provider benchmarks mandatory in CI: default quality gates must remain deterministic, offline, and credential-free.
- Replacing tool-specific safety contracts with a generic agent permission: explicit tool boundaries are a Fabrica strength.

## Open Questions

- Which user segment defines the first maturity target: individual local power users, teams sharing reproducible session evidence, or host integrators?
- Which session events are durable product records versus transient diagnostics, and what retention and redaction policy governs them?
- What sandbox guarantee can Fabrica truthfully make on macOS and Linux?
- Which evaluation tasks and graders best represent intended coding workflows?
- Is the next strategic host a richer terminal workflow, VS Code, MCP, an embedded SDK, or something else?

## Promotion Criteria

Before a workstream becomes an accepted specification, select a narrow target user and success measure, resolve material policy and storage assumptions, define compatibility and privacy boundaries, and create a focused specification with deterministic acceptance scenarios. Architectural changes such as persistent event storage, sandbox guarantees, or external-host protocol support require an ADR.
