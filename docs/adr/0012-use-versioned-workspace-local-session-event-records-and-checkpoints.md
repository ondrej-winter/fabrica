# 0012. Use Versioned Workspace-Local Session Event Records and Checkpoints

Date: 2026-09-12
Status: Accepted

## Context

The accepted mature-agent MVP requires durable session evidence, safe-boundary
resume, local inspection/export/deletion workflows, and deterministic offline
evaluation for Fabrica's terminal-hosted, workspace-scoped coding-agent session.
The existing Version 1 runtime owns normalized tool-turn transcripts only while a
run is active. Existing command and patch features own their individual approval,
recovery, and side-effect semantics.

Persisting opaque provider conversation state would couple recovery to a volatile
transport. Persisting a raw host or provider recording would capture credentials,
environments, wire payloads, and terminal keystrokes outside the accepted session
evidence boundary. Replaying an interrupted call, approval, command, or patch
would violate action-specific approval and existing recovery contracts.

## Decision

Fabrica will persist versioned, workspace-local append-only structured session
events and durable checkpoints beneath the selected workspace's `.fabrica/`
directory. The storage design must support schema evolution and recoverable reads.
Its records contain only the accepted structured, model-visible session-evidence
boundary; they must not contain process environments, credentials, authentication
headers, raw provider wire payloads, or terminal keystrokes outside structured
answers.

Checkpoints represent completed durable context, never suspended executable work.
Resume reconstructs that context into a fresh model turn after comparing the
current workspace fingerprint with the checkpoint fingerprint. A match permits
normal resume. A mismatch enters the MVP's `stale_context` replan workflow. No
resume path may revive or replay a pending question, approval, command, or patch;
new side effects require a new proposal and their ordinary separate approval.

The selected record encoding, schema-version migration policy, fingerprint
algorithm, path normalization, CLI names, and export representation remain derived
implementation-plan decisions. They must preserve this decision and the accepted
MVP specification.

## Consequences

- Durable session storage becomes a new cross-cutting product concern, composed at
  the terminal-session boundary while keeping provider transport and existing tool
  contracts authoritative.
- The implementation needs explicit event/checkpoint DTOs and ports, a
  workspace-local storage adapter, recovery behavior for incomplete writes, and
  terminal workflows for list, inspect, export, delete, and resume.
- `.fabrica/` is sensitive user-managed local evidence. Fabrica warns before first
  capture, retains records until explicit single-session deletion, and does not
  manage exported copies or alter filesystem permissions or `.gitignore`.
- Session history improves inspectability and deterministic evaluation, but it is
  not implicit authorization and does not make Fabrica a sandboxed runtime.
- Default validation remains deterministic, offline, and credential-free; any
  live-model evaluation remains optional and disposable.

## Alternatives considered

| Option                                                    | Reason rejected                                                                                                       |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Persist provider conversation IDs or opaque backend state | Couples resume correctness to volatile provider behavior and weakens deterministic offline fixtures.                  |
| Restore exact pending interactions or approvals           | A historical pending state cannot safely authorize a later action; re-presentation also risks replay confusion.       |
| Record raw process, terminal, and provider traffic        | Exceeds the accepted evidence boundary and increases credential/privacy exposure without improving session semantics. |
| Use only an in-memory transcript                          | Cannot support interruption recovery, local audit evidence, inspection, export, or deterministic resume evaluation.   |
