# Implementation Plan: Mature Agent MVP

## Status

- State: Ready for implementation.
- Source specification: [`docs/specs/mature-agent-mvp-spec.md`](../specs/mature-agent-mvp-spec.md), accepted September 12, 2026.
- Related decision: [ADR 0012](../adr/0012-use-versioned-workspace-local-session-event-records-and-checkpoints.md).
- Created: September 12, 2026.
- Planning decisions confirmed: September 13, 2026.

## Scope and constraints

This plan implements durable workspace-local terminal-session evidence,
safe-boundary resume, mismatch replan, user-managed record lifecycle, a
reporting-only deterministic evaluation corpus, and policy-only isolation
documentation. It must preserve the accepted Version 1 workspace containment,
tool exposure, action-specific approval, command/patch recovery, provider
isolation, and offline default validation contracts.

It does not add default web, Git mutation, or Skill-script authority; external
telemetry; automatic redaction, retention cleanup, upload, or `.gitignore`
mutation; a sandbox guarantee; or a new host.

## Confirmed planning decisions

| ID     | Decision                        | Confirmed design                                                                                                                                                                                                                                                                                                       | Required evidence                                         |
| ------ | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------ | ------ | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| MAD-01 | Durable records and recovery    | Store one schema-versioned JSON Lines event journal per session plus separately atomically replaced JSON checkpoint/metadata. Recover a malformed final journal record as an incomplete write; treat earlier corruption as unreadable and fail closed.                                                                 | Focused recovery tests and ADR-compatible design note.    |
| MAD-02 | Workspace fingerprinting        | Hash a canonical SHA-256 manifest sorted by workspace-relative POSIX path; each entry contains the path and file-content SHA-256. Honor `.fabricaignore`, reject escaping paths, and treat symlinks, unreadable/changing files, and scan failures as unavailable fingerprints requiring `stale_context`.               | Stable fixture vectors and coverage rationale.            |
| MAD-03 | CLI and export                  | Use `fabrica agent sessions list                                                                                                                                                                                                                                                                                       | inspect                                                   | resume | export | delete`. Export a deterministic directory bundle containing `manifest.json`, `events.jsonl`, and `checkpoint.json`. | `--help` coverage and deterministic export/inspection tests. |
| MAD-04 | Normalized observation capture  | Bootstrap decorates the published agent-runtime observation boundary. The recorder assigns a session ID and monotonic per-session sequence and synchronously writes each normalized event before continuation. An event or checkpoint write failure prevents further model/tool activity and ends the run as `failed`. | Ordered-event and write-failure composition tests.        |
| MAD-05 | Fresh-turn resume context       | The `agent_session` slice owns immutable provider-neutral `ResumeContext`, built from the latest completed checkpoint and a bounded ordered summary of later normalized events. Its continuation instruction treats history as context only and requires current workspace inspection before proposing work.           | Application-contract and normal-resume integration tests. |
| MAD-06 | `stale_context` acknowledgement | After fresh inspection and a displayed refreshed plan, require a dedicated terminal yes/no acknowledgement bound to that plan digest. Persist a distinct acknowledgement event; expire it when the plan changes; never treat it as a question answer or side-effect approval.                                          | State-transition and acknowledgement-isolation tests.     |

## Architecture and dependency order

```text
coding-agent-session CLI and terminal adapters
    -> agent-session application ports and use cases
        -> session event/checkpoint and resume-context DTOs
        -> workspace-local record and fingerprint adapters
bootstrap composition
    -> existing coding-agent-session published runtime boundary
    -> agent-runtime normalized observation boundary
```

The new `agent_session` feature owns durable session records, lifecycle,
fingerprinting, and safe-boundary resume orchestration. It consumes published
application ports only; it must not import private coding-agent-session use cases
or adapters. Existing workspace command and patch features retain their own
recovery and approval behavior.
Bootstrap composes cross-slice dependencies and the event-observation decorators;
adapters do not orchestrate side effects directly.

## Requirement traceability

| Requirement                                                   | Planned work                   |
| ------------------------------------------------------------- | ------------------------------ |
| R1 — Structured durable evidence boundary                     | MAM-01, MAM-02, MAM-04         |
| R2 — Sensitive lifecycle, warning, export, and deletion       | MAM-02, MAM-04, MAM-06, MAM-08 |
| R3 — Fingerprints and user-selected exclusions                | MAM-03, MAM-06, MAM-08         |
| R4 — Normal resume or mismatch replan                         | MAM-03, MAM-05                 |
| R5 — Replan acknowledgement before side effects               | MAM-05, MAM-06                 |
| R6 — No replay or inherited authority                         | MAM-01, MAM-04, MAM-05         |
| R7 — Deterministic reporting-only corpus                      | MAM-01, MAM-07                 |
| R8 — Optional live evaluation remains disposable and separate | MAM-07, MAM-09                 |
| R9 — Threat model and policy-only isolation posture           | MAM-08                         |

## Progress Tracking

- [x] **MAM-01** Establish storage and resume contracts. Evidence: September 13, 2026 — `agent_session` owns immutable normalized event, completed-checkpoint, resume-context, and stale-context acknowledgement DTOs; legal lifecycle transitions and focused unit tests pass.
- [x] **MAM-02** Implement versioned workspace-local event and checkpoint storage. Evidence: September 13, 2026 — POSIX `.fabrica/sessions/<session-id>/` JSONL/checkpoint adapter covers append durability, tail recovery, corruption rejection, export, and isolated deletion in temporary-workspace tests.
- [x] **MAM-03** Implement fingerprinting and `.fabricaignore` handling. Evidence: September 13, 2026 — deterministic SHA-256 manifest adapter excludes `.fabrica/` and `.git/`, supports ordered exclusions, and fails closed for invalid patterns and symlinks.
- [x] **MAM-04** Establish event-observation composition and integrate durable lifecycle capture. Evidence: September 13, 2026 — bootstrap-composed normalized model/tool observation decorators persist sensitivity warning, correlated monotonic events, running/completed checkpoints, and terminal dispositions in workspace-local records; recorder failures fail closed without changing tool authority. Focused tests and full offline quality gate pass (2,303 passed, 4 skipped).
- [ ] **MAM-05** Implement safe-boundary normal resume and stale-context replan.
- [ ] **MAM-06** Add terminal session-history, inspect, export, delete, and resume workflows.
- [ ] **MAM-07** Add deterministic reporting-only evaluation corpus.
- [ ] **MAM-08** Document the sensitive-data and policy-only isolation posture.
- [ ] **MAM-09** Complete full validation and handoff.

## Tasks

### MAM-01 — Establish storage, resume, and evaluation contracts

- [x] **MAM-01** Define `agent_session` feature-owned domain/application DTOs,
      ports, session-state transition rules, and test fakes for requirements R1, R4,
      R5, R6, and R7.

**Likely targets**

```text
src/fabrica/features/agent_session/domain/
src/fabrica/features/agent_session/application/dtos/
src/fabrica/features/agent_session/application/ports/
src/fabrica/features/agent_session/application/use_cases/
tests/unit/features/agent_session/
```

**Acceptance criteria**

- Contracts distinguish completed durable evidence from pending or in-flight work.
- The capture DTO boundary excludes every R1-prohibited host/provider artifact.
- State transitions reject invalid replay-oriented paths.
- The immutable provider-neutral `ResumeContext` contains a latest completed
  checkpoint, bounded ordered later-event summary, and fresh continuation
  instruction requiring current workspace inspection.
- The digest-bound stale-context acknowledgement is represented separately from
  question answers and ordinary command or patch approval decisions.

**Verification**

- Focused DTO, transition, and fake-port unit tests pass.
- Tests prove the confirmed MAD-01 through MAD-06 contracts before dependent
  adapter or composition work.

### MAM-02 — Implement versioned workspace-local event and checkpoint storage

- [x] **MAM-02** Implement append-only event recording, durable checkpoints,
      schema-version dispatch, single-session deletion, inspection, and export behind
      an outbound port.

**Dependencies:** MAM-01.

**Acceptance criteria**

- Storage is scoped to the canonical selected workspace's `.fabrica/` directory.
- A malformed final JSON Lines record is ignored as an incomplete write; corruption
  before that tail is unreadable and cannot be resumed.
- Checkpoint/metadata replacement is atomic so readers observe either the prior
  completed checkpoint or the replacement, never a partial checkpoint.
- Delete removes only the selected session; export does not become lifecycle-managed state.
- Records retain exactly the R1 capture boundary without automatic redaction or upload.

**Verification**

- Adapter integration tests use temporary workspaces and cover round-trip,
  incomplete-tail and earlier-corruption recovery, schema dispatch, export, valid
  checkpoint selection, and isolated deletion.

### MAM-03 — Implement fingerprinting and `.fabricaignore` handling

- [x] **MAM-03** Implement deterministic workspace fingerprint creation and
      comparison with mandatory `.fabrica/`/`.git/` exclusions and optional
      Gitignore-style `.fabricaignore` patterns.

**Dependencies:** MAM-01.

**Acceptance criteria**

- Pattern syntax failure is explicit and prevents unsafe ambiguous fingerprinting.
- User-selected exclusions may target any workspace path.
- The canonical manifest sorts workspace-relative POSIX paths and includes each
  path with its file-content SHA-256.
- Escaping paths, symlinks, unreadable or disappearing files, concurrent
  modification, and other scan failures produce an unavailable fingerprint that
  requires `stale_context` rather than a normal resume.
- Stable fixture vectors prove normalization and changed/non-changed outcomes.

**Verification**

- Unit and temporary-workspace tests cover mandatory exclusions, user exclusions,
  invalid patterns, path normalization, symlink and filesystem-race disposition,
  and matching/mismatching snapshots.

### MAM-04 — Establish event-observation composition and durable lifecycle capture

- [x] **MAM-04** Implement the bootstrap-composed synchronous observation recorder
      around terminal coding-session model turns, tools, approvals, questions, errors,
      final dispositions, and lifecycle transitions.

**Dependencies:** MAM-02, MAM-03.

**Acceptance criteria**

- First capture produces the required sensitivity warning.
- Recorded events are append-only, session-correlated, and sequenced
  monotonically per session.
- Bootstrap owns recorder composition; each normalized event is written before the
  run continues. An event or checkpoint write failure prevents further model/tool
  activity and ends the session as `failed`.
- Process environments, credentials, auth headers, raw provider payloads, and
  non-structured terminal keystrokes are absent from persisted artifacts.
- Existing tool approvals and recovery contracts are unchanged.

**Verification**

- Offline composition tests assert ordered correlated event capture, persistence
  write-failure disposition, prohibited-data absence, and no added tool authority.

### MAM-05 — Implement safe-boundary normal resume and stale-context replan

- [ ] **MAM-05** Add resume orchestration that compares fingerprints, reconstructs
      completed evidence into a fresh model turn for a match, and enters
      `stale_context` for a mismatch.

**Dependencies:** MAM-03, MAM-04.

**Acceptance criteria**

- Resume never restores a pending question, approval, command, or patch.
- Normal resume starts a fresh model turn from the latest completed checkpoint and
  a bounded ordered summary of later normalized events; it requires current
  workspace inspection before proposing work.
- Mismatch blocks side effects until fresh inspection, displayed refreshed plan,
  a dedicated digest-bound terminal acknowledgement, and ordinary separate approval.
- The replan acknowledgement expires when its plan changes, cannot authorize a
  command, patch, or other side effect, and cannot be fulfilled by a historical
  question answer.

**Verification**

- Integration tests cover interruption, match, provider-neutral fresh-turn context,
  mismatch, stale-context blocking, fresh acknowledgement isolation, and non-replay
  of command/patch effects.

### MAM-06 — Add terminal session-record workflows

- [ ] **MAM-06** Add CLI workflows to start persisted sessions and list, inspect,
      export, delete, and resume them; document `.fabricaignore` trade-offs in help.

**Dependencies:** MAM-02, MAM-05.

**Acceptance criteria**

- CLI exposes `fabrica agent sessions list|inspect|resume|export|delete`; output
  identifies session state and produces clear deletion/export evidence.
- Export produces a deterministic directory bundle with `manifest.json`,
  `events.jsonl`, and `checkpoint.json`.
- Help warns that records are sensitive and exclusions can reduce resume sensitivity.
- The terminal start/list/inspect/export/delete/resume contract includes a visible
  warning when `.fabrica/` is not Git-ignored, does not warn incorrectly when no
  Git repository exists, and never modifies `.gitignore`.
- Commands retain workspace scoping and do not modify `.gitignore`.

**Verification**

- CLI parser/adapter tests cover Git-ignored, unignored, non-Git-workspace, and
  unreadable/malformed ignore-file outcomes; `uv run fabrica --help` and relevant
  subcommand help checks pass.

### MAM-07 — Add deterministic reporting-only evaluation corpus

- [ ] **MAM-07** Build versioned fixtures and rule-based transcript/tool/state
      assertions for R7's six confirmed scenarios, then emit a deterministic report.

**Dependencies:** MAM-04, MAM-05.

**Acceptance criteria**

- Corpus covers inspect-only success, approved scoped edit plus validation,
  denied-approval recovery, interruption/safe-boundary resume, mismatch replan,
  and secret-capture exclusions.
- It runs offline and credential-free, reports results, and does not gate releases.
- Fixture source of truth, report invocation, report location, schema version, and
  stable report fields are explicit; fixtures use normalized persisted evidence or
  fake application ports rather than provider wire payloads.
- Any optional live-model extension uses a disposable workspace and remains outside
  the default local and CI quality gates.

**Verification**

- Corpus tests pass in the default suite and assert a stable report schema.

### MAM-08 — Document the sensitive-data and policy-only isolation posture

- [ ] **MAM-08** Update project documentation with `.fabrica/` lifecycle and
      capture boundaries, resume/replan behavior, `.fabricaignore` warning, evaluation
      status, and the R9 threat model/policy-only isolation statement.

**Dependencies:** MAM-06, MAM-07.

**Acceptance criteria**

- Documentation does not promise redaction, automatic cleanup, upload safety, or sandbox containment.
- README-level guidance and detailed documentation match implemented commands and evidence boundaries.
- The threat model addresses malicious repository contents and scripts, prompt
  injection, secret exfiltration, symlink and concurrent-filesystem attacks,
  untrusted Skills, and network access, while truthfully stating the local
  operating system and user-process privileges as the effective isolation boundary.

**Verification**

- Documentation review against CLI help, storage tests, and the accepted specification.

### MAM-09 — Complete full validation and handoff

- [ ] **MAM-09** Run the configured project quality gate and record evidence.

**Dependencies:** MAM-01 through MAM-08.

**Required commands**

```bash
uv run ruff format .
uv run ruff check .
uv run ty check src tests
uv run lint-imports
uv run pytest
```

**Acceptance criteria**

- Focused tests and the configured full offline quality gate pass without bypasses.
- Handoff identifies the confirmed MAD-01 through MAD-06 designs, changed files,
  validation evidence, and intentionally unrun opt-in live checks.

## Risks and guardrails

1. Treat persisted records as sensitive user-managed artifacts; do not broaden the
   capture boundary while implementing convenient diagnostics.
2. Preserve append-only evidence and avoid using session history as implicit
   authority or a substitute for existing command/patch recovery.
3. Keep provider transport payloads private to the transport adapter; durable
   session records use normalized application-level evidence only.
4. Keep fingerprints deterministic and workspace-contained; document, rather than
   silently override, the user's chosen `.fabricaignore` trade-off.
5. Keep deterministic evaluations independent of live credentials and external
   services; a report is not a release gate without a future accepted decision.
6. Do not treat an acknowledgement, historical answer, or resumed context as
   authorization; every new command or patch remains subject to its existing
   ordinary approval path.
7. Treat fingerprint scan failures and persistence write failures as explicit state
   dispositions, never as silent successful matches or durable evidence.
