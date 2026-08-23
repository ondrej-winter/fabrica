# Implementation Plan: `apply_patch` Tool

## Overview

Implement the complete v1 contract in `docs/specs/apply-patch-tool.md`: one model-facing `apply_patch` tool for safe, contextual, multi-file UTF-8 workspace mutation, including authorization, derived directory effects, journaled commit/rollback, startup recovery, duplicate-delivery handling, and fatal-state propagation.

This plan is intentionally a living document. During implementation, update task, acceptance-criteria, verification, checkpoint, blocker, and deviation status after each completed task or meaningful scope change.

## Deliverables

- A new `workspace_editing` vertical slice under `src/fabrica/features/workspace_editing/`.
- Async, cancellation-aware registered-tool runtime contracts.
- Typed tool outcomes supporting recoverable rejection and fatal mutation states.
- POSIX filesystem adapters for supported macOS/Linux filesystems.
- Parser, matcher, planner, policy, approval, staging, commit, rollback, and recovery behavior.
- A model-facing `apply_patch` registration and bootstrap composition.
- Unit, integration, fault-injection, concurrency, and recovery tests.
- ADRs, spec clarification, README/index updates, and platform evidence.

## Constraints

- Deliver the complete v1 specification, not a reduced MVP.
- Preserve hexagonal vertical-slice boundaries and existing import-linter contracts.
- Keep all filesystem handles, OS structures, durability operations, and UI approval details in adapters/bootstrap.
- Do not add a dependency until the POSIX capability spike proves the standard library is insufficient.
- Do not claim cross-file atomicity.
- Do not expose overlapping model-facing create, delete, move, mkdir, or whole-file-write tools.
- Unsupported safety guarantees must fail before file commit rather than degrade silently.
- Keep this plan current during implementation.

## Readiness Finding

Implementation is blocked pending an architectural feasibility gate. Exploration found three issues that must be resolved before production `workspace_editing` code begins:

1. Derived parent directories become visible before the spec's stated file commit point. They must be modeled as reversible pre-file-commit mutations with durable recovery intent, cancellation cleanup, directory outcomes, and truthful mutation guarantees.
2. The current registered-tool contract returns only `str`. It cannot represent recoverable `REJECTED` outcomes, fatal partial/indeterminate outcomes, structured metadata, or safe output-bound behavior.
3. A hard non-cancellable cleanup deadline conflicts with “never return while mutation may continue” if a POSIX operation blocks. The design must prove bounded in-process cleanup or use a supervised helper process whose state and recovery ownership survive the caller deadline.

## Architecture Decisions

- Model-facing mutation remains a single `apply_patch` registered tool with canonical `{ "input": string }` arguments.
- Operation-specific parser, matcher, planner, filesystem, journal, and recovery components are internal implementation details owned by `workspace_editing`.
- Cross-slice integration happens through published application ports and bootstrap composition; feature adapters must not import cross-slice adapters.
- Visible derived destination parent directories are planned effects, not model-authored actions, and require explicit approval, journaling, rollback, recovery, and result evidence.
- No production implementation starts before Checkpoint A proves runtime and POSIX feasibility.

## Progress Tracking

After every completed task or meaningful change:

- check off completed tasks, acceptance criteria, verification items, and checkpoints;
- leave unfinished or unverified items unchecked;
- add newly discovered work and update sequencing when scope or dependencies change;
- note blockers, deviations, and decisions that affect remaining work.

## Task List

### Phase 1: Design Gates and Runtime Foundation

- [ ] Task 1: Clarify the mutation lifecycle and record architecture decisions
- [ ] Task 2: Define typed async registered-tool execution contracts
- [ ] Task 3: Migrate the tool loop and model boundary to async
- [ ] Task 4: Implement runtime ledger and mutation-aware status mapping
- [ ] Task 5: Prove POSIX capability and cleanup-deadline feasibility

### Checkpoint A: Architecture Feasibility

- [ ] Tasks 1-5 are accepted.
- [ ] Async runtime and existing tools pass their tests.
- [ ] The cleanup/deadline model is credible on both supported platforms.
- [ ] No new dependency is added without recorded evidence.
- [ ] Production `workspace_editing` implementation has not started before this checkpoint.

### Phase 2: Pure `workspace_editing` Application Core

- [ ] Task 6: Establish DTOs, exhaustive errors, and result serialization
- [ ] Task 7: Implement the side-effect-free patch parser
- [ ] Task 8: Implement text snapshot decoding and rendering
- [ ] Task 9: Implement deterministic hunk matching
- [ ] Task 10: Define slice-owned ports and recovery state machine
- [ ] Task 11: Implement immutable planning, preview, and digest generation

### Checkpoint B: Pure Core

- [ ] Parser, text, matcher, ports, recovery state machine, planner, preview, and result-contract tests pass.
- [ ] No application module performs filesystem or approval UI I/O.

### Phase 3: POSIX Adapters and Transactional Behavior

- [ ] Task 12: Implement the mutating resolver and snapshot adapter
- [ ] Task 13: Implement mutation lease, policy, and approval adapters
- [ ] Task 14: Implement durable journal and reversible pre-commit effects
- [ ] Task 15: Implement staging, revalidation, and commit scheduling
- [ ] Task 16: Implement rollback and startup recovery

### Checkpoint C: Filesystem Safety

- [ ] Basic operations, stale plans, concurrency, durability, rollback, retained directories, and recovery pass on supported POSIX systems.
- [ ] Fault tests cover every journal transition and visible mutation step.
- [ ] The adapter never reports while unmanaged mutation can continue.

### Phase 4: Use Case, Model Exposure, and Handoff

- [ ] Task 17: Compose the `ApplyPatch` application use case
- [ ] Task 18: Register the sole model-facing tool and complete acceptance evidence

### Checkpoint D: Complete v1

- [ ] Every success criterion in the specification maps to passing automated evidence.
- [ ] No overlapping filesystem mutation tool is registered.
- [ ] macOS and Linux capability evidence is recorded.
- [ ] Full local quality gate passes.
- [ ] This living plan reflects final status, deviations, and unresolved operational follow-ups.

## Detailed Tasks

### Task 1: Clarify the Mutation Lifecycle and Record Architecture Decisions

**Description:** Amend the specification and add ADRs covering visible derived-directory effects, durable recovery intent, file commit point, rollback/recovery ownership, async tool execution, and duplicate delivery.

**Acceptance criteria:**

- [ ] The lifecycle explicitly distinguishes side-effect-free planning from visible reversible directory creation and file commit.
- [ ] Cancellation and mutation guarantees are defined for created, removed, retained, and uncertain directories.
- [ ] ADRs document the runtime and filesystem decisions, including the lack of cross-file atomicity.

**Verification:**

- [ ] Documentation review covers every lifecycle, cancellation, rollback, and recovery statement in `docs/specs/apply-patch-tool.md`.
- [ ] ADR index links to the new decisions.

**Dependencies:** None.

**Files likely touched:**

- `docs/specs/apply-patch-tool.md`
- `docs/adr/0002-*.md`
- `docs/adr/0003-*.md`
- `docs/adr/README.md`
- `docs/specs/README.md`

**Estimated scope:** Medium.

### Task 2: Define Typed Async Registered-Tool Execution Contracts

**Description:** Replace the `Callable[..., str]` assumption with an async handler receiving a typed execution context and returning a typed outcome.

**Acceptance criteria:**

- [ ] `ToolExecutionContext` carries call identity, canonical argument digest, cancellation, and phase deadlines without exposing host services generically.
- [ ] The outcome distinguishes model-continue success, recoverable rejection, ordinary tool failure, and fatal runtime stop.
- [ ] Result bounding always preserves status, error code, mutation guarantee, and fatal disposition before optional detail.

**Verification:**

- [ ] DTO and port tests cover immutability, status invariants, canonical serialization, and bounded output.

**Dependencies:** Task 1.

**Files likely touched:**

- `src/fabrica/features/agent_runtime/application/dtos/tools.py`
- `src/fabrica/features/agent_runtime/application/ports/registered_tool.py`
- `src/fabrica/features/agent_runtime/application/ports/tool_execution.py`
- `tests/unit/features/agent_runtime/application/test_tool_dtos.py`
- `tests/unit/features/agent_runtime/adapters/outbound/registered_tool/test_adapter.py`

**Estimated scope:** Medium.

### Task 3: Migrate the Tool Loop and Model Boundary to Async

**Description:** Migrate `RunToolLoop`, tool-aware model ports/adapters, runtime wrappers, and composition to async. Adapt existing deterministic tools through an explicit sync-handler wrapper.

**Acceptance criteria:**

- [ ] Existing tools run through the async boundary without changing their exposed behavior.
- [ ] Cancellation reaches model turns and tool handlers.
- [ ] Tool-call ordering remains deterministic.

**Verification:**

- [ ] Migrated agent-runtime unit tests pass.
- [ ] `tests/integration/features/agent_runtime/test_tool_loop_composition.py` passes.

**Dependencies:** Task 2.

**Files likely touched:**

- `src/fabrica/features/agent_runtime/application/use_cases/run_tool_loop.py`
- `src/fabrica/features/agent_runtime/application/ports/tool_aware_agent_model.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/registered_tool/adapter.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/pydantic_ai_model/`
- `src/fabrica/bootstrap/composition/tool_loop.py`
- `tests/unit/features/agent_runtime/application/test_run_tool_loop.py`
- `tests/integration/features/agent_runtime/test_tool_loop_composition.py`

**Estimated scope:** Large; split during implementation if test migration becomes noisy.

### Task 4: Implement Runtime Ledger and Mutation-Aware Status Mapping

**Description:** Add exact duplicate-delivery replay and runtime behavior for recoverable versus fatal tool outcomes.

**Acceptance criteria:**

- [ ] Same `call_id` and canonical normalized-argument digest returns the recorded terminal result without handler execution.
- [ ] Same `call_id` with different arguments is rejected before execution.
- [ ] Recoverable patch rejection continues the model loop; partial, rollback-failed, and indeterminate outcomes stop it fatally.

**Verification:**

- [ ] Unit and integration tests assert handler invocation counts and loop status.

**Dependencies:** Tasks 2-3.

**Files likely touched:**

- Agent-runtime DTOs and ports
- `src/fabrica/features/agent_runtime/application/use_cases/run_tool_loop.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/registered_tool/adapter.py`
- Agent-runtime unit and integration tests

**Estimated scope:** Medium.

### Task 5: Prove POSIX Capability and Cleanup-Deadline Feasibility

**Description:** Build a non-production spike for macOS and Linux covering no-follow traversal, no-replace rename, pinned identities, link counts, mode bits, file/directory `fsync`, and blocked-operation ownership.

**Acceptance criteria:**

- [ ] Evidence identifies which primitives are available through Python 3.13 and where `ctypes` or another dependency would be required.
- [ ] The design chooses either demonstrably bounded in-process cleanup or a supervised helper-process/recovery model.
- [ ] Unsupported platforms/filesystems have a deterministic fail-closed probe result.

**Verification:**

- [ ] Focused probe tests run on real macOS and Linux runners.
- [ ] Recorded evidence includes commands, filesystem type, Python version, and results.

**Dependencies:** Task 1.

**Files likely touched:**

- Isolated probe/test modules
- ADRs from Task 1
- Optional CI matrix files if needed

**Estimated scope:** Medium.

### Task 6: Establish DTOs, Exhaustive Errors, and Result Serialization

**Description:** Create the `workspace_editing` slice’s application DTOs, error table, status types, mutation guarantees, and compact JSON serialization boundary.

**Acceptance criteria:**

- [ ] Frozen DTOs represent actions, hunks, limits, evidence, plans, statuses, mutation guarantees, and path/directory outcomes.
- [ ] Every required v1 error code has phase, retryability, mutation guarantee, required metadata, and runtime mapping.
- [ ] Compact canonical JSON preserves mandatory fields under output limits.

**Verification:**

- [ ] DTO invariant, error-table exhaustiveness, and serialization tests pass.

**Dependencies:** Checkpoint A.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/dtos/`
- `src/fabrica/features/workspace_editing/application/errors.py`
- `tests/unit/features/workspace_editing/application/`

**Estimated scope:** Medium.

### Task 7: Implement the Side-Effect-Free Patch Parser

**Description:** Parse the canonical patch protocol into immutable intermediate representation without reading or mutating the filesystem.

**Acceptance criteria:**

- [ ] Canonical sentinels and Add/Update/Delete/Move grammar are parsed exactly.
- [ ] Anchors, before/after insertion, EOF assertion, and terminal-newline directives obey the spec.
- [ ] Invalid, incomplete, unprefixed, over-limit, and no-op forms return the required error codes.

**Verification:**

- [ ] Table-driven parser tests cover the grammar acceptance matrix.

**Dependencies:** Task 6.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/use_cases/parse_patch.py`
- Parser DTOs and tests

**Estimated scope:** Medium.

### Task 8: Implement Text Snapshot Decoding and Rendering

**Description:** Represent source and resulting text bytes with exact UTF-8, BOM, EOL, and terminal-newline semantics.

**Acceptance criteria:**

- [ ] UTF-8 and UTF-8 BOM are distinguished; NUL/binary and unsupported encoding are rejected.
- [ ] Uniform LF/CRLF and terminal-newline state are represented exactly; mixed EOL is rejected.
- [ ] Rendering preserves BOM, EOL, terminal newline, and inserted bytes according to the action rules.

**Verification:**

- [ ] Byte-level unit tests cover empty files and no-terminal-newline cases.

**Dependencies:** Task 6.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/`
- `tests/unit/features/workspace_editing/application/`

**Estimated scope:** Medium.

### Task 9: Implement Deterministic Hunk Matching

**Description:** Match hunks against immutable source snapshots using the v1 exact and trailing-whitespace-only strategy.

**Acceptance criteria:**

- [ ] Matching uses immutable source snapshots, exact pass first, then trailing-whitespace-only tolerance.
- [ ] Ambiguous/missing anchors and hunks, overlap, reverse order, unsafe insertion, and EOF failure are rejected deterministically.
- [ ] Untouched context bytes come from the source snapshot.

**Verification:**

- [ ] Focused matching matrix and property-style edge-case tests pass.

**Dependencies:** Tasks 7-8.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/use_cases/match_hunks.py`
- Matcher support modules and tests

**Estimated scope:** Medium.

### Task 10: Define Slice-Owned Ports and Recovery State Machine

**Description:** Define all application-owned outbound ports and the durable journal/recovery state machine before commit adapter implementation.

**Acceptance criteria:**

- [ ] Ports cover lease, capability/snapshot access, policy, approval, staging/commit, journal/recovery, clock, and cancellation where needed.
- [ ] OS handles and platform structs do not cross the application boundary.
- [ ] Journal states, legal transitions, crash points, and recovery outcomes are exhaustive before commit code exists.

**Verification:**

- [ ] Type checks, state-transition tests, and architecture/import-linter review pass.

**Dependencies:** Tasks 1, 5-6.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/ports/`
- Recovery DTO/state modules
- `tests/unit/features/workspace_editing/application/`

**Estimated scope:** Medium.

### Task 11: Implement Immutable Planning, Preview, and Digest Generation

**Description:** Build `PatchPlan` from parsed actions and fake snapshots, including path validation, derived effects, preview, schedule, and digest.

**Acceptance criteria:**

- [ ] Global source/destination disjointness, aliases, move chains/swaps, collisions, resource ceilings, and derived directories are validated.
- [ ] Derived directories are collapsed and ordered; input reporting order and deterministic commit order remain distinct.
- [ ] Plan digest binds canonical actions, exact resulting bytes, evidence, effects, modes, schedule, and approval preview; truncated previews cannot be approved.

**Verification:**

- [ ] Planner tests with fake snapshots pass and prove zero filesystem I/O.

**Dependencies:** Tasks 6-10.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/use_cases/plan_patch.py`
- Preview/digest modules and tests

**Estimated scope:** Medium.

### Task 12: Implement the Mutating Resolver and Snapshot Adapter

**Description:** Implement the POSIX adapter responsible for mutating-safe path resolution and source/destination snapshot evidence.

**Acceptance criteria:**

- [ ] Root/parent traversal is handle-relative and rejects absolute, escaping, symlink, alias, special-file, multiple-hard-link, and non-directory-parent cases.
- [ ] Source and destination evidence includes required identities, hashes, metadata, ancestor identities, and absence evidence.
- [ ] Cross-device moves and failed capability probes reject before mutation.

**Verification:**

- [ ] Real-filesystem integration tests pass on macOS/Linux.

**Dependencies:** Tasks 5, 10-11.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/adapters/outbound/posix_filesystem/`
- `tests/integration/features/workspace_editing/`

**Estimated scope:** Medium.

### Task 13: Implement Mutation Lease, Policy, and Approval Adapters

**Description:** Add per-workspace serialization, host policy evaluation, and approval binding for immutable patch plans.

**Acceptance criteria:**

- [ ] One exclusive lease serializes all patch mutation for a workspace from before snapshot through cleanup.
- [ ] Default policy requires approval; `.git/**`, stage, and journal paths are denied.
- [ ] Approval is bound to the complete plan digest and cannot use a truncated preview.

**Verification:**

- [ ] Deterministic concurrency, cancellation, denial, timeout, and stale-approval tests pass.

**Dependencies:** Tasks 10-12.

**Files likely touched:**

- Workspace-editing outbound lease/policy/approval adapters
- Bootstrap seams
- Tests

**Estimated scope:** Medium.

### Task 14: Implement Durable Journal and Reversible Pre-Commit Effects

**Description:** Record recovery intent and manage visible derived-directory creation before file commit.

**Acceptance criteria:**

- [ ] Recovery intent is durable before creating visible destination parent directories.
- [ ] Directories are created shallowest-first through pinned handles and are reported/cleaned by identity.
- [ ] Cancellation after directory creation performs bounded cleanup and reports retained/failed/uncertain effects truthfully.

**Verification:**

- [ ] Fault injection covers every directory and journal transition.

**Dependencies:** Tasks 10, 12-13.

**Files likely touched:**

- POSIX journal/directory-effect adapters
- Integration tests

**Estimated scope:** Medium.

### Task 15: Implement Staging, Revalidation, and Commit Scheduling

**Description:** Create same-filesystem staging artifacts, revalidate plan evidence, and execute the deterministic pre-commit schedule.

**Acceptance criteria:**

- [ ] Same-filesystem staging uses host-controlled names and strict permissions, writes full contents, applies modes, and executes durability barriers.
- [ ] Source, parent, destination, directory absence, policy, and digest are revalidated at required boundaries.
- [ ] The explicit file commit point and deterministic action schedule match the approved plan.

**Verification:**

- [ ] Pre-commit fault tests prove either no visible effect or fully reported reversible directory effects.

**Dependencies:** Task 14.

**Files likely touched:**

- POSIX stage/commit adapter modules
- Integration tests

**Estimated scope:** Medium.

### Task 16: Implement Rollback and Startup Recovery

**Description:** Implement safe rollback after commit failures and startup handling for incomplete journals.

**Acceptance criteria:**

- [ ] Rollback never overwrites or removes independently changed paths and removes plan-created directories deepest-first only when identity and emptiness match.
- [ ] All terminal states include required per-path and directory evidence.
- [ ] Startup blocks mutation on incomplete journals; only evidence-proven rollback is automatic, otherwise status is `RECOVERY_REQUIRED`.

**Verification:**

- [ ] Fault injection after every visible commit step plus restart/crash-fixture tests pass.

**Dependencies:** Tasks 10, 14-15.

**Files likely touched:**

- POSIX rollback/recovery adapters
- Startup gate composition
- Integration tests

**Estimated scope:** Medium.

### Task 17: Compose the `ApplyPatch` Application Use Case

**Description:** Implement the single application orchestration path that composes parser, snapshot, matcher, planner, policy, approval, journal, stage, commit, rollback, cleanup, and result formatting ports.

**Acceptance criteria:**

- [ ] One orchestration path performs lease → parse → snapshot → match → plan → policy/approval → durable intent/effects → stage/revalidate → commit/rollback → cleanup/result.
- [ ] Phase deadlines and cancellation follow the corrected lifecycle and commit boundary.
- [ ] Every expected rejection and post-commit state maps to the exhaustive result contract.

**Verification:**

- [ ] Application tests with deterministic fakes pass for every phase and terminal status.

**Dependencies:** Tasks 11-16.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/use_cases/apply_patch.py`
- `tests/unit/features/workspace_editing/application/`

**Estimated scope:** Medium.

### Task 18: Register the Sole Model-Facing Tool and Complete Acceptance Evidence

**Description:** Expose `apply_patch` through the agent runtime and bootstrap composition, then complete acceptance tests, docs, and quality gates.

**Acceptance criteria:**

- [ ] Registration exposes exactly the canonical `{ "input": string }` schema and specified description; provider raw-string repair remains adapter-only.
- [ ] Recoverable rejections continue, success returns normally, and partial/rollback-failed/indeterminate outcomes stop the runtime fatally.
- [ ] All spec acceptance scenarios are traceable to tests; README, specs/ADR indexes, import-linter policy, and platform support notes are current.

**Verification:**

- [ ] End-to-end offline model-tool-loop tests pass.
- [ ] Complete acceptance matrix passes.
- [ ] macOS/Linux CI evidence is recorded.
- [ ] Full quality gate passes.

**Dependencies:** Task 17.

**Files likely touched:**

- Runtime registered-tool adapter/composition
- `src/fabrica/bootstrap/`
- `tests/integration/features/workspace_editing/`
- `tests/integration/features/agent_runtime/`
- `README.md`
- Docs indexes
- `pyproject.toml` if boundary or dependency changes are justified

**Estimated scope:** Medium.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Required POSIX primitives are unavailable or not safely bounded | High | Fail at Checkpoint A; add a dependency or supervised helper only with recorded evidence. |
| Async migration destabilizes existing tools | High | Complete runtime migration and regression tests before starting the new slice. |
| Directory creation contradicts no-mutation preflight language | High | Clarify the lifecycle first; journal and report directory effects explicitly. |
| Current 4,000-character tool-loop bound truncates required evidence | Medium | Introduce typed prioritized bounding before patch result integration. |
| Case/Unicode behavior differs by filesystem | Medium | Probe active filesystem and use identity-based alias tests on both supported platforms. |
| Fault/crash tests become nondeterministic | High | Build explicit fault-injection seams around journal and mutation transitions. |
| Cross-slice adapter imports violate architecture | Medium | Connect slices through published application contracts and bootstrap composition; validate with `lint-imports`. |

## Open Implementation Decisions

There are no unresolved v1 product questions, but Checkpoint A must settle:

- bounded in-process cleanup versus supervised helper-process ownership;
- exact stage/journal placement and protection policy;
- approval UI adapter ownership;
- platform primitive/dependency choice;
- prioritized output-bound policy for complete post-commit evidence.

## Validation Commands

Use focused checks while iterating. Before handoff or PR, run the full local quality gate:

```text
uv run ruff format .
uv run ruff check .
uv run ty check src tests
uv run lint-imports
uv run pytest
```
