# Implementation Plan: Commit Workflow Snapshot-Safety Conformance

## Status

- State: Ready.
- Source specification: `docs/specs/commit-workflows-spec.md`.
- Related adapter specification: `docs/specs/tools-git-workflow-tools-spec.md`.
- Created: September 3, 2026.
- Owner: Maintainer.
- Review updated: September 3, 2026.

## Objective

Implement the accepted commit-workflow safety contract so `fabrica commit`:

1. detects index or tracked-worktree changes caused by pre-commit through
   before/after repository-state comparison rather than hook-output parsing alone;
2. refuses to commit when the index changed after the displayed recommendation was
   generated; and
3. still permits approval when only tracked, unstaged worktree files change after
   recommendation generation and the index tree remains unchanged.

## Scope

### In Scope

- A developer-workflow application boundary type for a safe repository-state
  fingerprint containing an index-tree identity and tracked-worktree identity.
- A focused outbound port and git subprocess adapter that capture the fingerprint
  through fixed, non-shell Git commands and safe application errors.
- Pre-commit adapter behavior that captures fingerprints before and after hooks,
  returns `MODIFIED_FILES` when either relevant state component changes, and
  retains safe hook-output handling.
- Confirmed-commit application workflow behavior that captures the analyzed index
  tree before staged-evidence generation, proves it remains unchanged before
  recommendation display, and revalidates it immediately after CLI approval and
  before calling the commit-creation port.
- Composition wiring, deterministic unit tests, temporary-repository integration
  tests, and synchronized specification/README documentation.

### Out of Scope

- Changes to the read-only `fabrica commit-message` workflow.
- Automatic staging, unstaging, restoring, or cleanup of tracked/untracked files.
- Blocking approved commits on worktree-only changes after recommendation display.
- Arbitrary Git/pre-commit command execution, model-provided Git arguments, or
  non-interactive approval.
- Detecting, reporting, or deleting untracked pre-commit cache artifacts beyond
  ensuring they do not alone produce a modified-files result.

## Confirmed Decisions and Constraints

- The index tree is the authoritative commit snapshot.
- Pre-commit compares both index tree and tracked-worktree state before and after
  hook execution. A change to either stops the workflow before model invocation.
- After recommendation generation, only the index tree is revalidated. An
  unchanged index permits commit despite tracked but unstaged worktree changes.
- Repository fingerprints and error metadata must not expose raw file contents,
  unbounded status output, or secrets.
- All subprocess calls use fixed argument vectors, `shell=False` through the
  existing process-group runner, the composition-owned working directory, and
  bounded timeouts.
- Follow the hexagonal ownership boundary: DTOs and ports in
  `developer_workflow/application`, subprocess behavior in the feature-owned
  outbound adapter, prompting in the CLI adapter, and wiring in bootstrap.
- The first implementation provides an application-layer, best-effort
  compare-before-commit guarantee. Git can still change the index after the final
  comparison and before the independently invoked `git commit` subprocess. The
  implementation and documentation must not claim atomic compare-and-commit
  protection. A stronger guarantee requires a separately accepted commit-port and
  adapter contract change.

## Fingerprint Algorithm and State Semantics

- The index-tree identity is the strict, lowercase hexadecimal object ID emitted
  by fixed `git --no-pager write-tree` argv. The snapshot adapter treats empty,
  malformed, non-zero, undecodable, or oversized output as an application-safe
  snapshot-load failure.
- The tracked-worktree identity is a fixed-length digest of the raw, tracked-only
  diff representation emitted by fixed Git argv with external diff disabled. The
  adapter computes the digest locally and never exposes diff text, pathnames, or
  raw command output through application DTOs or safe error metadata.
- The selected tracked-worktree command must compare the working tree with the
  index, include content and mode changes, exclude untracked and ignored files,
  and use flags that prevent pager, external-diff, text-conversion, and ambient
  configuration behavior from changing the representation. T2 must record the
  exact argv and expected output behavior in the adapter specification.
- Unmerged index entries, unavailable Git, non-repository execution, timeout,
  non-zero execution, decode failure, malformed output, and output above the
  configured bound are non-comparable states. They fail safely; the workflow must
  not continue to model invocation or commit creation.
- Pre-commit state comparison uses both fingerprint components. The
  post-approval check uses only the captured index-tree identity. The tracked
  worktree component is intentionally not retained as a commit-approval
  precondition.
- Snapshot reads are read-only observations, not a transaction or reservation.
  The final comparison narrows but cannot eliminate an external-process race
  before `git commit` begins.

## Dependency Graph

```text
Repository fingerprint DTO + outbound port
  -> git subprocess fingerprint adapter and command builders
    -> pre-commit before/after state comparison
    -> capture-before-generation and verify-before-display index lifecycle
      -> CLI-approved index revalidation
        -> composition wiring and end-to-end integration tests
```

Tasks 1 through 4 are sequential because each consumes the preceding contract.
Documentation updates and test additions should accompany their owning task;
final quality-gate execution follows all implementation work.

## Progress Tracking

- [ ] T1 — Define repository snapshot application contracts.
- [ ] T2 — Implement and test the safe Git subprocess snapshot adapter.
- [ ] T3 — Make pre-commit state comparison authoritative.
- [ ] T4 — Retain and revalidate the analyzed index snapshot before commit.
- [ ] T5 — Wire the implementation and synchronize user-facing/adapter specs.
- [ ] T6 — Run focused, integration, and full quality-gate validation.
- [ ] C1 — Contract checkpoint after T2.
- [ ] C2 — Workflow checkpoint after T4.
- [ ] C3 — Handoff checkpoint after T6.

## Ordered Tasks

### T1 — Define repository snapshot application contracts

- Add an immutable, validated repository-state fingerprint DTO under
  `src/fabrica/features/developer_workflow/application/dtos/` with only the
  index-tree identity and tracked-worktree identity required by the accepted
  contract.
- Add a narrow outbound port in
  `src/fabrica/features/developer_workflow/application/ports/git.py` to load the
  fingerprint and current index-tree identity. Equality comparison remains in the
  application workflow; the port does not promise atomic compare-and-commit.
- Define application-safe error categories/messages for unavailable Git,
  non-repository execution, timeout, non-zero execution, decode failure, and
  malformed fingerprint output. Do not expose raw stderr or paths in safe mode.
- Update package exports only for the intended public application surface.

**Likely files**

- `src/fabrica/features/developer_workflow/application/dtos/git.py`
- `src/fabrica/features/developer_workflow/application/dtos/__init__.py`
- `src/fabrica/features/developer_workflow/application/ports/git.py`
- `src/fabrica/features/developer_workflow/application/ports/__init__.py`
- `tests/unit/features/developer_workflow/application/`

**Acceptance criteria**

- The fingerprint has explicit types, immutability, non-empty validation, and
  no transport/process-specific fields.
- The port is application-owned, focused, and usable by both the pre-commit
  adapter implementation and confirmed-commit workflow without
  adapter-to-adapter calls.
- The DTO documentation and port contract state that snapshots are observations,
  not a lock or transaction, and that the final comparison is best-effort.
- Error semantics remain safe and deterministic.

**Verification**

- Run the focused DTO/port tests created or updated by this task.
- Run `uv run ruff format .` and `uv run ruff check .` for changed Python files.

### T2 — Implement and test the safe Git subprocess snapshot adapter

- Add fixed command builders for index-tree identity and tracked-worktree
  identity, using the exact algorithm and output constraints defined above, under
  `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/`.
- Implement a feature-owned subprocess adapter using the existing injectable
  `GitCommandRunner`, process-group runner, composition-owned working directory,
  and configured timeout behavior.
- Parse and validate command output strictly; normalize failures to the T1
  application-safe error contract.
- Ensure the tracked-worktree identity excludes untracked files and
  pre-commit cache artifacts by choosing a Git command that observes only tracked
  worktree differences. Hash bounded raw output locally rather than carrying it
  across the application boundary.
- Add deterministic adapter tests for fixed argv, successful fingerprints,
  state changes, malformed/decode/oversized output, timeout, unavailable Git,
  and non-repository failures.

**Likely files**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/<new_snapshot_module>.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/<new_snapshot_commands_module>.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/<new_snapshot_errors_module>.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/__init__.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/<new_snapshot_test_module>.py`

**Acceptance criteria**

- No shell, dynamic command name, model argument, arbitrary path, or unvalidated
  Git argument is introduced.
- Snapshot reads are bounded, safe, and deterministic under injected runners.
- The adapter reports tracked-worktree changes without treating untracked-only
  changes as relevant state changes.
- Tests cover mode-only changes, empty tracked-worktree differences, malformed
  object IDs, and the selected non-comparable-state behavior.

**Verification**

- Run the new snapshot-adapter test module.
- Run `uv run ruff format .` and `uv run ruff check .`.

### C1 — Contract checkpoint after T2

- Confirm T1 and T2 expose a minimal application-owned snapshot contract.
- Confirm command selection observes index and tracked worktree only and is
  compatible with the accepted adapter safety specification.
- Record any required deviation from the plan before proceeding; otherwise
  leave no unchecked blocking decision.

### T3 — Make pre-commit state comparison authoritative
- Keep `PreCommitSubprocessRunner` and the snapshot reader in the same
  feature-owned git-subprocess adapter boundary. Reuse adapter-local command
  builders and the existing injectable `GitCommandRunner`; do not inject one
  separately composed adapter into another adapter.
- Capture state before hooks, execute the existing narrow pre-commit command,
  then capture state after every hook process that started and returned a process
  result, including non-zero exits. Skip the after-state read only when the hook
  cannot start, times out, or is interrupted before a comparable process result
  exists.
  outcome.
- Return `PreCommitRunStatus.MODIFIED_FILES` when the index tree or tracked
  worktree identity changed, regardless of hook return code/output marker.
- Preserve existing handling for missing configuration, unavailable
  pre-commit, timeout, invalid configuration, decode failures, and bounded output.
- When a started hook both changes state and exits non-zero, return
  `MODIFIED_FILES` as the primary safe outcome and retain only bounded,
  non-authoritative failure diagnostics. A failed post-state read is an
  application-safe failure that stops the workflow; it must not be silently
  treated as unchanged state.
- Retire output-marker parsing as the source of truth; it may remain only as
  non-authoritative diagnostic context if it remains safe and useful.
- Add unit and temporary-repository integration coverage for silent tracked
  worktree changes, index changes, formatter-style changes, unchanged successful
  hooks, non-zero hooks that modify state, and untracked/cache-only artifacts.

**Likely files**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/pre_commit.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/pre_commit_commands.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_pre_commit.py`
- `tests/integration/features/developer_workflow/test_confirmed_commit_composition.py`

**Acceptance criteria**

- A silent hook mutation produces `MODIFIED_FILES` and stops before model use.
- A hook that changes neither index nor tracked worktree can pass even if its
  output differs from conventional pre-commit wording.
- Untracked-only artifacts do not cause `MODIFIED_FILES`.
- A non-zero hook that modified tracked state returns `MODIFIED_FILES`; a
  non-comparable post-hook fingerprint fails safely.
- No hook-produced changes are staged, reverted, or committed by Fabrica.

**Verification**

- Run focused pre-commit adapter and confirmed-workflow unit tests.
- Run the impacted temporary-repository integration tests.

### T4 — Retain and revalidate the analyzed index snapshot before commit
- Extend the confirmed-commit application flow so it captures the index-tree
  identity after pre-commit passes and before staged-evidence generation. After
  generation, re-read the identity before returning a recommendation to the CLI;
  deny the flow without display or prompting if it changed during generation.
- Retain the validated pre-display index-tree identity with the recommendation
  without leaking Git process details to the CLI adapter.
  process details to the CLI adapter.
- Change the inbound confirmed-commit port/result contract only as needed to
  carry the captured identity between `generate()` and the approved `commit()`
  call; update fakes and callers together.
- Immediately after positive CLI approval, re-read the index identity and
  refuse commit-port invocation when it differs from the captured value. Document
  this as a best-effort application-layer check, not an atomic Git guarantee.
- Return a safe, user-facing observation stating that staged changes changed
  after recommendation generation and that the command must be rerun.
- Permit commit when only tracked unstaged worktree state changes after
  recommendation display and the index identity is unchanged.
- Add deterministic unit coverage for unchanged index success, index change
  during generation, changed-index denial after approval, and worktree-only
  non-denial. Add temporary-repository integration scenarios proving no commit
  occurs after an index change and that `HEAD` remains unchanged.
- Add a deterministic CLI orchestration test with controllable approval input or
  workflow coordination that mutates the index after `yes` is read and before the
  final validation result; assert one recommendation display, a non-zero denial,
  and no commit-port invocation.

**Likely files**

- `src/fabrica/features/developer_workflow/application/use_cases/commit_workflow.py`
- `src/fabrica/features/developer_workflow/application/dtos/commit_message.py`
- `src/fabrica/features/developer_workflow/application/ports/inbound.py`
- `src/fabrica/features/developer_workflow/adapters/inbound/cli/runner.py`
- `tests/unit/features/developer_workflow/application/test_confirmed_commit_workflow.py`
- `tests/unit/features/developer_workflow/adapters/inbound/cli/test_commit_command.py`
- `tests/integration/features/developer_workflow/test_confirmed_commit_composition.py`

**Acceptance criteria**

- The commit port receives the exact recommendation message only when the index
  still matches the analyzed snapshot.
- An index mismatch returns non-zero, does not invoke the commit port, and does
  not mutate the repository.
- An index mismatch detected before recommendation display skips the prompt and
  tells the user to rerun the workflow.
- A tracked-worktree-only change after generation does not prevent a commit.
- Rejection, EOF, and interrupted input retain their existing behavior.

**Verification**

- Run focused application and feature CLI tests.
- Run the impacted temporary-repository integration tests.

### C2 — Workflow checkpoint after T4

- Confirm pre-commit compares both accepted state components before model
  invocation.
- Confirm the post-approval path revalidates index only, immediately before
  commit creation, and that documentation accurately labels the remaining
  cross-process TOCTOU window.
- Confirm all denied paths skip commit-port invocation and preserve index and
  worktree state.

### T5 — Wire the implementation and synchronize documentation

- Update bootstrap composition so the confirmed workflow receives the snapshot
  dependency through application-owned ports.
- Update `docs/specs/tools-git-workflow-tools-spec.md` because it owns the
  pre-commit subprocess adapter contract; specify its fixed snapshot commands,
  fingerprint algorithm, state-comparison rule, failure precedence, residual
  compare-before-commit race, and safe result/error behavior.
- Update `docs/specs/commit-workflows-spec.md` to state the capture-before-
  generation and verify-before-display lifecycle, and to avoid claiming atomic
  compare-and-commit protection.
- Update `README.md` only if user-visible failure behavior or wording changes
  materially; keep the staged-only and explicit-approval guidance aligned.
- Update this plan’s task/checkpoint status after each completed task and
  document any scope deviation or newly discovered blocker.

**Likely files**

- `src/fabrica/bootstrap/composition/developer_workflow.py`
- `docs/specs/tools-git-workflow-tools-spec.md`
- `README.md` if required by observable CLI wording
- `docs/plans/commit-workflow-snapshot-safety-conformance-plan.md`

**Acceptance criteria**

- Composition has no adapter-to-adapter dependency leakage.
- The two specifications agree on ownership and the state-comparison contract.
- The specifications distinguish the implemented best-effort check from a future
  atomic compare-and-commit guarantee.
- Public documentation remains accurate and does not claim completed behavior
  before the implementation and validation tasks pass.

**Verification**

- Review specification cross-references and CLI help/README wording.
- Run the focused composition tests.

### T6 — Run focused, integration, and full quality-gate validation

- Run focused application tests:
  `uv run pytest tests/unit/features/developer_workflow/application/`.
- Run focused feature CLI tests:
  `uv run pytest tests/unit/features/developer_workflow/adapters/inbound/cli/`.
- Run focused Git subprocess tests:
  `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/`.
- Run developer-workflow integration tests:
  `uv run pytest tests/integration/features/developer_workflow/`.
- Verify deterministic coverage for: index mutation during generation; index
  mutation after approval; tracked-worktree-only mutation after display; silent
  successful hook mutation; non-zero hook mutation; untracked-only artifacts;
  and non-comparable fingerprint failures.
- Run the full configured quality gate without ad hoc final-run flags:
  `uv run ruff format .`, `uv run ruff check .`, `uv run ty check src tests`,
  and `uv run pytest`.
- Record executed commands and outcomes in the implementation handoff; leave
  failed/skipped checks visible with root cause and mitigation.

**Acceptance criteria**

- All required checks pass with no unapproved failures.
- Tests cover the accepted safety contract and regressions identified in the
  September 3, 2026 audit.
- The plan has accurate completion state and no hidden deferred blocker.

### C3 — Handoff checkpoint after T6

- Confirm all T1–T6 acceptance and verification items are complete.
- Confirm implementation, tests, README, and both related specifications agree.
- Summarize changed files, validation evidence, accepted risks, and any
  intentionally deferred work.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| A fingerprint command accidentally includes untracked cache artifacts. | Use Git commands that observe only the index and tracked worktree; cover untracked-only integration cases. |
| Hook output conflicts with actual repository state. | Make before/after state comparison authoritative and retain output only as bounded diagnostic context. |
| A new snapshot contract leaks subprocess concerns into the application core. | Limit DTOs to immutable domain-neutral identifiers and define application-owned ports; keep command construction/parsing in the adapter. |
| Index changes race with evidence generation. | Capture the index before generation and re-read it before recommendation display; deny stale recommendations before prompting. |
| Index changes race with approval/commit. | Revalidate immediately after approval and before commit-port invocation; document the remaining unavoidable process-level race as an accepted best-effort limitation. Do not claim atomicity without a separately accepted port/adapter redesign. |
| Fingerprint representation is affected by Git configuration or non-comparable index state. | Specify exact fixed argv, disable representation-changing external behavior, strictly validate output, and fail safely for unmerged, malformed, timed-out, or oversized observations. |
| Pre-commit fails after mutating state. | Capture post-hook state after every started process with a result and make `MODIFIED_FILES` the primary outcome when state changed; fail safely when the post-state cannot be compared. |
| Broad interface changes complicate CLI fakes and tests. | Carry only the minimum snapshot value needed between generation and commit; update affected fakes in the same task. |

## Assumptions

- Git can provide stable, safe-to-compare identities for the current index tree
  and tracked worktree state through fixed local commands.
- The repository already provides deterministic temporary-git-repository test
  helpers that can be extended without live network or Codex calls.
- No backward-compatibility shim is required; the project is in raw development.

## Deferred Work

- Atomic compare-and-commit protection is deferred. The first implementation
  narrows the external-process race with application-layer revalidation but does
  not eliminate it. Any later change that passes an expected index identity into
  the commit-creation port or changes commit-adapter behavior requires an updated
  and accepted specification.

## Open Questions

None. T2 must select and document the exact tracked-worktree Git argv consistent
with the fingerprint algorithm before implementation starts; if available Git
semantics cannot meet that algorithm, stop at C1 and raise a specification
decision rather than weakening the accepted safety contract.
