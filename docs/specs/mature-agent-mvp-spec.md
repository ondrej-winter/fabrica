# Spec: Mature Agent MVP

## Status

- State: Draft — unconfirmed.
- Implementation status: Not implemented. This specification extracts a narrow MVP
  from `docs/ideas/mature-agent-product-roadmap.md`; it does not modify accepted
  Version 1 runtime or coding-agent-session contracts.
- Accepted by: Not yet accepted.
- Accepted on: Not applicable.
- Revision: Revised from confirmed product-policy interview decisions on September
  11, 2026.
- Acceptance basis: The MVP boundaries below reflect confirmed user decisions, but
  a maintainer has not formally accepted this canonical specification for
  implementation.
- Supersedes: The initial draft revision dated September 11, 2026.

This is the proposed canonical source of truth for the mature-agent MVP. It must
remain a draft until a maintainer formally accepts it. The user-confirmed capture
policy intentionally differs from the roadmap's original redaction proposal:
session records are complete, unredacted, and sensitive local artifacts.

## Objective

Define the smallest maturity increment for Fabrica's accepted terminal-hosted,
workspace-scoped coding-agent session. The MVP must let an individual local
developer retain complete session evidence, inspect or export it, and resume an
interrupted session quickly when workspace context is unchanged—or safely replan
when it is not—without expanding existing tool authority or overstating execution
containment.

## Current Context

- `docs/specs/coding-agent-session-spec.md` owns the accepted Version 1 terminal
  session composition, workspace scope, explicit approvals, and default tool
  exposure.
- `docs/specs/agent-runtime-spec.md` owns the provider-neutral tool-loop contract.
- Existing patch and command tools retain their own approval, recovery,
  containment, and execution contracts; this MVP must not weaken them.
- Default tests and CI are deterministic, offline, and credential-free. Opt-in
  live Codex validation remains separate.
- The source roadmap recommends durable, observable, measurable, and contained
  operation before broader autonomy or new integrations. Where this draft differs
  from its redaction recommendation, the confirmed product-policy decisions in
  this draft take precedence.

## Scope

### In Scope

- Complete, append-only, unredacted, unbounded session-event records and durable
  checkpoints in workspace-local `.fabrica/`.
- Persisted session states: `running`, `waiting_for_user`,
  `waiting_for_approval`, `interrupted`, `completed`, `failed`, and
  `stale_context`.
- Terminal workflows to start a session and list, inspect, export, delete, and
  resume a persisted session.
- Workspace-fingerprint comparison for a normal resume path and a mandatory
  replan path when the fingerprint differs.
- Optional Gitignore-style `.fabricaignore` patterns that exclude user-selected
  workspace paths from checkpoint fingerprints.
- A versioned deterministic offline evaluation corpus that initially reports
  results without blocking changes.
- Complete local audit and diagnostic evidence derived from durable session
  records, without external telemetry.
- A threat model and documented policy-only execution-isolation posture for the
  supported local product configuration.

### Out of Scope

- Enabling public web access, Git mutation, or Agent Skill scripts by default.
- Replacing action-specific approvals with persistent or session-wide approval.
- External telemetry, hosted storage, automatic session upload, automatic
  redaction, automatic retention cleanup, or Fabrica-managed filesystem
  permissions for `.fabrica/`.
- A VS Code extension, browser host, daemon, remote service, multi-user host, or
  reconnectable remote-session protocol.
- Mandatory live-provider evaluation in default local checks or CI.
- Stronger sandbox implementation or a sandbox-containment guarantee.
- Context compaction, long-task cache behavior, and host-strategy selection beyond
  the terminal workflow.

## Requirements

- R1: Fabrica must persist a complete append-only event stream and durable
  checkpoints for each terminal coding-agent session under the selected
  workspace's `.fabrica/` directory. Records must retain model prompts and
  responses, tool calls and results, command and patch text, approvals, user
  questions and answers, errors, final outcomes, and session state transitions.
  The MVP must not automatically redact, truncate, size-limit, expire, or upload
  this content.
  Basis: Confirmed product-policy decision on September 11, 2026.
- R2: `.fabrica/` and all session exports must be documented and presented as
  highly sensitive local data that can contain secrets and repository content.
  Fabrica must retain session records until explicit user deletion and provide
  terminal workflows to list, inspect, export, and delete them. Fabrica must warn
  visibly when `.fabrica/` is not Git-ignored, document the required ignore entry,
  and never edit `.gitignore` automatically.
  Basis: Confirmed product-policy decision on September 11, 2026.
- R3: Each resumable checkpoint must include a workspace fingerprint. The
  fingerprint must exclude `.fabrica/`, `.git/`, and paths matched by an optional
  Gitignore-style `.fabricaignore`; by default, no other paths are excluded.
  Basis: Confirmed product-policy decision on September 11, 2026.
- R4: On an explicit resume request, Fabrica must compare the current fingerprint
  with the checkpoint fingerprint. A match must take the normal resume path. A
  difference must transition the session to `stale_context` and require replan.
  Basis: Confirmed product-policy decision on September 11, 2026.
- R5: In `stale_context`, Fabrica must preserve history but programmatically block
  side-effecting tool calls until a successful fresh workspace inspection has
  occurred, an updated user-visible plan/intent summary has been displayed, and
  the user has explicitly acknowledged that summary. After acknowledgement, every
  side effect remains subject to current tool policy and its normal separate
  action-specific approval flow.
  Basis: Confirmed product-policy decision on September 11, 2026.
- R6: Stored events, checkpoints, refreshed-plan acknowledgement, and historical
  approvals must never silently replay a side effect or authorize a new action.
  Existing accepted command and patch approval contracts remain authoritative.
  Basis: Confirmed product-policy decision and accepted Version 1 contracts.
- R7: The MVP must introduce a versioned deterministic offline evaluation corpus
  covering inspection, scoped edits, validation, approval denials, cancellation,
  resume with matching and mismatched fingerprints, replan acknowledgement,
  malicious-repository or prompt-injection cases, and recovery. It must report
  results but must not initially block changes or releases. A future maintainer
  may separately decide to make it a release gate.
  Basis: Confirmed product-policy decision on September 11, 2026.
- R8: Optional live-model evaluation must use disposable workspaces and remain
  separate from the deterministic, offline, credential-free default quality gate.
  Basis: Existing accepted Version 1 validation contract.
- R9: Before authority expansion, Fabrica must document a threat model and its
  policy-only execution-isolation posture. It must state that supported workspace
  and tool policies are enforced where implemented, while the local operating
  system and user-process privileges remain the effective isolation boundary. It
  must make no sandbox-containment guarantee. The threat model must address
  malicious repository contents and scripts, prompt injection, secret
  exfiltration, symlink and concurrent-filesystem attacks, untrusted Skills, and
  network access.
  Basis: Confirmed product-policy decision on September 11, 2026.
- R10: The MVP must preserve accepted workspace scope, tool-specific contracts,
  explicit action-specific approval, provider isolation, and offline default
  validation from the Version 1 specifications.
  Basis: Existing accepted runtime and coding-agent-session specifications.

## Binding Constraints and Execution Boundaries

- Always: Keep durable records local to the selected workspace and make their
  sensitivity clear to the user. Treat `.fabrica/` and its exports as potentially
  containing secrets, private source, prompts, responses, commands, patches, and
  tool output.
- Always: Retain every captured byte until explicit user deletion. Session record
  handling, filesystem permissions, available disk space, and export distribution
  remain the user's responsibility.
- Always: On a fingerprint mismatch, enforce replan before any side effect can be
  proposed; apply the existing action-specific approval boundary afterward.
- Always: Preserve workspace scope, existing tool-specific safety contracts,
  provider isolation, and deterministic offline default validation.
- Ask first: Select durable-record encoding or migration policy, choose the
  fingerprint algorithm, add dependencies, or alter accepted CLI, tool, approval,
  or workspace contracts.
- Never: Modify `.gitignore` automatically; silently replay a side effect; reuse a
  historical approval as authorization; upload session data automatically; claim
  technical sandbox containment; or make live-provider evaluation mandatory in
  default CI.

## Acceptance Checks

| ID  | Requirement | Conditions and action                                                                                                                                        | Expected observable result                                                                                                                                                          | Verification method                                                                                      |
| --- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| AC1 | R1, R2      | Run sessions that complete, fail, are interrupted, wait for user input, and wait for approval; inspect and export each retained record.                      | `.fabrica/` contains ordered full event history and checkpoints, including sensitive content when present; records remain until explicit deletion; exports retain the same content. | Focused unit and integration tests plus fixture inspection.                                              |
| AC2 | R2          | Start a persistent session in workspaces with and without `.fabrica/` ignored by Git.                                                                        | Fabrica never edits `.gitignore`; it visibly warns when `.fabrica/` is not ignored and documentation specifies the required ignore entry.                                           | Deterministic CLI tests and documentation review.                                                        |
| AC3 | R3, R4      | Resume after unchanged workspaces, changes under `.fabrica/` or `.git/`, and changes under normal or `.fabricaignore`-matched workspace paths.               | Matching fingerprints use normal resume; excluded-path changes do not trigger replan; other changes transition to `stale_context`.                                                  | Deterministic checkpoint and CLI/composition tests.                                                      |
| AC4 | R5, R6      | Resume a mismatched session and attempt side-effecting calls before and after fresh inspection, plan display, acknowledgement, and separate action approval. | Side effects are blocked until the replan sequence completes; refreshed-plan acknowledgement does not replace action-specific approval; prior approvals are never reused.           | Deterministic runtime and terminal-host tests.                                                           |
| AC5 | R7, R8      | Execute the versioned offline corpus and separately execute any opt-in live-model suite in disposable workspaces.                                            | Offline scenarios report deterministic outcomes without credentials or network access and do not gate changes; live evaluation is never part of the default gate.                   | Corpus runner output, CI configuration review, and tests.                                                |
| AC6 | R9          | Review the threat model and supported policy-only isolation statement before authority expansion.                                                            | Documentation identifies covered threats, policy enforcement boundaries, local OS/process residual risk, and the absence of a sandbox-containment guarantee.                        | Documentation review and required ADR for any future storage-architecture or isolation-guarantee change. |
| AC7 | R10         | Run applicable existing regression and boundary suites.                                                                                                      | Workspace containment, explicit approvals, provider isolation, and offline-quality-gate behavior remain intact.                                                                     | Focused regression tests followed by the configured local quality gate.                                  |

## Success Criteria

- A developer can retain, inspect, export, and explicitly delete complete local
  session evidence for their own workspace.
- An unchanged workspace resumes without unnecessary replan, while a changed
  non-excluded workspace requires inspection, plan refresh, acknowledgement, and
  separately approved side effects.
- No session history, checkpoint, plan acknowledgement, or prior approval becomes
  implicit authority for a new effect.
- The project has repeatable offline behavior and safety evidence without making
  the initial corpus an uncalibrated release gate.
- Fabrica clearly states that `.fabrica/` is sensitive local data and that its
  execution-isolation guarantee is policy-only.

## Assumptions

- Individual local developers value complete local evidence enough to accept the
  confidentiality and disk-consumption risks of unredacted, unbounded storage.
- Users will configure filesystem permissions, Git ignores, and disk management
  appropriately for `.fabrica/`.
- A compact deterministic task corpus provides useful reporting evidence before a
  maintainer decides whether to make it release-gating.
- Optional `.fabricaignore` patterns are used narrowly; users accept that changes
  beneath ignored paths do not trigger replan.

## Resolved Product-Policy Decisions

| Decision                             | Confirmed outcome                                                                                                                                                       | Basis                                                  |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Durable record content and retention | Capture all session content, including sensitive content and secrets, without automatic redaction, bounds, expiry, or upload; retain until user deletion.               | User-confirmed interview decision, September 11, 2026. |
| Storage and lifecycle                | Store records in workspace-local `.fabrica/`; support list, inspect, export, and delete; warn but never edit `.gitignore`.                                              | User-confirmed interview decision, September 11, 2026. |
| Resume validation                    | Compare checkpoint and current workspace fingerprints; exclude `.fabrica/`, `.git/`, and optional `.fabricaignore` patterns only.                                       | User-confirmed interview decision, September 11, 2026. |
| Mismatch handling                    | Enter `stale_context` replan; require fresh inspection, displayed refreshed plan, and user acknowledgement before proposing a side effect for separate normal approval. | User-confirmed interview decision, September 11, 2026. |
| Evaluation promotion                 | Start deterministic evaluation as reporting-only; require a separate future maintainer decision to make it gating.                                                      | User-confirmed interview decision, September 11, 2026. |
| Execution isolation                  | Make a policy-only statement; do not make a sandbox-containment guarantee.                                                                                              | User-confirmed interview decision, September 11, 2026. |

## Open Questions

No product-policy decision blocks a derived implementation plan. The following
implementation design choices must preserve the requirements above and require
maintainer review during planning:

| Question                                                                                        | Impact                                                                         | Owner      | Resolution                           |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------- | ------------------------------------ |
| What durable-record encoding, schema versioning, and migration policy should `.fabrica/` use?   | Determines implementation compatibility and recovery behavior.                 | Maintainer | Deferred to implementation planning. |
| What deterministic fingerprint algorithm and path-normalization rules should implement R3?      | Determines reproducibility, performance, and precise matching semantics.       | Maintainer | Deferred to implementation planning. |
| What terminal command names and export-bundle representation best fit existing CLI conventions? | Determines the user-facing interface without changing the required lifecycle.  | Maintainer | Deferred to implementation planning. |
| Which initial corpus fixtures and reporting fields best demonstrate R7?                         | Determines initial evaluation coverage while preserving reporting-only status. | Maintainer | Deferred to implementation planning. |

## Acceptance and Planning Gate

This draft has resolved its product-policy decisions through a confirmed interview,
but it is not formally accepted. A maintainer must accept this specification before
implementation planning begins. Persistent session-event storage is an
architectural decision and requires an ADR before implementation. Any future change
to the policy-only isolation claim, session-data sensitivity boundary, or accepted
Version 1 tool, approval, workspace, and offline-validation contracts requires a
material specification revision and, where applicable, an ADR.

## Revision and Handoff Notes

- September 11, 2026: Revised the initial roadmap extraction with confirmed
  product-policy decisions for full local capture, `.fabricaignore` fingerprint
  exclusions, normal resume, mandatory mismatch replan, reporting-only evaluation,
  and policy-only execution isolation.
- The roadmap remains an idea record. This draft adds no runtime authority and
  does not authorize implementation.
- Next authorized step: formal maintainer acceptance, then an ADR for persistent
  session storage and a derived implementation plan.
