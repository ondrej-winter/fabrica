# Spec: Mature Agent MVP

## Status

- State: Accepted.
- Implementation status: Not implemented. This specification extracts a narrow MVP
  from `docs/ideas/mature-agent-product-roadmap.md`; it does not modify accepted
  Version 1 runtime or coding-agent-session contracts.
- Accepted by: Maintainer.
- Accepted on: September 12, 2026.
- Revision: Accepted after product-policy interview confirmation on September 12, 2026.
- Acceptance basis: The maintainer explicitly confirmed the consolidated MVP
  intent and audit resolution as the basis for the persistent-storage ADR and
  derived implementation plan.
- Supersedes: The initial draft revision dated September 11, 2026.

This is the canonical source of truth for the accepted mature-agent MVP. The
accepted structured-session capture policy intentionally differs from the
roadmap's original redaction proposal: records are unredacted within the explicit
capture boundary below and are sensitive local artifacts.

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
  workspace's `.fabrica/` directory. Complete means the unredacted structured,
  model-visible session evidence: prompts, normalized model responses, tool calls
  and results, command and patch text, approvals, user questions and structured
  answers, errors, final outcomes, session metadata, and state transitions.
  Fabrica must never persist process environments, credentials, authentication
  headers, raw provider request or response wire payloads, or terminal keystrokes
  outside structured submitted answers. The MVP must not automatically redact,
  truncate, size-limit, expire, or upload captured evidence.
  Basis: Confirmed product-policy decision on September 12, 2026.
- R2: `.fabrica/` and all session exports must be documented and presented as
  highly sensitive local data that can contain secrets and repository content.
  Before the first persisted capture in a workspace, Fabrica must issue a visible
  sensitivity warning. Fabrica must retain session records indefinitely until
  explicit user deletion, provide terminal workflows to list, inspect, export, and
  delete them, and ensure deletion of a session removes only that session's
  records and checkpoints. Exports are user-managed copies outside Fabrica's
  lifecycle. Fabrica must warn visibly when `.fabrica/` is not Git-ignored,
  document the required ignore entry, and never edit `.gitignore` automatically.
  Basis: Confirmed product-policy decision on September 12, 2026.
- R3: Each resumable checkpoint must include a workspace fingerprint. The
  fingerprint must exclude `.fabrica/`, `.git/`, and paths matched by an optional
  Gitignore-style `.fabricaignore`; by default, no other paths are excluded.
  Users may exclude any workspace paths. Fabrica must validate ignore-pattern
  syntax, but must not infer whether an excluded path is semantically relevant;
  its help and documentation must warn that excluding relevant paths can make
  normal resume less context-sensitive.
  Basis: Confirmed product-policy decision on September 12, 2026.
- R4: On an explicit resume request, Fabrica must compare the current fingerprint
  with the checkpoint fingerprint. A match must take the normal resume path by
  reconstructing completed durable context into a fresh model turn. A difference
  must transition the session to `stale_context` and require replan.
  Basis: Confirmed product-policy decision on September 12, 2026.
- R5: In `stale_context`, Fabrica must preserve history but programmatically block
  side-effecting tool calls until a successful fresh workspace inspection has
  occurred, an updated user-visible plan/intent summary has been displayed, and
  the user has explicitly acknowledged that summary. After acknowledgement, every
  side effect remains subject to current tool policy and its normal separate
  action-specific approval flow.
  Basis: Confirmed product-policy decision on September 11, 2026.
- R6: Stored events, checkpoints, refreshed-plan acknowledgement, and historical
  approvals must never silently replay a side effect or authorize a new action.
  An interruption checkpoint must preserve completed evidence only: resume must
  not revive a pending user question, approval, command, or patch. Commands and
  patches remain governed by their existing recovery contracts, while any resumed
  side effect requires a fresh model proposal and its normal separate approval.
  Existing accepted command and patch approval contracts remain authoritative.
  Basis: Confirmed product-policy decision and accepted Version 1 contracts.
- R7: The MVP must introduce a versioned deterministic offline evaluation corpus
  with rule-based transcript, tool, and state assertions. Its initial fixtures
  must cover inspect-only success, an approved scoped edit plus validation,
  denied-approval recovery, interruption and safe-boundary resume,
  fingerprint-mismatch replan, and secret-capture exclusions. It must report
  results but must not initially block changes or releases. A future maintainer
  may separately decide to make it a release gate.
  Basis: Confirmed product-policy decision on September 12, 2026.
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

| Decision                             | Confirmed outcome                                                                                                                                                                                                                    | Basis                                                  |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| Durable record content and retention | Capture unredacted structured, model-visible session evidence; never capture process environments, credentials, auth headers, raw provider payloads, or non-structured terminal keystrokes. Retain indefinitely until user deletion. | User-confirmed interview decision, September 12, 2026. |
| Storage and lifecycle                | Store records in workspace-local `.fabrica/`; warn before first capture; support list, inspect, export, and single-session deletion; keep exports outside Fabrica's lifecycle; never edit `.gitignore`.                              | User-confirmed interview decision, September 12, 2026. |
| Resume validation                    | Compare checkpoint and current workspace fingerprints; exclude `.fabrica/`, `.git/`, and optional user-selected `.fabricaignore` patterns. Warn that exclusions can make normal resume less context-sensitive.                       | User-confirmed interview decision, September 12, 2026. |
| Mismatch handling                    | Enter `stale_context` replan; require fresh inspection, displayed refreshed plan, and user acknowledgement before proposing a side effect for separate normal approval.                                                              | User-confirmed interview decision, September 11, 2026. |
| Safe-boundary resume                 | Resume from completed durable context in a fresh model turn; never revive pending questions, approvals, commands, or patches; require fresh approval for each new side effect.                                                       | User-confirmed interview decision, September 12, 2026. |
| Evaluation promotion                 | Use a small deterministic corpus with rule-based transcript, tool, and state assertions; start as reporting-only and require a separate future decision to make it gating.                                                           | User-confirmed interview decision, September 12, 2026. |
| Execution isolation                  | Make a policy-only statement; do not make a sandbox-containment guarantee.                                                                                                                                                           | User-confirmed interview decision, September 11, 2026. |

## Open Questions

No product-policy decision blocks a derived implementation plan. The following
implementation design choices must preserve the requirements above and require
maintainer review during planning:

| Question                                                                                        | Impact                                                                        | Owner      | Resolution                           |
| ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ---------- | ------------------------------------ |
| What durable-record encoding, schema versioning, and migration policy should `.fabrica/` use?   | Determines implementation compatibility and recovery behavior.                | Maintainer | Deferred to implementation planning. |
| What deterministic fingerprint algorithm and path-normalization rules should implement R3?      | Determines reproducibility, performance, and precise matching semantics.      | Maintainer | Deferred to implementation planning. |
| What terminal command names and export-bundle representation best fit existing CLI conventions? | Determines the user-facing interface without changing the required lifecycle. | Maintainer | Deferred to implementation planning. |
| Which stable report fields best demonstrate R7?                                                 | Determines useful evaluation evidence while preserving reporting-only status. | Maintainer | Deferred to implementation planning. |

## Acceptance and Planning Gate

The maintainer accepted this specification on September 12, 2026 after confirming
the consolidated product-policy interview outcomes. Persistent session-event
storage is an architectural decision recorded by ADR 0012. The derived
implementation plan may resolve the listed implementation design choices without
changing these requirements. Any future change to the policy-only isolation claim,
session-data sensitivity boundary, or accepted Version 1 tool, approval, workspace,
and offline-validation contracts requires a material specification revision and,
where applicable, an ADR.

## Revision and Handoff Notes

- September 12, 2026: Accepted after confirmation of the local-data lifecycle,
  safe-boundary resume, structured evidence boundary, unrestricted user-selected
  fingerprint exclusions, and initial deterministic evaluation corpus.
- The roadmap remains an idea record. This accepted MVP adds no runtime authority.
- Next authorized step: execute the derived implementation plan under ADR 0012.
