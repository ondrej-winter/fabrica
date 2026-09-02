# Implementation Plan: Complete Production `apply_patch` Enablement

## Status

- Readiness: **AP-01 complete; ready for AP-02 native-operation implementation**.
  Production mutation remains fail-closed until AP-02 and AP-03 prove the
  selected native no-replace backend and supervised helper ownership design for
  the actual workspace.
- Created: September 1, 2026.
- Source specification: `docs/specs/tools-apply-patch-tool-spec.md`.
- Scope: remaining work only. The existing `workspace_editing` parser, matcher,
  planner, authorization, journaling, commit/rollback, registered-tool adapter,
  and associated tests are already substantially implemented.

## Current Gap Assessment

The feature is intentionally fail-closed in production. The primary blocker is
`PosixPatchWorkspaceSnapshotAdapter.verify_workspace_capabilities()`: its
default configuration rejects production mutation because the current adapter
does not yet prove two required guarantees:

1. Native, no-replace POSIX destination creation/rename semantics.
2. Supervised ownership of potentially blocking commit and cleanup work, so the
   host never returns while unmanaged mutation may continue.

The current bootstrap helper accepts an injected `PatchApplier`; it does not
assemble production dependencies, perform startup recovery, or bind the runtime
execution context's cancellation and phase deadlines to the patch lifecycle.

The public tool schema also needs to be reconciled with the accepted 256 KiB
patch-input limit and the generic runtime's lower string-argument limit.

## Scope and Non-Goals

### In scope

- Capability-proven POSIX production enablement. Apple Silicon macOS is the
  primary, release-blocking v1 target. Linux is required support work but does
  not block the primary macOS release; incomplete Linux support must be
  documented and fail cleanly.
- Native no-replace operations, descriptor-rooted mutation safety, supervised
  commit ownership, runtime deadline/cancellation propagation, recovery gating,
  production bootstrap composition, and acceptance coverage.
- Before native code is added, a reviewable decision must prove the selected
  platform backend and helper-process ownership architecture against the accepted
  specification. Unsupported combinations remain fail-closed.
- Positive runtime capability evidence for the actual workspace is the sole
  authority for mutation enablement. Platform or filesystem names alone never
  enable production mutation.

### Out of scope

- Windows support, fallback best-effort mutation, fuzzy matching, non-UTF-8
  editing, symlink mutation, automatic patch retries, cross-device moves, and
  new public filesystem mutation tools.

## Progress Tracking

- [x] AP-01 Define and approve production capability evidence, native-operation boundaries, and helper ownership architecture.
- [ ] AP-02 Implement descriptor-rooted native no-replace mutation operations.
- [ ] AP-03 Implement supervised helper-process commit and cleanup ownership.
- [ ] AP-04 Propagate runtime cancellation and phase deadlines into patch execution.
- [ ] AP-05 Add startup recovery orchestration and workspace mutation gating.
- [ ] AP-06 Add explicit production bootstrap composition.
- [ ] AP-07 Align the public schema and runtime argument bounds with the spec.
- [ ] AP-08 Add production-path integration and acceptance tests.
- [ ] AP-09 Update documentation and run the full quality gate.

Keep these checkboxes current during implementation. After every completed task
or meaningful scope change, update its detailed status, acceptance criteria,
verification evidence, blockers, and any newly discovered work.

## Dependency Order

```text
AP-01 approved capability and ownership design
  -> AP-02 native no-replace operations
    -> AP-03 supervised helper ownership
      -> AP-04 cancellation/deadlines
      -> AP-05 startup recovery gate
        -> AP-06 production composition
          -> AP-07 runtime-bound alignment
            -> AP-08 composed-runtime acceptance tests
              -> AP-09 documentation and full validation
```

AP-02 and AP-03 are the production critical path. Do not relax the current
fail-closed default until both are complete and tested.

## Ordered Tasks

### AP-01 — Define production capability evidence, native-operation boundaries, and helper ownership architecture

**Status: Complete (2026-09-02).** ADR 0009 records the selected macOS and
Linux backend boundaries plus the per-operation supervised-helper protocol.
Adapter-private actual-workspace evidence now records platform, architecture,
filesystem/device, selected backend, and primitive-level unsupported or failed
reasons. It remains intentionally fail-closed until AP-02 and AP-03 prove the
native and helper primitives.

**Likely files**

- `src/fabrica/features/workspace_editing/application/ports/workspace_mutation.py`
- New narrow modules under
  `src/fabrica/features/workspace_editing/adapters/outbound/posix_filesystem/`
- `scripts/apply_patch_posix_capability_probe.py`
- Matching unit and integration tests.

**Work**

1. Record an adapter-private backend design for pinned directory traversal,
   no-follow operations, no-replace destination creation, durability barriers,
   and supervised mutation execution. Identify the exact native primitive(s),
   FFI/binding signatures or other binding mechanism, supported platform and
   filesystem scope, and every explicit fail-closed condition.
2. Record whether the helper is a short-lived per-operation process or another
   supervised model; define its parent/child terminal-state protocol, durable
   evidence required before the first visible effect, IPC-loss behavior,
   cancellation/deadline behavior, termination proof, and recovery handoff.
   Add an ADR before implementation if this durable native/helper architecture
   is not already covered by an accepted ADR.
3. Replace the current boolean production gate with structured capability
   evidence that records platform, filesystem/device, required primitives, the
   selected backend, and explicit unsupported reasons.
4. Preserve fail-closed behavior whenever any required primitive is unavailable.
5. Treat Apple Silicon macOS as the primary release target. Investigate Linux in
   the same design, but record any unproven Linux platform/filesystem/backend
   combination as clearly unsupported rather than delaying the macOS release.

**Acceptance criteria**

- [x] A reviewable backend and helper-ownership decision exists before native code
      is added. It explicitly labels each candidate platform as guaranteed or
      unsupported.
- [x] Production enablement depends on verified backend capability evidence, not
       merely on macOS/Linux detection, filesystem naming, or a feature flag.
- [x] Unsupported platform/filesystem/backend combinations return
      `UNSUPPORTED_FILESYSTEM_GUARANTEE` before mutation.
- [x] Capability evidence is collected against the actual workspace and records
      enough platform, filesystem/device, primitive, backend, and probe-failure
      detail to explain unsupported status and guide an operator.

**Verification**

- [x] Capability-probe tests cover supported, unsupported, and failed probes.
- [x] Existing fail-closed snapshot tests still pass.

### AP-02 — Implement descriptor-rooted native no-replace mutation operations

**Likely files**

- `src/fabrica/features/workspace_editing/adapters/outbound/posix_filesystem/adapter.py`
- `src/fabrica/features/workspace_editing/adapters/outbound/posix_filesystem/commit.py`
- `src/fabrica/features/workspace_editing/adapters/outbound/posix_filesystem/journal.py`
- New platform modules such as `native_operations.py`, `descriptor_paths.py`,
  and platform-specific no-replace bindings.
- POSIX integration tests.

**Work**

1. Implement the smallest native binding necessary for no-replace destination
   semantics: Linux `renameat2(..., RENAME_NOREPLACE)` where available, and a
   macOS equivalent only if it proves the required guarantee.
2. Move mutation-sensitive traversal and file operations to descriptor-rooted,
   no-follow behavior.
3. Revalidate source, destination, parent, planned-directory absence, identity,
   and policy evidence immediately before the commit point.
4. Forbid fallback to ordinary rename/replace APIs where no-replace semantics
   are required.

**Acceptance criteria**

- [ ] Add and Move never overwrite paths created after planning.
- [ ] Parent replacement, symlink substitution, source changes, and destination
      races reject safely.
- [ ] Journal updates remain durable before every visible effect.

**Verification**

- [ ] Fault-injection/race tests cover destination creation and parent changes
      after approval.
- [ ] Existing POSIX commit, snapshot, and journal integration suites pass.

### Checkpoint A — Native safety proof

- [ ] The selected local POSIX backend passes the complete required capability
      probe, including no-replace semantics.
- [ ] No unsafe fallback path remains reachable in production composition.

### AP-03 — Implement supervised helper-process commit and cleanup ownership

**Likely files**

- New helper-process modules under
  `src/fabrica/features/workspace_editing/adapters/outbound/posix_filesystem/`
- `commit.py` and `journal.py` in the same adapter package.
- Related tests; reuse established helper-process patterns from
  `workspace_reading` only through local adaptation, not cross-slice adapter
  imports.

**Work**

1. Create a bounded parent/helper protocol for preparation, commit, rollback,
   and terminal-state evidence.
2. Have the helper reopen and validate durable plan/journal state rather than
   trusting process-memory state alone.
3. After runtime cancellation, caller disconnect, or deadline expiry, keep the
   helper responsible until it finishes or rolls back to a journaled terminal
   state. The parent returns a clear non-success pending/uncertain result until
   it can prove that terminal outcome.
4. Ensure no helper can continue mutating after the host reports a terminal
   outcome.

**Acceptance criteria**

- [ ] Timeout or cancellation after derived-directory creation never reports
      `no_mutation` unless cleanup is proven.
- [ ] Communication loss, helper crash, and uncertain termination yield
      `INDETERMINATE_COMMIT_STATE` or `RECOVERY_REQUIRED` as appropriate.
- [ ] The parent never reports successful mutation before it has journal-backed
       evidence of the helper's terminal result.
- [ ] Rollback retains externally changed directories/files and reports their
      per-path outcomes.

**Verification**

- [ ] Deterministic tests cover normal commit, helper crash, timeout before and
      after commit point, communication loss, successful rollback, and failed or
      retained cleanup.

### AP-04 — Propagate runtime cancellation and phase deadlines

**Likely files**

- `src/fabrica/features/workspace_editing/adapters/inbound/registered_tool/adapter.py`
- `src/fabrica/features/workspace_editing/application/use_cases/apply_patch.py`
- `src/fabrica/features/workspace_editing/application/ports/workspace_mutation.py`
- Patch DTOs and focused tests as needed.

**Work**

1. Stop discarding `ToolExecutionContext` in the registered-tool adapter.
2. Adapt its cancellation signal and phase deadlines to patch-owned ports and
   phase checks for lease/planning, approval, staging, commit, and rollback.
3. Map deadline expiry to stable patch result codes and fatality guarantees.

**Acceptance criteria**

- [ ] Runtime cancellation and deadlines affect the actual patch lifecycle.
- [ ] Pre-visible-effect timeout is a recoverable, no-mutation result.
- [ ] Post-commit-point uncertainty is fatal and never downgraded to rejection.

**Verification**

- [ ] Deterministic clock/cancellation unit tests cover every phase.
- [ ] Tool-loop integration tests verify outcome status and runtime disposition.

### AP-05 — Add startup recovery orchestration and workspace mutation gating

**Likely files**

- New use case under
  `src/fabrica/features/workspace_editing/application/use_cases/`
- `application/ports/workspace_mutation.py`
- POSIX journal/commit adapters.
- Bootstrap composition and integration tests.

**Work**

1. Define the bootstrap-owned startup contract: discover incomplete journals
   before tool exposure, inspect durable evidence, perform only proven-safe
   rollback, persist the final recovery state, and return structured startup
   gating evidence when mutation cannot be enabled.
2. Gate registered-tool exposure for workspaces with unresolved recovery without
   preventing unrelated read-only tools from being composed.
3. Make recovery deterministic when more than one incomplete journal exists.
4. Emit stable structured mutation-disabled status with
   `UNSUPPORTED_FILESYSTEM_GUARANTEE` for failed capability proof and
   `RECOVERY_REQUIRED` for unresolved recovery. Include diagnostic capability or
   journal evidence and operator guidance as metadata.

**Acceptance criteria**

- [ ] An unresolved incomplete journal prevents `apply_patch` from being exposed
      for that workspace.
- [ ] Recovery never resumes forward commit.
- [ ] Recovery only removes plan-created directories when identity and emptiness
      prove that removal is safe.
- [ ] A recovery-blocked host retains read-only tools and reports
       `RECOVERY_REQUIRED` with structured recovery guidance.

**Verification**

- [ ] Integration fixtures cover each recoverable and unrecoverable journal
      state, including external modifications.

### Checkpoint B — Recovery-gated mutation lifecycle

- [ ] A capability-proven workspace performs startup recovery before public
      mutation registration.
- [ ] The recovery gate unblocks only after safe terminal evidence exists.

### AP-06 — Add explicit production bootstrap composition

**Likely files**

- `src/fabrica/bootstrap/composition/workspace_editing.py`
- `src/fabrica/bootstrap/composition/__init__.py`
- `src/fabrica/bootstrap/__init__.py`
- Settings/options DTOs in the owning layer.
- Composition integration tests.

**Work**

1. Retain the existing injected-use-case helper for tests/custom hosts.
2. Add a separate production factory that receives a workspace root and explicit
   host policy/approval/supervision configuration.
3. Compose the use case, POSIX adapters, lease, policy, approval, journal,
   recovery gate, cancellation/deadline bridge, and registered-tool adapter.
4. Keep stage/journal paths workspace-contained and protected by default policy.
5. Return a normal host when mutation is unavailable: retain read-only tools,
   omit `apply_patch`, and expose structured mutation-disabled status rather than
   failing the entire bootstrap.

**Acceptance criteria**

- [ ] A caller can construct the single production `apply_patch` tool without
      manually assembling filesystem internals.
- [ ] Production defaults require approval.
- [ ] Capability failure or unresolved recovery omits `apply_patch` while
       retaining read-only tools and exposing structured evidence with the stable
       `UNSUPPORTED_FILESYSTEM_GUARANTEE` or `RECOVERY_REQUIRED` status.
- [ ] Filesystem details do not leak into `agent_runtime`.

**Verification**

- [ ] Temporary-workspace composition tests cover clean startup, unsupported
      capability, approval denial, successful approval, and recovery-required
      startup.

### AP-07 — Align public schema and runtime argument bounds

**Likely files**

- `src/fabrica/features/workspace_editing/adapters/inbound/registered_tool/adapter.py`
- `src/fabrica/features/agent_runtime/application/dtos/tools.py`, if a
  tool-specific bounded-string path is necessary.
- Registered-tool tests.

**Work**

1. Make the public schema specify `input.minLength = 1` and
   `input.maxLength = 262144`.
2. Add a schema-aware, tool-name-scoped argument-normalization exception in the
   agent runtime that permits only `apply_patch.input` up to 262,144 characters
   while retaining the 20,000-character generic limit for every other tool
   argument. The generic normalization path runs before a registered-tool handler,
   so changing only the apply-patch adapter would not make the accepted contract
   observable.
3. Ensure oversize patch input maps to structured `LIMIT_EXCEEDED` behavior.

**Acceptance criteria**

- [ ] Model-facing schema matches the accepted public interface.
- [ ] Patches up to 262,144 characters reach canonical patch validation.
- [ ] Empty and oversized input return deterministic typed outcomes.

**Verification**

- [ ] Boundary tests cover lengths 0, 1, 20,000, 20,001, 262,144, and 262,145.

### AP-08 — Add production-path integration and acceptance coverage

**Likely files**

- `tests/unit/features/workspace_editing/`
- `tests/integration/features/workspace_editing/`
- Targeted `agent_runtime` tool-loop integration tests where runtime behavior is
  the subject under test.

**Work**

1. Add tests for capability-proven composition, native no-replace races,
   helper-process terminal guarantees, deadline/cancellation mapping, startup
   recovery gating, and the agent-runtime normalization path that permits a
   262,144-character `apply_patch.input`.
2. Cover duplicate delivery replay and conflicting `call_id` behavior through the
   composed runtime.
3. Clearly label existing fixtures that set
   `require_production_capabilities=False` as non-production behavior tests.

**Acceptance criteria**

- [ ] Every remaining critical success criterion in the accepted specification
      has a direct regression test.
- [ ] Capability-dependent tests skip only when the real primitive is absent;
      they never turn an unsupported production path into success.

**Verification**

- [ ] Focused workspace-editing unit and integration suites pass.
- [ ] Targeted runtime tool-loop integration suite passes.

### AP-09 — Documentation and final validation

**Likely files**

- `README.md`
- `docs/adr/`, if the chosen native-operation/helper architecture is a material
  architectural decision.
- This plan document.

**Work**

1. Update README wording only after production enablement is genuinely complete;
   document workspace capability requirements, Apple Silicon macOS release scope,
   Linux support status, approval behavior, recovery gating, and structured
   mutation-disabled outcomes.
2. Add an ADR if the platform-specific binding or helper-process architecture
   introduces a durable architecture/dependency decision.
3. Update this plan's checkboxes and concise status notes with actual validation
   evidence.

**Acceptance criteria**

- [ ] Documentation no longer describes production mutation as universally
      fail-closed once a proven backend exists.
- [ ] Unsupported environments and recovery-required behavior remain documented.

**Verification**

- [ ] `uv run ruff format .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run ty check src tests`
- [ ] `uv run lint-imports`
- [ ] `uv run pytest`
- [ ] `uv build`
- [ ] `uvx --from . fabrica --help`
- [ ] Run `scripts/apply_patch_posix_capability_probe.py` against a temporary
       workspace on each supported target platform. Store the structured results
       as implementation evidence; a skipped or failed probe may confirm
       unsupported status but must never enable production mutation.

## Risks, Assumptions, and Open Questions

### Risks

- macOS may not offer a supported no-replace primitive with the required
  semantics. It must remain unsupported rather than receive a weaker fallback.
- Helper-process ownership introduces IPC, crash, and durable-state complexity;
  journal evidence is the source of truth after uncertainty.
- Native bindings must be narrowly scoped and thoroughly tested to preserve the
  feature's fail-closed safety model.

### Assumptions

- Existing parser/planner/commit behavior remains valid except where production
  native-operation and helper ownership changes require narrow adaptation.
- The current agent-runtime ledger already satisfies duplicate delivery replay
  and conflicting-call-ID rejection requirements.
- No new user decision is required unless capability research proves a spec-level
  ambiguity; then update the specification and obtain renewed acceptance before
  widening behavior.

### Confirmed decisions

- Apple Silicon macOS is the primary and release-blocking production-v1 target.
  Linux is required support work but is non-blocking; unsupported or incomplete
  Linux combinations must fail cleanly and be documented.
- Each actual workspace must positively prove the complete native filesystem
  contract at runtime. No static platform or filesystem allowlist may enable
  production mutation.
- A supervised helper owns a started commit through successful completion or
  rollback to a journaled terminal state, including after caller disconnect,
  cancellation, or deadline expiry. The parent must not claim successful mutation
  until it has terminal-result evidence.
- Bootstrap always preserves independent read-only tools. When mutation is
  unavailable, it omits `apply_patch` and exposes machine-readable disabled
  status: `UNSUPPORTED_FILESYSTEM_GUARANTEE` for failed capability proof or
  `RECOVERY_REQUIRED` for unresolved recovery, with diagnostic evidence and
  operator guidance as metadata.
- Preserve the accepted 262,144-character `apply_patch.input` limit by adding a
  narrowly scoped runtime normalization exception; all other tool arguments keep
  the generic 20,000-character limit.

### Remaining AP-01 research deliverables

- **Owner: feature implementer and approver.** Select and prove the exact macOS
  and Linux native primitives/bindings for no-replace creation/rename,
  descriptor-rooted traversal, and durability. Record supported capability
  evidence and every errno or probe result that requires fail-closed unsupported
  status.
- **Owner: feature implementer and approver.** Specify the supervised helper's
  creation, IPC, deadline, cancellation, disconnect, termination, and
  journal-backed recovery protocol, including how the parent verifies terminal
  evidence before making a terminal claim to the runtime.
- If investigation cannot prove Apple Silicon macOS support, mark it unsupported
  for production v1 rather than weakening or implicitly changing the accepted
  specification.
