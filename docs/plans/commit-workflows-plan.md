# Implementation Plan: Commit Workflows

## Overview

Implement the canonical commit workflows from
`docs/specs/commit-workflows.md` while preserving the existing hexagonal
`developer_workflow` slice boundaries. The implementation must keep
`fabrica commit-message` read-only and staged-only, and make `fabrica commit`
run pre-commit before any model call, stop safely on pre-commit failure or file
modification, display one recommendation block, prompt conservatively, and
commit only after explicit approval.

## Goal

Bring the current implementation fully in line with the commit workflow spec.

## Deliverables

- Application-layer orchestration for pre-commit gating before commit-message
  generation in `fabrica commit`.
- CLI behavior/tests preserving conservative approval, rejection, interruption,
  and evidence output behavior.
- Composition wiring that injects the existing pre-commit subprocess adapter into
  the confirmed commit workflow.
- Focused unit and integration tests for the pre-commit gate, commit creation,
  and no-mutation failure paths.
- README/help/docs updates only if implementation changes visible behavior beyond
  current documented text.
- This living plan document with task checkboxes and verification status.

## Success Criteria

- `fabrica commit-message` remains read-only, staged-only, and does not run
  pre-commit or git commit.
- `fabrica commit` runs pre-commit before model invocation.
- `fabrica commit` skips model invocation, prompting, and commit execution when
  pre-commit fails, times out, cannot run, or reports modified files.
- The generated recommendation block is printed once before prompting.
- Only trimmed, case-insensitive `y` or `yes` commits.
- Rejection leaves staged files untouched and exits `0`; interrupted input exits
  non-zero.
- The exact `CommitMessageRecommendation.commit_message` is passed to git commit
  creation.
- Tests are deterministic/offline and use temporary git repositories or fakes.
- Final quality gate passes:
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run ty check src tests`
  - `uv run pytest`

## Constraints

- Preserve hexagonal boundaries in `src/fabrica/features/developer_workflow/`.
- Keep terminal prompts in inbound CLI adapters.
- Keep pre-commit and git commit execution behind developer-workflow outbound
  ports/adapters.
- Do not add `--yes`, auto-staging, hook bypassing, auto-push,
  edit/regenerate flow, JSON output, arbitrary git commands, or model-callable
  mutating git powers.
- Do not inspect unstaged changes as commit-message evidence.
- Keep per-file evidence analysis async and bounded-parallel.
- Do not run pre-commit with `--all-files`; use the existing staged workflow
  default `PreCommitRunCommand()`.
- Avoid compatibility shims; this project is still early and code clarity is
  preferred.

## Architecture Decisions

- **Use the existing pre-commit port/adapter.** `PreCommitRunner`,
  `PreCommitRunCommand`, `PreCommitRunResult`, and `PreCommitSubprocessRunner`
  already exist and should be reused instead of adding a second quality-check
  abstraction.
- **Move confirmed commit orchestration into the developer-workflow application
  use case layer.** `ConfirmedCommitWorkflow` and
  `ConfirmedCommitWorkflowResult` should be owned by
  `src/fabrica/features/developer_workflow/application/use_cases/commit_workflow.py`
  rather than growing additional business workflow logic in the composition root.
  `src/fabrica/bootstrap/composition.py` should only wire concrete dependencies:
  `GenerateCommitMessage`, `CreateGitCommit`, `PreCommitSubprocessRunner`, and
  evidence-recorder/runtime plumbing.
- **Gate inside the confirmed workflow use case before generation.** The
  pre-commit check belongs in the developer-workflow application use case, before
  `GenerateCommitMessage.generate_async()` is called. The CLI should still own
  only the interactive prompt and terminal I/O.
- **Keep commit creation split from generation.** Continue using
  `ConfirmedCommitWorkflow.generate()` followed by the CLI prompt and
  `ConfirmedCommitWorkflow.commit()` so rejection never calls the commit port.
- **Map pre-commit stop conditions to safe application results.** Pre-commit
  failure, modified files, timeout/startup errors should become
  `ConfirmedCommitWorkflowResult` failures with safe `RuntimeObservation`
  metadata and `commit_attempted=False`.
- **Use conservative pre-commit result mapping.** A blocked pre-commit gate should
  return `LocalAgentRunStatus.CONFIGURATION_ERROR`, `recommendation=None`,
  `commit_result=None`, `commit_attempted=False`, and empty usage/cost evidence.
  Use observation category `pre_commit_failed` for
  `PreCommitRunStatus.FAILED`, `pre_commit_modified_files` for
  `PreCommitRunStatus.MODIFIED_FILES`, and the safe `PreCommitRunError.category`
  metadata for timeout/startup/configuration errors.
- **Preserve async bounded-parallel staged-file analysis.** `GenerateCommitMessage`
  should continue to use async per-file analysis through
  `BoundedAsyncQueryFanoutExecutor.gather_ordered(...)`. `max_parallel_analysis`
  remains configurable and defaults to `4`. The final evidence bundle must
  preserve staged-file order even when analysis runs concurrently.

## Pre-commit Gate Result Mapping

| Pre-commit outcome | Workflow status | Observation category | Recommendation | Commit attempted | Usage/cost evidence |
| --- | --- | --- | --- | --- | --- |
| `PreCommitRunStatus.PASSED` | Continue to recommendation generation | n/a | Generated after model workflow | `False` until approval/commit | Collected from model calls |
| `PreCommitRunStatus.FAILED` | `LocalAgentRunStatus.CONFIGURATION_ERROR` | `pre_commit_failed` | `None` | `False` | Empty |
| `PreCommitRunStatus.MODIFIED_FILES` | `LocalAgentRunStatus.CONFIGURATION_ERROR` | `pre_commit_modified_files` | `None` | `False` | Empty |
| `PreCommitRunError` | `LocalAgentRunStatus.CONFIGURATION_ERROR` | safe `err.category` metadata | `None` | `False` | Empty |

The modified-files observation message must tell the user that no commit was
created and they must review and stage changed files before retrying.
Formatter hooks that rewrite files are part of this `MODIFIED_FILES` path: stop
without model invocation, prompting, or commit creation; do not auto-stage the
formatter output; wait for the user to review, stage, and rerun `fabrica commit`.

## Progress Tracking

Treat this plan as a living document during implementation. After each completed
task or meaningful scope change:

- check off completed tasks, acceptance criteria, verification items, and
  checkpoints
- leave unfinished or unverified items unchecked
- add newly discovered work and update sequencing when scope or dependencies
  change
- note blockers, deviations, and decisions that affect remaining work

## Task List

### Phase 1: Lock current gaps with focused tests

#### Task 1: Add application tests for pre-commit gating before recommendation generation

**Description:** Add tests proving that confirmed commit generation runs
pre-commit before staged-file/model work and stops before model invocation on
non-passing pre-commit outcomes.

**Acceptance criteria:**

- [x] A passing pre-commit result allows recommendation generation to proceed.
- [x] `FAILED` pre-commit result skips generator/model invocation and commit
      execution.
- [x] `MODIFIED_FILES` pre-commit result skips generator/model invocation and
      reports that the user must review/stage changes before retrying.
- [x] `PreCommitRunError` skips generator/model invocation and commit execution.
- [x] The pre-commit command uses `PreCommitRunCommand()` and does not enable
      `all_files`.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/`
  - 2026-08-10: Expected red-test failure captured. New tests fail because
    `ConfirmedCommitWorkflow.__init__()` does not yet accept `pre_commit_runner`.
  - 2026-08-10: Passed after implementing the confirmed commit pre-commit gate.

**Dependencies:** None.

**Files likely touched:**

- `tests/unit/features/developer_workflow/application/test_create_git_commit.py`
  or new `tests/unit/features/developer_workflow/application/test_confirmed_commit_workflow.py`
- `src/fabrica/features/developer_workflow/application/use_cases/commit_workflow.py`
- `src/fabrica/bootstrap/composition.py` only if moving existing confirmed
  workflow classes out of bootstrap requires import/wiring updates

**Estimated scope:** Small.

#### Task 2: Add CLI tests for pre-commit-stop presentation through confirmed commit results

**Description:** Ensure the CLI preserves existing prompt behavior and does not
prompt when the application reports pre-commit stop/failure before recommendation
generation.

**Acceptance criteria:**

- [x] Pre-commit failure result produces a clear stderr observation and non-zero
      exit.
- [x] No confirmation prompt is written when recommendation generation is blocked.
- [x] `workflow.commit()` is not called.

**Verification:**

- [x] `uv run pytest tests/unit/adapters/inbound/cli/test_commit_command.py`
  - 2026-08-10: Passed after adding pre-commit-stop CLI regression coverage.

**Dependencies:** Task 1.

**Files likely touched:**

- `tests/unit/adapters/inbound/cli/test_commit_command.py`

**Estimated scope:** XS/S.

### Checkpoint: Pre-commit gate behavior specified by tests

- [x] Focused application and CLI tests fail for the expected missing
      implementation reason before production changes.
- [x] No unrelated behavior changes have been introduced.

### Phase 2: Implement pre-commit gate in the confirmed workflow

#### Task 3: Extend confirmed commit orchestration with a pre-commit runner

**Description:** Add pre-commit execution to
`ConfirmedCommitWorkflow.generate_async()` in the developer-workflow application
use case before `self.generator.generate_async(...)`. If the pre-commit check
does not pass, return a safe `ConfirmedCommitWorkflowResult` and do not call the
generator. Move existing confirmed commit workflow/result classes out of
`src/fabrica/bootstrap/composition.py` if needed so application orchestration is
owned by `src/fabrica/features/developer_workflow/application/use_cases/commit_workflow.py`.

**Acceptance criteria:**

- [x] `PreCommitRunner.run_pre_commit(PreCommitRunCommand())` is called before
      generator invocation.
- [x] `PreCommitRunStatus.PASSED` continues to existing async bounded-parallel
      recommendation generation.
- [x] `FAILED` and `MODIFIED_FILES` return a safe failure status with
      observations and `commit_attempted=False`.
- [x] `PreCommitRunError` returns a safe failure result with category metadata
      and `commit_attempted=False`.
- [x] Model usage/cost evidence remains empty when generation never starts.
- [x] Direct `ConfirmedCommitWorkflow` tests use an explicit passing fake
      pre-commit runner; production composition must not rely on a default that
      silently disables the gate.
- [x] `bootstrap/composition.py` remains side-effect-light and contains wiring,
      not confirmed commit business decision logic.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/`

**Dependencies:** Task 1.

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/use_cases/commit_workflow.py`
- `src/fabrica/features/developer_workflow/application/use_cases/__init__.py` if
  exports change
- `src/fabrica/bootstrap/composition.py` for import and dependency wiring updates
- `tests/unit/features/developer_workflow/application/`

**Estimated scope:** Medium.

#### Task 4: Wire the pre-commit subprocess adapter into confirmed commit composition

**Description:** Update composition so `create_confirmed_commit_workflow()` and
`create_codex_confirmed_commit_workflow()` use `PreCommitSubprocessRunner` with
the composition-owned working directory, timeout, and diagnostics options.

**Acceptance criteria:**

- [x] Confirmed commit workflow construction injects `PreCommitSubprocessRunner`.
- [x] Construction remains side-effect-light: no pre-commit execution happens
      until workflow run.
- [x] `commit-message` composition remains unchanged and does not run pre-commit.
- [x] Existing pre-commit registered-tool composition remains separate from the
      confirmed commit workflow gate.

**Verification:**

- [x] `uv run pytest tests/integration/features/developer_workflow/test_confirmed_commit_composition.py tests/integration/features/developer_workflow/test_commit_message_composition.py tests/integration/features/developer_workflow/test_pre_commit_tool_composition.py`

**Dependencies:** Task 3.

**Files likely touched:**

- `src/fabrica/bootstrap/composition.py`
- `tests/integration/features/developer_workflow/test_confirmed_commit_composition.py`
- `tests/integration/features/developer_workflow/test_commit_message_composition.py`
  if adding a read-only guard

**Estimated scope:** Medium.

### Checkpoint: Confirmed commit pre-commit gate wired end-to-end

- [x] Focused unit tests pass.
- [x] Focused developer-workflow integration tests pass.
- [x] Manual review confirms `commit-message` remains read-only.
  - 2026-08-10: Confirmed `create_commit_message_workflow()` still wires only
    staged-change loading, evidence analysis, and synthesis; the pre-commit
    runner is injected only by `create_confirmed_commit_workflow()`.

### Phase 3: Tighten spec alignment and edge cases

#### Task 5: Preserve async bounded-parallel staged-file analysis

**Description:** Confirm the implementation keeps the existing async
bounded-parallel per-file evidence analysis while adding the pre-commit gate
before generation. Do not serialize the analysis path.

**Acceptance criteria:**

- [x] `GenerateCommitMessage` continues to use async per-file analysis.
- [x] `max_parallel_analysis` remains configurable and defaults to `4`.
- [x] Evidence remains ordered in the final bundle despite parallel execution.
- [x] Pre-commit runs before any async file-diff/model analysis starts in
      `fabrica commit`.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/test_generate_commit_message.py`
  - 2026-08-10: Passed together with confirmed commit workflow tests after
    adding coverage for default/configured bounded parallelism and ordered
    evidence through the query executor boundary.
- [x] New/updated confirmed commit tests prove pre-commit failure means no
      generator/model calls happen.

**Dependencies:** Tasks 3-4.

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/use_cases/commit_workflow.py`
- `tests/unit/features/developer_workflow/application/test_generate_commit_message.py`
  only if guard coverage needs strengthening

**Estimated scope:** Small.

#### Task 6: Add integration coverage for pre-commit pass/fail/modified paths in temporary repositories

**Description:** Extend offline integration tests so temporary repositories prove
the composed workflow creates a commit only after pre-commit passes and never
commits when pre-commit fails or modifies files.

Use deterministic temp-repo-local pre-commit fixtures. Each temporary repository
that exercises the confirmed commit workflow should write a minimal local
`.pre-commit-config.yaml` and local hook scripts so tests do not depend on the
workspace's ambient pre-commit configuration, network access, or developer state.
Existing success-path confirmed commit integration tests must install a passing
local pre-commit hook after the gate is wired.

**Acceptance criteria:**

- [x] Passing pre-commit path creates exactly one commit with the generated
      message.
- [x] Failing pre-commit path creates no commit and does not invoke the fake
      runtime/model.
- [x] Modifying pre-commit path creates no commit and leaves the user to
      review/stage changed files.
- [x] Success-path tests use a temp-repo-local passing pre-commit hook.
- [x] Failure and modification tests use temp-repo-local hooks and remain fully
      offline/deterministic.
- [x] Existing git hook failure after approval remains covered separately as a
      git commit failure, if still relevant.

**Verification:**

- [x] `uv run pytest tests/integration/features/developer_workflow/test_confirmed_commit_composition.py`
  - 2026-08-10: Passed after adding temp-repo-local passing, failing, and
    modifying pre-commit hook fixtures.

**Dependencies:** Tasks 3-4.

**Files likely touched:**

- `tests/integration/features/developer_workflow/test_confirmed_commit_composition.py`

**Estimated scope:** Medium.

### Checkpoint: Spec-critical behavior covered

- [x] No pre-commit failure path invokes model runtime.
- [x] No rejection/failure path creates a commit.
- [x] Successful path preserves exact commit message.

### Phase 4: Documentation and final validation

#### Task 7: Update CLI/README/help docs only where current docs diverge

**Description:** README already documents both workflows and the pre-commit gate.
Verify parser help and README remain accurate after implementation; update only
if needed.

**Acceptance criteria:**

- [x] `fabrica commit --help` distinguishes mutating confirmed commit from
      read-only preview.
- [x] `fabrica commit --help` mentions that the mutating workflow runs a
      pre-commit quality gate before message generation.
- [x] README mentions pre-commit gate and conservative approval behavior
      accurately.
- [x] No docs imply `commit-message` runs hooks or mutates state.

**Verification:**

- [x] `uv run fabrica commit --help`
- [x] Documentation review of `README.md` and `docs/specs/commit-workflows.md`

**Dependencies:** Tasks 3-6.

**Files likely touched:**

- `README.md` only if needed
- `src/fabrica/features/developer_workflow/adapters/inbound/cli/registration.py`
  only if help text needs changes

**Estimated scope:** XS/S.

#### Task 8: Run focused checks and full quality gate

**Description:** Validate the implementation through focused tests first, then
the full formatting/lint/type/test gate.

**Acceptance criteria:**

- [x] Focused application tests pass.
- [x] Focused CLI tests pass.
- [x] Focused developer-workflow integration tests pass.
- [x] Full project quality gate passes.

**Verification:**

```bash
uv run pytest tests/unit/features/developer_workflow/application/
uv run pytest tests/unit/adapters/inbound/cli/
uv run pytest tests/integration/features/developer_workflow/
uv run ruff format .
uv run ruff check .
uv run ty check src tests
uv run pytest
```

- [x] 2026-08-10: All focused checks and the full project quality gate passed.

**Dependencies:** All implementation tasks.

**Files likely touched:** No new files unless validation finds issues.

**Estimated scope:** Small.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Pre-commit hooks can modify files | High: committing stale or unreviewed state | Stop before model invocation on `MODIFIED_FILES`; integration-test no commit/runtime calls |
| Formatter hooks rewrite files | High: generated message could be based on stale staged evidence or formatter output could be auto-staged without review | Treat formatter rewrites as `MODIFIED_FILES`; stop and require the user to review/stage/rerun |
| Pre-commit may not be installed/configured | Medium: confusing failures | Map `PreCommitRunError` to safe, clear CLI observation |
| Existing tests may assume commit happens without pre-commit | Medium: test churn | Update tests to use passing fake pre-commit where commit behavior is under test |
| Async analysis ordering can regress | Medium: misleading final synthesis | Keep `gather_ordered(...)` and test ordered evidence bundle semantics |
| CLI evidence output after rejection/failure can duplicate blocks | Medium: confusing UX | Preserve existing `output_already_written` path and test block appears once |
| Git hooks run again during `git commit` | Medium: pre-commit can pass first but fail during git commit hook | Keep git commit failure path as separate safe failure with `commit_attempted=True` |

## Open Questions

- None currently. Confirmed decisions:
  - Keep per-file evidence analysis async and bounded-parallel.
  - Run pre-commit without `--all-files`.
  - Store this plan at `docs/plans/commit-workflows-plan.md`.

## Handoff Notes for Implementation

- Start with tests that express the missing pre-commit gate before changing
  production code.
- Keep each task small and update this plan's checkboxes after each completed
  task.
- Avoid broad refactors in `composition.py`; touch only the confirmed commit
  workflow path and necessary imports/options.
- Keep `fabrica commit-message` untouched except for guard tests proving it
  remains read-only/no-pre-commit.
- Preserve all existing CLI behavior around prompt, rejection, interruption,
  evidence output, and one-time recommendation rendering.
