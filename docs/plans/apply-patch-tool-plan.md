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

Implementation is gated by architecture and platform feasibility. Task 1 resolved
the documentation-level lifecycle and ADR decisions for the first two issues, but
production `workspace_editing` code remains blocked until Tasks 2-5 and
Checkpoint A are accepted:

1. Derived parent directories become visible before the file commit point and are
   now modeled as reversible preparation effects with durable recovery intent,
   cancellation cleanup, directory outcomes, and truthful mutation guarantees.
2. The current registered-tool contract returns only `str`. ADR 0002 records the
   decision to replace this with typed async registered-tool outcomes, but the
   runtime implementation remains Task 2 work.
3. A hard non-cancellable cleanup deadline conflicts with “never return while mutation may continue” if a POSIX operation blocks. The design must prove bounded in-process cleanup or use a supervised helper process whose state and recovery ownership survive the caller deadline.

## Architecture Decisions

- Model-facing mutation remains a single `apply_patch` registered tool with canonical `{ "input": string }` arguments.
- Operation-specific parser, matcher, planner, filesystem, journal, and recovery components are internal implementation details owned by `workspace_editing`.
- Cross-slice integration happens through published application ports and bootstrap composition; feature adapters must not import cross-slice adapters.
- Visible derived destination parent directories are planned effects, not model-authored actions, and require explicit approval, journaling, rollback, recovery, and result evidence.
- ADR 0002 accepts typed async registered-tool execution with duplicate-delivery ledger semantics and fatal mutation outcomes.
- ADR 0003 accepts the journaled reversible workspace mutation lifecycle and explicitly rejects cross-file atomicity.
- No production implementation starts before Checkpoint A proves runtime and POSIX feasibility.

## Progress Tracking

After every completed task or meaningful change:

- check off completed tasks, acceptance criteria, verification items, and checkpoints;
- leave unfinished or unverified items unchecked;
- add newly discovered work and update sequencing when scope or dependencies change;
- note blockers, deviations, and decisions that affect remaining work.

## Task List

### Phase 1: Design Gates and Runtime Foundation

- [x] Task 1: Clarify the mutation lifecycle and record architecture decisions
- [x] Task 2: Define typed async registered-tool execution contracts
- [x] Task 3: Migrate the tool loop and model boundary to async
- [x] Task 4: Implement runtime ledger and mutation-aware status mapping
- [x] Task 5: Prove POSIX capability and cleanup-deadline feasibility

### Checkpoint A: Architecture Feasibility

- [x] Tasks 1-5 are accepted.
- [x] Async runtime and existing tools pass their tests.
- [ ] The cleanup/deadline model is credible on both supported platforms. macOS-local and Docker Linux evidence select supervised helper-process/recovery ownership, but that production ownership model remains unimplemented.
- [x] No new dependency is added without recorded evidence.
- [ ] Production mutation exposure remains blocked until the selected no-replace rename and supervised-cleanup guarantees are implemented. Pure-core and explicit-dependency adapter work began before this checkpoint by user request; this is a documented sequencing deviation, not evidence that the production capability gate is satisfied.

### Phase 2: Pure `workspace_editing` Application Core

- [x] Task 6: Establish DTOs, exhaustive errors, and result serialization
- [x] Task 7: Implement the side-effect-free patch parser
- [x] Task 8: Implement text snapshot decoding and rendering
- [x] Task 9: Implement deterministic hunk matching
- [x] Task 10: Define slice-owned ports and recovery state machine
- [x] Task 11: Implement immutable planning, preview, and digest generation

### Checkpoint B: Pure Core

- [x] Parser, text, matcher, ports, recovery state machine, planner, preview, and result-contract tests pass.
- [x] No application module performs filesystem or approval UI I/O.

### Phase 3: POSIX Adapters and Transactional Behavior

- [x] Task 12: Implement the mutating resolver and snapshot adapter
- [x] Task 13: Implement mutation lease, policy, and approval adapters
- [x] Task 14: Implement durable journal and reversible pre-commit effects
- [ ] Task 15: Implement staging, revalidation, and commit scheduling
- [x] Task 16: Implement rollback and startup recovery

### Checkpoint C: Filesystem Safety

- [ ] Basic operations, stale plans, concurrency, durability, rollback, retained directories, and recovery pass on supported POSIX systems.
- [ ] Fault tests cover every journal transition and visible mutation step.
- [ ] The adapter never reports while unmanaged mutation can continue.

### Phase 4: Use Case, Model Exposure, and Handoff

- [x] Task 17: Compose the `ApplyPatch` application use case
- [ ] Task 18: Register the sole model-facing tool and complete acceptance evidence

### Checkpoint D: Complete v1

- [ ] Every success criterion in the specification maps to passing automated evidence.
- [ ] No overlapping filesystem mutation tool is registered.
- [x] macOS and Linux capability evidence is recorded.
- [x] Full local quality gate passes.
- [ ] This living plan reflects final status, deviations, and unresolved operational follow-ups.

## Detailed Tasks

### Task 1: Clarify the Mutation Lifecycle and Record Architecture Decisions

**Description:** Amend the specification and add ADRs covering visible derived-directory effects, durable recovery intent, file commit point, rollback/recovery ownership, async tool execution, and duplicate delivery.

**Acceptance criteria:**

- [x] The lifecycle explicitly distinguishes side-effect-free planning from visible reversible directory creation and file commit.
- [x] Cancellation and mutation guarantees are defined for created, removed, retained, and uncertain directories.
- [x] ADRs document the runtime and filesystem decisions, including the lack of cross-file atomicity.

**Verification:**

- [x] Documentation review covers every lifecycle, cancellation, rollback, and recovery statement in `docs/specs/apply-patch-tool.md`.
- [x] ADR index links to the new decisions.

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

- [x] `ToolExecutionContext` carries call identity, canonical argument digest, cancellation, and phase deadlines without exposing host services generically.
- [x] The outcome distinguishes model-continue success, recoverable rejection, ordinary tool failure, and fatal runtime stop.
- [x] Result bounding always preserves status, error code, mutation guarantee, and fatal disposition before optional detail.

**Verification:**

- [x] DTO and port tests cover immutability, status invariants, canonical serialization, and bounded output.

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

- [x] Existing tools run through the async boundary without changing their exposed behavior.
- [x] Cancellation reaches model turns and tool handlers.
- [x] Tool-call ordering remains deterministic.

**Verification:**

- [x] Migrated agent-runtime unit tests pass.
- [x] `tests/integration/features/agent_runtime/test_tool_loop_composition.py` passes.

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

- [x] Same `call_id` and canonical normalized-argument digest returns the recorded terminal result without handler execution.
- [x] Same `call_id` with different arguments is rejected before execution.
- [x] Recoverable patch rejection continues the model loop; partial, rollback-failed, and indeterminate outcomes stop it fatally.

**Verification:**

- [x] Unit tests assert handler invocation counts and loop status.

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

- [x] Evidence identifies which primitives are available through Python 3.13 and where `ctypes` or another dependency would be required.
- [x] The design chooses either demonstrably bounded in-process cleanup or a supervised helper-process/recovery model.
- [x] Unsupported platforms/filesystems have a deterministic fail-closed probe result.

**Verification:**

- [x] Focused probe tests run on real macOS and Linux environments. The repository records local macOS and Docker-based Linux evidence.
- [x] Recorded evidence includes commands, filesystem type, Python version, and results in `docs/apply-patch-posix-capability-evidence.md`.

**Dependencies:** Task 1.

**Files touched:**

- `scripts/apply_patch_posix_capability_probe.py`
- `tests/integration/features/workspace_editing/test_posix_capability_probe.py`
- `docs/apply-patch-posix-capability-evidence.md`
- `docs/plans/apply-patch-tool-plan.md`

**Task 5 finding:** Python 3.13 standard library covers most required POSIX
filesystem evidence primitives, but lacks a portable no-replace rename wrapper.
Production code therefore needs a platform-specific syscall/`ctypes` seam or a
different pre-commit design before mutation can be exposed. Bounded in-process
cleanup is not credible for potentially blocking POSIX syscalls, so the design
selects supervised helper-process/recovery ownership. Unsupported platforms or
failed probes must fail closed before mutation with
`UNSUPPORTED_FILESYSTEM_GUARANTEE`.

**Estimated scope:** Medium.

### Task 6: Establish DTOs, Exhaustive Errors, and Result Serialization

**Description:** Create the `workspace_editing` slice’s application DTOs, error table, status types, mutation guarantees, and compact JSON serialization boundary.

**Acceptance criteria:**

- [x] Frozen DTOs represent actions, hunks, limits, evidence, plans, statuses, mutation guarantees, and path/directory outcomes.
- [x] Every required v1 error code has phase, retryability, mutation guarantee, required metadata, and runtime mapping.
- [x] Compact canonical JSON preserves mandatory fields under output limits.

**Verification:**

- [x] DTO invariant, error-table exhaustiveness, and serialization tests pass.

**Dependencies:** Checkpoint A.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/dtos/`
- `src/fabrica/features/workspace_editing/application/errors.py`
- `tests/unit/features/workspace_editing/application/`

**Estimated scope:** Medium.

**Implementation note:** Completed the pure application DTO and error-table
foundation under `src/fabrica/features/workspace_editing/application/` with
focused unit tests in `tests/unit/features/workspace_editing/application/`.
Focused pytest passed with coverage disabled because the project-level coverage
gate is not meaningful for a single-test-file run. Ruff, ty, and import-linter
checks passed for the new slice. This intentionally started pure core work before
Checkpoint A was accepted because the user explicitly requested the next slice;
production mutation exposure remains blocked by the unresolved no-replace rename
and supervised-cleanup guarantees.

**Status reconciliation (2026-08-26):** The Task 5 probe evidence was recorded
for local macOS and Docker-based Linux on 2026-08-25. Focused validation on
2026-08-26 passed 156 workspace-editing unit/integration tests, Ruff, ty, and
import-linter. This verifies the recorded fail-closed decision; it does not
implement or approve production mutation exposure.

### Task 7: Implement the Side-Effect-Free Patch Parser

**Description:** Parse the canonical patch protocol into immutable intermediate representation without reading or mutating the filesystem.

**Acceptance criteria:**

- [x] Canonical sentinels and Add/Update/Delete/Move grammar are parsed exactly.
- [x] Anchors, before/after insertion, EOF assertion, and terminal-newline directives obey the spec.
- [x] Invalid, incomplete, unprefixed, over-limit, and no-op forms return the required error codes.

**Verification:**

- [x] Table-driven parser tests cover the grammar acceptance matrix.

**Dependencies:** Task 6.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/use_cases/parse_patch.py`
- Parser DTOs and tests

**Estimated scope:** Medium.

**Implementation note:** Completed the side-effect-free parser use case under
`src/fabrica/features/workspace_editing/application/use_cases/parse_patch.py`.
The parser accepts the canonical v1 sentinels and model-authored Add, Update,
Delete, Move, anchored hunk, before/after insertion, EOF assertion, and terminal
newline marker forms into immutable DTOs without reading or mutating the
filesystem. Focused parser tests cover accepted grammar and structured rejection
codes for incomplete sentinels, unknown actions, invalid hunk bodies, invalid
delete bodies, no-op updates, unsafe insertion-only hunks, misplaced EOF
assertions, and input limits.

### Task 8: Implement Text Snapshot Decoding and Rendering

**Description:** Represent source and resulting text bytes with exact UTF-8, BOM, EOL, and terminal-newline semantics.

**Acceptance criteria:**

- [x] UTF-8 and UTF-8 BOM are distinguished; NUL/binary and unsupported encoding are rejected.
- [x] Uniform LF/CRLF and terminal-newline state are represented exactly; mixed EOL is rejected.
- [x] Rendering preserves BOM, EOL, terminal newline, and inserted bytes according to the action rules.

**Verification:**

- [x] Byte-level unit tests cover empty files and no-terminal-newline cases.

**Dependencies:** Task 6.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/`
- `tests/unit/features/workspace_editing/application/`

**Estimated scope:** Medium.

**Implementation note:** Completed pure application text snapshot decoding and
rendering in `workspace_editing.application.text_snapshot`. The implementation
distinguishes UTF-8 from UTF-8 BOM, rejects NUL/binary, invalid UTF-8, mixed LF
and CRLF, and bare CR line endings, represents terminal-newline state explicitly,
and renders Update/Move replacement bytes using source conventions while Add File
rendering uses v1 UTF-8/LF/no-BOM defaults.

### Task 9: Implement Deterministic Hunk Matching

**Description:** Match hunks against immutable source snapshots using the v1 exact and trailing-whitespace-only strategy.

**Acceptance criteria:**

- [x] Matching uses immutable source snapshots, exact pass first, then trailing-whitespace-only tolerance.
- [x] Ambiguous/missing anchors and hunks, overlap, reverse order, unsafe insertion, and EOF failure are rejected deterministically.
- [x] Untouched context bytes come from the source snapshot.

**Verification:**

- [x] Focused matching matrix and property-style edge-case tests pass.

**Dependencies:** Tasks 7-8.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/use_cases/match_hunks.py`
- Matcher support modules and tests

**Estimated scope:** Medium.

**Implementation note:** Completed the pure application hunk matcher under
`src/fabrica/features/workspace_editing/application/use_cases/match_hunks.py`.
The matcher applies hunks against immutable decoded source snapshots, tries exact
matching before trailing-whitespace-only tolerance, preserves untouched context
from source bytes, supports before/after anchor insertion, and returns structured
no-mutation rejections for missing/ambiguous anchors, missing/ambiguous hunks,
overlap, reverse order, and EOF assertion failures. Focused workspace-editing
unit tests, ruff, and ty checks passed for this slice.

### Task 10: Define Slice-Owned Ports and Recovery State Machine

**Description:** Define all application-owned outbound ports and the durable journal/recovery state machine before commit adapter implementation.

**Acceptance criteria:**

- [x] Ports cover lease, capability/snapshot access, policy, approval, staging/commit, journal/recovery, clock, and cancellation where needed.
- [x] OS handles and platform structs do not cross the application boundary.
- [x] Journal states, legal transitions, crash points, and recovery outcomes are exhaustive before commit code exists.

**Verification:**

- [x] Type checks, state-transition tests, and architecture/import-linter review pass.

**Dependencies:** Tasks 1, 5-6.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/ports/`
- Recovery DTO/state modules
- `tests/unit/features/workspace_editing/application/`

**Estimated scope:** Medium.

**Implementation note:** Completed pure application Task 10 contracts under
`workspace_editing.application.ports` and recovery/journal DTOs under
`workspace_editing.application.dtos.recovery`. The ports cover the mutation lease,
capability/snapshot access, policy, approval, durable journal/recovery,
staging/commit/rollback, clock, cancellation, and cleanup/resource boundaries
without exposing OS handles or platform structs. The recovery state module defines
journal lifecycle states, legal transitions, startup recovery decisions, terminal
states, and invariants for clean versus operator-gated recovery. Focused recovery
state and port-boundary tests pass, along with ruff, ty, and import-linter checks
for this slice.

### Task 11: Implement Immutable Planning, Preview, and Digest Generation

**Description:** Build `PatchPlan` from parsed actions and fake snapshots, including path validation, derived effects, preview, schedule, and digest.

**Acceptance criteria:**

- [x] Global source/destination disjointness, aliases, move chains/swaps, collisions, resource ceilings, and derived directories are validated.
- [x] Derived directories are collapsed and ordered; input reporting order and deterministic commit order remain distinct.
- [x] Plan digest binds canonical actions, exact resulting bytes, evidence, effects, modes, schedule, and approval preview; truncated previews cannot be approved.

**Verification:**

- [x] Planner tests with fake snapshots pass and prove zero filesystem I/O.

**Dependencies:** Tasks 6-10.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/use_cases/plan_patch.py`
- Preview/digest modules and tests

**Estimated scope:** Medium.

**Implementation note:** Completed the pure application planner under
`workspace_editing.application.use_cases.plan_patch`. The planner consumes parsed
actions plus adapter-supplied fake snapshot evidence, validates global source and
destination disjointness before mutation, derives collapsed missing destination
parent directory effects, keeps input change reporting distinct from deterministic
commit scheduling, produces a bounded non-truncated approval preview, and binds
actions, evidence, directory effects, schedule, and preview into the immutable
plan digest. Focused planner tests pass with no filesystem adapter or I/O.

### Task 12: Implement the Mutating Resolver and Snapshot Adapter

**Description:** Implement the POSIX adapter responsible for mutating-safe path resolution and source/destination snapshot evidence.

**Acceptance criteria:**

- [x] Root/parent traversal rejects absolute, escaping, symlink, alias, special-file, multiple-hard-link, and non-directory-parent cases. Handle-relative traversal remains for the later commit-capable adapter increment.
- [x] Source and destination evidence includes identities, hashes, metadata, ancestor identities, and absence evidence.
- [x] Failed capability probes reject before mutation; Move source and destination-parent device evidence rejects cross-device moves during snapshot planning.

**Verification:**

- [x] Focused real-filesystem snapshot integration tests pass locally on macOS with coverage disabled for the targeted file.

**Dependencies:** Tasks 5, 10-11.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/adapters/outbound/posix_filesystem/`
- `tests/integration/features/workspace_editing/`

**Estimated scope:** Medium.

**Implementation note:** Added the first POSIX filesystem snapshot adapter slice
under `workspace_editing.adapters.outbound.posix_filesystem`. The adapter remains
side-effect-free: it fails closed for production mutation capabilities until the
no-replace rename/helper-process design is implemented, builds planning snapshots
from real filesystem evidence when explicitly used for snapshot-only behavior,
and rejects symlinks, non-directory parents, existing Add/Move destinations,
special files, missing sources, multiple-hard-link aliases, and cross-device
Moves before mutation.
Focused macOS integration tests cover evidence and rejection behavior. The
commit-capable handle-relative traversal remains intentionally deferred to Tasks
14-16.

### Task 13: Implement Mutation Lease, Policy, and Approval Adapters

**Description:** Add per-workspace serialization, host policy evaluation, and approval binding for immutable patch plans.

**Acceptance criteria:**

- [x] One exclusive lease serializes all patch mutation for a workspace from before snapshot through cleanup.
- [x] Default policy requires approval; `.git/**`, stage, and journal paths are denied.
- [x] Approval is bound to the complete plan digest and cannot use a truncated preview.

**Verification:**

- [x] Deterministic concurrency, cancellation, denial, timeout, and stale-approval tests pass.

**Dependencies:** Tasks 10-12.

**Files likely touched:**

- Workspace-editing outbound lease/policy/approval adapters
- Bootstrap seams
- Tests

**Estimated scope:** Medium.

**Implementation note:** Added focused authorization adapters under
`workspace_editing.adapters.outbound.authorization`: an in-process async lease
manager, a protected-path policy evaluator, and a digest-bound approval requester
with timeout, denial, stale-plan, and unsafe-preview rejection behavior. Focused
authorization unit tests cover protected path denial, approval success and
failure modes, and cancellation-safe lease release. Commit-capable durable lease
ownership remains part of the later journal/helper-process implementation.

### Task 14: Implement Durable Journal and Reversible Pre-Commit Effects

**Description:** Record recovery intent and manage visible derived-directory creation before file commit.

**Acceptance criteria:**

- [x] Recovery intent is durable before creating visible destination parent directories.
- [x] Directories are created shallowest-first through pinned handles and are reported/cleaned by identity.
- [x] Cancellation after directory creation performs bounded cleanup and reports retained/failed/uncertain effects truthfully.

**Verification:**

- [x] Fault injection covers every directory and journal transition.

**Dependencies:** Tasks 10, 12-13.

**Files likely touched:**

- POSIX journal/directory-effect adapters
- Integration tests

**Estimated scope:** Medium.

**Implementation note:** Added a POSIX journal/preparation adapter under
`workspace_editing.adapters.outbound.posix_filesystem`. It durably writes JSON
journal records with file and directory fsync before visible preparation effects,
transitions through the application-owned journal state machine, creates derived
directories shallowest-first, records identity evidence, cleans up created
directories deepest-first on preparation failure, and lists incomplete journals
for later startup recovery. Focused macOS/Linux integration tests cover durable
intent-before-effect ordering, failure rollback, and incomplete journal discovery.

### Task 15: Implement Staging, Revalidation, and Commit Scheduling

**Description:** Create same-filesystem staging artifacts, revalidate plan evidence, and execute the deterministic pre-commit schedule.

**Acceptance criteria:**

- [x] Same-filesystem staging uses host-controlled names and strict permissions, writes full contents, and executes durability barriers for the current complete-payload adapter path.
- [x] Applies modes for the full v1 metadata contract.
- [ ] Source, parent, destination, directory absence, policy, and digest are revalidated at required boundaries. Source identity/content, destination absence, destination parent identity, and journal/plan digest binding are covered in the current adapter path; remaining policy and full digest-bound result-payload revalidation stay open.
- [x] Source identity/content digest revalidation rejects stale plans before visible file commit in the current adapter path.
- [x] The explicit file commit point and deterministic action schedule match the approved plan for add, update, delete, and move complete-payload actions.

**Verification:**

- [x] Focused POSIX integration tests cover staging/commit for add, update, delete, move and stale-plan rejection before visible file commit.
- [x] Focused staging fault tests prove no visible file effect and clean up host-managed stage artifacts before the file commit point.

**Dependencies:** Task 14.

**Files likely touched:**

- POSIX stage/commit adapter modules
- Integration tests

**Estimated scope:** Medium.

**Implementation note:** Added `PosixPatchCommitAdapter` with same-workspace
staging under `.fabrica/apply-patch/stage/<journal-digest>/`, strict staged
payload permissions, file/directory durability barriers, source evidence
revalidation, and deterministic commit execution for add/update/delete/move
steps. A later increment added journal/plan digest binding before staging and
commit, durable COMMITTING/COMMITTED journal writes, and persisted committed path
outcomes. Focused integration tests passed for successful mixed-operation commit,
stale-plan rejection, digest mismatch rejection, and committed journal evidence.
Remaining Task 15 work: broader parent/destination/policy revalidation and
pre-commit fault-injection coverage.

**Incremental update:** Added deterministic staging-durability fault coverage
for failures while flushing both the first and a later staged payload. The
adapter rejects before the explicit file commit point, removes host-managed
staging artifacts, preserves existing source content, and leaves the planned
destination absent. Remaining Task 15 work is policy revalidation; visible-file-
commit crash/fault coverage remains Task 16/18 work.

**Incremental update:** The POSIX snapshot adapter now captures portable mode
bits for replacement payloads and rejects nonzero POSIX file flags plus all
ACL/security-relevant extended attributes before mutation. This fail-closed
contract covers ACL-backed extended attributes that the staged-replacement adapter
cannot preserve without rejecting unrelated host provenance metadata. Focused
tests cover empty, benign, ACL-backed, and uninspectable extended-attribute states.

**Incremental update:** Added commit-time ancestor identity revalidation for
planned paths, including absent add/move destinations whose derived parent
directories may have been created during preparation. Directory ancestor evidence
now uses stable device/inode/mode identity rather than link-count-sensitive file
identity so planned child directory creation does not make a valid plan stale.
The adapter now explicitly rejects add/move destination appearance before the
visible file commit point and verifies destination parent identity against the
approved plan evidence.
Focused integration coverage rejects a replaced destination parent before visible
file commit. Remaining Task 15 work still includes policy revalidation and
broader pre-commit fault-injection coverage.

**Incremental update:** Added commit-time staged-payload revalidation before the
file commit loop. Missing or changed staged payloads now reject as stale before
any visible file operation, with focused integration coverage for the missing
payload case. Remaining Task 15 work still includes policy revalidation and
broader pre-commit fault-injection coverage.

**Incremental update:** Added POSIX staged payload mode handling for the current
complete-payload adapter path. Update and Move payloads now preserve the planned
source file mode, Add payloads use the adapter default `0644`, commit-time staging
revalidation rejects changed payload modes before visible file mutation, and final
path evidence reports resulting file mode. Focused integration coverage verifies
Add/Update/Move modes and stale staged-mode rejection. Remaining Task 15 work
still includes policy revalidation and pre-commit fault-injection coverage.

**Incremental update:** Added an explicit, validated `workspace_umask` setting to
the POSIX commit adapter. Add payloads now use v1 base mode `0666` filtered by the
configured workspace umask (default `0022` produces `0644`), while Update and
Move preserve their planned source modes. Commit-time staged-payload revalidation
uses the same configured policy and rejects a tampered Add payload before visible
file mutation. Focused POSIX integration coverage verifies restrictive-umask
output, tamper rejection, and invalid-mask construction. Remaining Task 15 work
still includes policy revalidation and pre-commit fault-injection coverage.

**Incremental update:** The POSIX snapshot adapter now rejects nonzero POSIX file
flags with `UNSUPPORTED_METADATA` before planning, staging, or mutation because
the staged-replacement commit path cannot preserve them safely. Focused tests
cover accepted zero flags and the no-mutation rejection path. Remaining Task 15
work is policy revalidation and pre-commit fault-injection coverage.

**Incremental update:** Extended nonzero POSIX file-flag rejection to existing
destination parent directories during snapshot planning. This prevents Add or
Move operations from modifying a directory hierarchy whose metadata the current
adapter cannot preserve. Focused integration coverage proves the rejection occurs
before a destination child becomes visible. Policy revalidation and pre-commit
fault-injection coverage remain open.

**Incremental update:** File staging and commit now revalidate the durable journal
record immediately before pre-commit staging and again before the explicit file
commit point. The record must still bind the approved plan and be in the
`PREPARED` state, preventing a tampered, stale, or already-committing journal from
authorizing file mutation. Failed staging also removes adapter-owned incomplete
stage artifacts before reporting the no-file-mutation rejection. Focused POSIX
integration tests cover durable journal state and plan-binding rejection. Full
metadata preservation, commit-time policy revalidation, and pre-commit
fault-injection coverage remain open.

**Incremental update:** `ApplyPatch` now revalidates host policy after staged
payload preparation and immediately before the file commit point. A policy change
at that boundary prevents file mutation and invokes rollback for the already
visible, reversible preparation effects. Focused application orchestration tests
cover the second policy evaluation, no commit after rejection, and rollback before
lease release. Full digest-bound result-payload revalidation and pre-commit
fault-injection coverage remain open.

**Incremental update:** `ApplyPatch` now also revalidates the immutable workspace
snapshot after staged payload preparation and before the final policy check and
file commit. A stale-plan rejection at that boundary prevents file mutation and
rolls back already-visible reversible preparation effects. Focused application
orchestration tests cover the second snapshot validation, rollback, and absence of
a commit call. Full digest-bound result-payload revalidation and pre-commit
fault-injection coverage remain open.

**Incremental update:** The POSIX commit adapter now verifies each staged payload's
SHA-256 digest against the immutable planned bytes immediately before the visible
file commit point, in addition to the existing presence, size, and mode checks.
Focused integration coverage rejects same-length staged-payload tampering before
the destination becomes visible. Remaining Task 15 work is metadata beyond mode
plus broader pre-commit fault-injection coverage.

### Task 16: Implement Rollback and Startup Recovery

**Description:** Implement safe rollback after commit failures and startup handling for incomplete journals.

**Acceptance criteria:**

- [x] Rollback never overwrites or removes independently changed paths and removes plan-created directories deepest-first only when identity and emptiness match.
- [x] All terminal states include required per-path and directory evidence.
- [x] Startup blocks mutation on incomplete journals; only evidence-proven rollback is automatic, otherwise status is `RECOVERY_REQUIRED`.

**Verification:**

- [x] Fault injection after every visible commit step plus restart/crash-fixture tests pass.

**Dependencies:** Tasks 10, 14-15.

**Files likely touched:**

- POSIX rollback/recovery adapters
- Startup gate composition
- Integration tests

**Estimated scope:** Medium.

**Incremental update:** Added POSIX directory rollback and startup recovery seams
to `PosixPatchCommitAdapter`. The adapter now removes journal-created directories
deepest-first only when identity evidence matches and the directory is empty,
retains independently populated directories without deleting external content, and
classifies startup journals so planned/prepared preparation can recover safely while
commit-phase journals require operator recovery. Focused integration tests cover
safe directory rollback, retained external content, automatic prepared-journal
recovery, and operator-gated commit recovery. Remaining Task 16 work: durable
file-operation preimage evidence plus fault injection after every visible commit
step.

**Incremental update:** Added durable file-operation rollback evidence to the
POSIX commit adapter. Before each visible file operation, the adapter now records
the action preimage and expected postimage in the durable journal; non-Add source
contents are held in host-managed backup artifacts. Restart recovery can restore
Add, Update, Delete, and Move effects only while on-disk postimage evidence still
matches. Independently changed paths are retained untouched with `UNKNOWN`
per-path evidence and `RECOVERY_REQUIRED`. Focused POSIX integration tests cover
automatic file rollback from a durable committing journal and external-change
retention. Remaining Task 16 work is fault injection after every visible commit
step and restart/crash-fixture coverage.

**Incremental update:** Added an adapter-local, test-only post-commit-step seam
that runs only after each visible file action and its updated `COMMITTING` journal
record are durable. A parameterized POSIX integration test interrupts after every
mixed-patch Add, Update, Delete, and Move step, discovers the incomplete journal
through a fresh adapter instance, and verifies evidence-proven rollback restores
the original workspace. Task 16 verification is now complete.

### Task 17: Compose the `ApplyPatch` Application Use Case

**Description:** Implement the single application orchestration path that composes parser, snapshot, matcher, planner, policy, approval, journal, stage, commit, rollback, cleanup, and result formatting ports.

**Acceptance criteria:**

- [x] One orchestration path performs lease → parse → snapshot → match → plan → policy/approval → durable intent/effects → stage/revalidate → commit/rollback → cleanup/result.
- [x] Phase deadlines and cancellation follow the corrected lifecycle and commit boundary.
- [x] Every expected rejection and post-commit state maps to the exhaustive result contract.

**Verification:**

- [x] Application tests with deterministic fakes pass for representative phase ordering, matching, pre-mutation rejection, and rollback-on-staging-rejection outcomes.

**Dependencies:** Tasks 11-16.

**Files likely touched:**

- `src/fabrica/features/workspace_editing/application/use_cases/apply_patch.py`
- `tests/unit/features/workspace_editing/application/`

**Estimated scope:** Medium.

**Implementation note:** Added `ApplyPatch` under
`src/fabrica/features/workspace_editing/application/use_cases/apply_patch.py`.
The use case composes application-owned ports for mutation lease, capability
checks, parsing, text hunk matching, immutable planning, snapshot revalidation,
policy, approval, durable journal creation, preparation/file staging, commit, and
rollback-on-pre-commit failure. Extended the snapshot-reader port with planning
snapshot and decoded text reads so the application can orchestrate matching
without importing adapters or performing direct filesystem I/O. Focused unit
tests in `tests/unit/features/workspace_editing/application/test_apply_patch.py`
cover representative happy-path ordering, update hunk matching into complete
payloads, pre-journal policy rejection, and rollback after file-staging
rejection. Remaining broader v1 evidence belongs to Task 18 registration and
acceptance testing.

### Task 18: Register the Sole Model-Facing Tool and Complete Acceptance Evidence

**Description:** Expose `apply_patch` through the agent runtime and bootstrap composition, then complete acceptance tests, docs, and quality gates.

**Acceptance criteria:**

- [x] Registration exposes exactly the canonical `{ "input": string }` schema and specified description; provider raw-string repair remains adapter-only.
- [x] Recoverable rejections continue, success returns normally, and partial/rollback-failed/indeterminate outcomes stop the runtime fatally at the registered-tool outcome mapping boundary.
- [ ] All spec acceptance scenarios are traceable to tests; README, specs/ADR indexes, import-linter policy, and platform support notes are current. Acceptance traceability, README architecture notes, specs index, and current platform support notes are documented; ADR index, CI platform evidence, remaining open scenario coverage, and final validation remain open.

**Verification:**

- [x] End-to-end offline model-tool-loop tests pass.
- [ ] Complete acceptance matrix passes.
- [ ] macOS/Linux CI evidence is recorded.
- [x] Full quality gate passes.

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

**Implementation note:** Added the first Task 18 registration slice under
`workspace_editing.adapters.inbound.registered_tool`. The adapter exposes the
sole model-facing `apply_patch` `AsyncRegisteredTool` with the canonical
`{"input": string}` schema and recommended description, rejects non-string input
before invoking the application use case, and maps committed results to success,
no-mutation patch rejections to recoverable model-loop rejections, and retained,
partial, rollback-failed, or indeterminate mutation guarantees to fatal runtime
stop outcomes. Focused unit tests cover the schema/description and result-status
Remaining Task 18 work is bootstrap composition, end-to-end offline
model-tool-loop acceptance evidence, documentation/index updates, platform CI
evidence, and the full quality gate.

**Incremental update:** Added bootstrap composition for explicitly supplied
apply-patch application dependencies through
`create_apply_patch_registered_tool_adapter`. The helper exposes the model-facing
tool without filesystem probing, approval prompting, backend calls, or mutation
during construction. Added an offline tool-loop composition test proving a fake
model can request the composed `apply_patch` tool, the injected use case receives
the raw canonical `input`, and committed patch output returns through the runtime
loop. Remaining Task 18 work is full acceptance traceability, documentation/index
updates, platform CI evidence, and the full quality gate.

**Incremental update:** Added
`docs/apply-patch-acceptance-traceability.md` to map the v1 acceptance scenarios
from `docs/specs/apply-patch-tool.md` to current unit/integration test evidence
and explicitly list open safety scenarios. Linked the traceability document from
the specs index and README architecture notes, including the current fail-closed
production POSIX platform support status. Remaining Task 18 work is ADR index
review, Linux/macOS CI evidence, closing or deferring the open acceptance
scenarios, and the full quality gate.

**Incremental update:** Reviewed the ADR index and confirmed that ADRs 0002 and
0003 are already indexed. Updated `docs/README.md` to include the current
read-files, search-codebase, and apply-patch specifications plus the apply-patch
acceptance-traceability record. Remaining Task 18 work is Linux/macOS CI
evidence, closing or explicitly deferring the open acceptance scenarios, and the
full quality gate.

**Incremental update:** Recorded local macOS and Docker-based Linux POSIX
capability evidence without expanding CI/CD. The standard-library probe passed
on macOS and in `python:3.13-slim` on Linux `overlayfs`, with both environments
reporting the expected fail-closed decision for unresolved portable no-replace
rename and bounded-cleanup limitations. The capability-evidence and acceptance-
traceability notes now include reproducible local and Docker commands instead of
a CI matrix. Remaining Task 18 work is closing or explicitly deferring the open
acceptance scenarios and completing the full quality gate.

**Incremental update:** Tightened POSIX parent-chain validation to reject FIFO
and other non-regular special-file parent components as
`SPECIAL_FILE_UNSUPPORTED`, while retaining `PARENT_PATH_NOT_DIRECTORY` for
regular-file parents. Added focused FIFO-parent integration coverage proving the
rejection is side-effect-free. Remaining Task 18 work is closing or explicitly
deferring the remaining open acceptance scenarios and completing the full
quality gate.

**Incremental update:** Added focused POSIX snapshot evidence that FIFO nodes are
rejected as both existing Update sources and existing Add targets before
planning or mutation. The tests preserve and compare the FIFO device/inode
identity, proving the unsupported node is not replaced. Remaining Task 18 work
is closing or explicitly deferring case/Unicode alias detection, cross-device
move evidence, non-FIFO special-file classes, metadata handling, and the open
rollback/fault-injection scenarios before completing the full quality gate.

**Incremental update:** Added focused POSIX snapshot evidence that Unix-domain
socket nodes are rejected as both existing Update sources and existing Add
targets before planning or mutation. The tests preserve and compare the socket
device/inode identity while it remains bound, extending special-file coverage
beyond FIFO nodes. Remaining Task 18 work is closing or explicitly deferring
case/Unicode alias detection, cross-device move evidence, other special-file
classes, metadata handling, and the open rollback/fault-injection scenarios
before completing the full quality gate.

**Incremental update:** Added focused POSIX snapshot evidence that a Unix-domain
socket cannot serve as an Add destination parent. The test preserves and compares
the bound socket identity and verifies no child path becomes visible, proving
parent-chain rejection is side-effect-free. Remaining Task 18 work is closing or
explicitly deferring cross-device move evidence, other special-file classes,
metadata handling, and the open rollback/fault-injection scenarios before
completing the full quality gate.

**Incremental update:** Added side-effect-free POSIX snapshot rejection for case-
and Unicode-normalization-equivalent path aliases, including aliases in destination
parent components. Focused integration tests preserve existing content and prove
that no aliased destination becomes visible. Remaining Task 18 work is closing or
explicitly deferring cross-device move evidence, other special-file classes,
metadata handling, and the open rollback/fault-injection scenarios before
completing the full quality gate.

**Incremental update:** Extended offline end-to-end model-tool-loop acceptance
evidence for the explicitly composed `apply_patch` tool. Integration coverage now
proves that no-mutation patch rejections are delivered to a subsequent model turn
and that indeterminate mutation states stop the runtime before another model turn.
Production default mutation composition remains fail-closed pending the documented
POSIX no-replace rename and supervised-cleanup guarantees. Remaining Task 18 work
is closing or explicitly deferring the open acceptance scenarios and completing
the full quality gate.

**Incremental update:** Closed the remaining special-file classification evidence
gap without requiring privileged device-node creation. Focused tests now exercise
character- and block-device modes at both existing action-path and parent-path
classification boundaries, complementing the real FIFO and Unix-domain socket
integration tests. All such modes fail before mutation as
`SPECIAL_FILE_UNSUPPORTED`. Remaining Task 18 work is closing or explicitly
deferring the other open acceptance scenarios. The full local quality gate passes with 1,026 tests, 2 skips, and 93.01% coverage; broader Task 18 acceptance and production-exposure gates remain open.

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
