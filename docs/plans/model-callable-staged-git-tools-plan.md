# Implementation Plan: Model-Callable Staged Git Tools

## Overview

Add optional model-callable tools for read-only staged git context so explicit
agent/tool-loop workflows can inspect staged changes on demand. The implementation
must preserve the deterministic `commit-message` workflow: it continues to load
bounded staged diff context before model invocation and does not depend on model
tool calls.

## Goal

Deliver three explicitly composed, read-only, staged-only registered tools:

- `git_staged_files` for discovering staged file paths and statuses.
- `git_staged_diff` for inspecting the whole staged patch.
- `git_staged_file_diff` for inspecting one validated staged file patch.

## Deliverables

- Staged file/status DTOs and validation under
  `src/fabrica/features/developer_workflow/application/dtos/`.
- Extended staged git application boundary under
  `src/fabrica/features/developer_workflow/application/ports/git_staged_changes.py`.
- Read-only subprocess adapter support for staged file listing and per-file diff
  under
  `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/`.
- Staged-git registered-tool bridge implemented against an agent-runtime
  application-owned registered-tool callable contract.
- Explicit composition helper(s) in `src/fabrica/bootstrap/local_agent_runtime.py`.
- Focused unit and integration tests for DTOs, adapter behavior, registered tool
  behavior, composition, and deterministic commit-message preservation.
- Documentation updates when usage or composition behavior becomes user-visible.

## Success Criteria

- The three tools expose the exact intended model-callable surface:
  `git_staged_files`, `git_staged_diff`, and `git_staged_file_diff`.
- Tools are read-only, staged-only, bounded, deterministic, and explicitly
  composed.
- The model cannot choose the repository working directory, arbitrary git flags,
  arbitrary pathspecs, or mutating git operations.
- `git_staged_file_diff` accepts only a safe relative path that is currently
  staged.
- Existing `commit-message` behavior remains deterministic and does not depend on
  model tool calls.
- Default automated tests remain deterministic, offline, and independent of the
  developer's ambient staged git state.
- Full quality gate passes before handoff:
  `uv run ruff format .`, `uv run ruff check .`,
  `uv run ty check src tests`, and `uv run pytest`.

## Constraints

- Do not expose arbitrary git command execution.
- Do not expose `git commit`, `git add`, `git reset`, checkout, branch switching,
  stash, push, pull, or any mutating git operation.
- Do not inspect unstaged changes in this implementation slice.
- Do not let the model choose the repository working directory.
- Do not replace deterministic commit-message staged-diff loading with a model
  tool call.
- Do not add broad multi-purpose `git` or overloaded `git_staged_changes` tools.
- Always use explicit git argument lists with `shell=False` and `--no-pager`.
- Always keep output bounded by staged diff bounds and tool-loop result limits.
- Never expose secrets, raw stderr, raw diagnostics, or full private paths in
  model-visible errors.

## Architecture Decisions

- **Developer-workflow owns staged git semantics:** DTOs, status parsing, path
  validation, failure categories, and git subprocess execution remain in the
  `developer_workflow` slice.
- **Small cohesive staged git boundary:** Extend the current staged changes
  boundary to support `list_files()`, `load_diff()`, and `load_file_diff(path)`
  rather than creating a vague arbitrary git service. Existing `load()` can be
  retained temporarily only if it is still the clearest local name during the
  refactor; this project is early-stage, so prefer clarity over compatibility
  shims.
- **Registered-tool boundary is application-owned:** Developer-workflow code must
  not import agent-runtime outbound adapter internals such as
  `agent_runtime.adapters.outbound.registered_tool.RegisteredTool`. Promote the
  registered-tool callable contract into an agent-runtime application-owned
  boundary, then let developer-workflow bridge staged-git capabilities to that
  stable application contract. Do not create a developer-workflow adapter that
  depends directly on an agent-runtime adapter module.
- **Explicit composition only:** Bootstrap helpers may create staged git tools,
  but no runtime receives them by default. Callers must pass them into the
  registered-tool or model-driven runtime composition explicitly.
- **Plain deterministic tool text for v1:** Prefer stable, model-friendly text
  outputs. `git_staged_files` should initially return one staged entry per line,
  such as `M\tpath.py`, unless implementation findings make structured text
  clearly safer.
- **Rename behavior is conservative in v1:** `git_staged_files` should parse
  `git diff --staged --name-status` rename/copy records explicitly. For v1,
  expose the new path as the canonical safe path accepted by
  `git_staged_file_diff`; old-path lookup variants are deferred.

## Resolved Pre-Implementation Decisions

These decisions are resolved and should guide implementation:

- [x] **Registered-tool boundary:** Promote the registered-tool callable contract
      into an agent-runtime application-owned boundary. The implementation must
      not make developer-workflow depend on agent-runtime adapter internals.
- [x] **Rename/copy staged file semantics:** Parse `R*`/`C*` `--name-status`
      records and accept the canonical new path for per-file diff. Old-path
      variants are deferred.
- [x] **Tool text rendering ownership:** Keep model-facing staged file-list
      formatting in the registered-tool bridge. Developer-workflow DTOs should
      focus on validated staged-file data rather than agent-specific phrasing.

## Progress Tracking

Treat this plan as a living document during implementation. After each completed
task or meaningful change:

- check off completed tasks, acceptance criteria, verification items, and
  checkpoints;
- leave unfinished or unverified items unchecked;
- add newly discovered work and update sequencing when scope or dependencies
  change;
- note blockers, deviations, and decisions that affect remaining work.

## Task List

### Phase 1: Application Boundary Foundation

#### Task 1: Add staged file DTOs and safe path/status validation

**Description:** Add application DTOs representing staged files, statuses, and a
bounded staged file list. These DTOs form the stable developer-workflow boundary
used by subprocess and registered-tool adapters.

**Acceptance criteria:**

- [x] DTOs represent staged file path, staged status, and a list of staged files.
- [x] Paths must be non-empty safe relative paths.
- [x] Absolute paths, parent-directory traversal, empty paths, and paths with
      leading/trailing ambiguity are rejected.
- [x] Status values are represented by a closed set or validated application
      value, not unbounded magic strings.
- [x] File list DTOs expose validated staged-file data; model-facing
      `git_staged_files` text formatting is owned by the registered-tool bridge.
- [x] DTOs remain immutable boundary values and preserve safe metadata only.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/test_git_staged_changes_dtos.py`

**Dependencies:** None.

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/dtos/git_staged_changes.py`
- `src/fabrica/features/developer_workflow/application/dtos/__init__.py`
- `tests/unit/features/developer_workflow/application/test_git_staged_changes_dtos.py`

**Estimated scope:** S: 2-3 files.

#### Task 2: Extend the staged git application port contract

**Description:** Update the developer-workflow application port so the core can
request staged file listing, full staged diff loading, and one-file staged diff
loading without exposing subprocess details, git flags, transport schemas, or
repository paths.

**Acceptance criteria:**

- [x] Application boundary supports staged file listing.
- [x] Application boundary supports full staged diff loading.
- [x] Application boundary supports per-file staged diff loading by safe relative
      path.
- [x] Existing commit-message preparation still calls the deterministic full diff
      loading path before model invocation.
- [x] Port signatures use developer-workflow application/domain DTOs only.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application`

**Dependencies:** Task 1.

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/ports/git_staged_changes.py`
- `src/fabrica/features/developer_workflow/application/use_cases/prepare_commit_message_run.py`
- `tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`
- integration or test fakes that implement the staged changes port

**Estimated scope:** S: 2-4 files.

### Checkpoint: Application boundary

- [x] Focused developer-workflow application tests pass.
- [x] Commit-message preparation still fails before runtime invocation when staged
      diff loading fails.
- [x] No agent-runtime DTOs are imported into developer-workflow application
      ports except existing approved runtime context boundary DTO usage.

### Phase 2: Read-Only Subprocess Adapter

#### Task 3: Implement staged file listing in the subprocess adapter

**Description:** Extend `GitStagedChangesSubprocessLoader` or its clarified
successor to call a read-only staged file listing command and parse the output
into application DTOs.

**Acceptance criteria:**

- [x] Adapter invokes `git --no-pager diff --staged --name-status` with
      `shell=False`.
- [x] Adapter uses the composition-owned working directory and timeout.
- [x] Adapter parses staged status/path output into staged file DTOs.
- [x] Adapter parses rename/copy `R*`/`C*` records and exposes the canonical new
      path for per-file diff; old-path lookup variants are deferred.
- [x] Adapter fails clearly for no staged files, not-a-repository, unavailable
      git, timeout, non-zero git failure, and decode failure.
- [x] Adapter does not include raw stderr, raw diff content, or unsafe private
      diagnostics in application-safe errors.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/test_adapter.py`

**Dependencies:** Tasks 1-2.

**Files likely touched:**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/adapter.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/__init__.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/test_adapter.py`

**Estimated scope:** M: 2-3 files.

#### Task 4: Implement per-file staged diff loading with staged path validation

**Description:** Add adapter behavior for loading a diff for one staged file path.
The adapter must validate the requested path against the staged file list before
constructing the git diff argv.

**Acceptance criteria:**

- [x] Unsafe paths are rejected before any per-file git diff command runs.
- [x] Paths not present in the staged file list are rejected.
- [x] Adapter invokes `git --no-pager diff --staged -- <path>` only after
      validation.
- [x] Adapter applies `GitStagedDiffBounds` to returned per-file diff text.
- [x] Empty per-file output and oversized output fail clearly before raw output is
      returned.
- [x] Tests prove the model cannot supply arbitrary git flags or pathspecs.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/test_adapter.py`

**Dependencies:** Task 3.

**Files likely touched:**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/adapter.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/test_adapter.py`

**Estimated scope:** M: 2 files.

### Checkpoint: Adapter behavior

- [x] `uv run pytest tests/unit/features/developer_workflow`
- [x] Subprocess adapter tests use fake runners and do not depend on ambient git
      state.
- [x] All git command argv assertions include `git`, `--no-pager`, read-only
      `diff`, `--staged`, and expected path separator behavior for per-file diff.

### Phase 3: Registered Tool Adapter

#### Task 5: Add the staged git registered-tool bridge

**Description:** Add a developer-workflow bridge that converts staged git
application capabilities into agent-runtime application-owned registered-tool
contracts without importing agent-runtime adapter internals.

**Acceptance criteria:**

- [x] Factory creates exactly `git_staged_files`, `git_staged_diff`, and
      `git_staged_file_diff` tools.
- [x] Each tool has the expected `ToolDefinition` name, description, and argument
      schema.
- [x] `git_staged_files` and `git_staged_diff` use empty argument schemas.
- [x] `git_staged_file_diff` requires only `path` and rejects additional
      arguments.
- [x] Successful handlers return deterministic, model-friendly text.
- [x] Invalid arguments raise `ValueError` so the registered-tool executor maps
      them to invalid tool request behavior.
- [x] Handlers catch `GitStagedChangesLoadError` and translate it to a safe
      executor-mapped tool failure, without exposing raw stderr, private paths,
      raw diff text, or sensitive diagnostics.
- [x] Staged-git load failures are translated to safe tool failures without raw
      sensitive diagnostics.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_registered_tool/test_adapter.py`

**Dependencies:** Tasks 1-4.

**Files likely touched:**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_registered_tool/adapter.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_registered_tool/__init__.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_registered_tool/test_adapter.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_registered_tool/__init__.py`
- The developer-workflow registered-tool bridge module, importing only
  agent-runtime application-owned tool contracts.
- `src/fabrica/features/agent_runtime/application/ports/registered_tool.py`
- `src/fabrica/features/agent_runtime/application/ports/__init__.py`
- The agent-runtime application boundary module that owns registered-tool
  callable contracts promoted from adapter internals.
- `src/fabrica/features/agent_runtime/adapters/outbound/registered_tool/adapter.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/registered_tool/__init__.py`

**Estimated scope:** M: 3 files.

#### Task 6: Verify tool-loop integration and output bounding

**Description:** Prove staged git registered tools behave correctly when executed
through the existing registered-tool and tool-loop mechanisms.

**Acceptance criteria:**

- [x] Tool definitions are available only when explicitly supplied to a composed
      runtime.
- [x] Tool result truncation and limit-exceeded behavior remain governed by
      `ToolLoopLimits.max_tool_result_chars`.
- [x] Existing registered-tool executor behavior remains unchanged for unknown
      tools, invalid arguments, failures, and duplicate names.
- [x] No ambient/global tool exposure is introduced.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_registered_tool/test_adapter.py`
- [x] `uv run pytest tests/unit/features/agent_runtime/adapters/outbound/registered_tool/test_adapter.py`
- [x] `uv run pytest tests/unit/features/agent_runtime/application/test_run_tool_loop.py`

**Dependencies:** Task 5.

**Files likely touched:**

- New registered-tool bridge tests.
- Possibly existing agent-runtime tool-loop tests if integration gaps are found.

**Estimated scope:** S: 1-2 files.

### Checkpoint: Tool adapter behavior

- [x] Registered-tool adapter tests pass.
- [x] Agent-runtime registered-tool and tool-loop tests pass.
- [x] Tool exposure remains explicit and composition-time only.

### Phase 4: Composition Root Helpers

#### Task 7: Add explicit staged git tool composition helper(s)

**Description:** Add bootstrap helper(s) that construct staged git registered
tools with a controlled working directory, bounds, timeout, and diagnostic mode.
These helpers should make tool exposure easy but never automatic.

**Acceptance criteria:**

- [x] Composition can create staged git registered tools with configured working
      directory, bounds, timeout, and diagnostics.
- [x] Helper construction does not read git state, call models, read Codex
      credentials, execute tools, or perform network I/O.
- [x] Existing `create_registered_tool_loop_runtime` and
      `create_model_driven_skill_runtime` remain opt-in and explicit.
- [x] Existing `create_codex_commit_message_workflow` remains deterministic and
      does not receive staged git tools by default.

**Verification:**

- [x] `uv run pytest tests/integration/features/developer_workflow/test_staged_git_tools_composition.py`
- [x] `uv run pytest tests/integration/features/developer_workflow/test_commit_message_composition.py`

**Dependencies:** Tasks 5-6.

**Files likely touched:**

- `src/fabrica/bootstrap/local_agent_runtime.py`
- `src/fabrica/bootstrap/__init__.py` if the new helper is part of the
  public bootstrap surface.
- `tests/integration/features/developer_workflow/test_staged_git_tools_composition.py`
- `tests/integration/features/developer_workflow/test_commit_message_composition.py`

**Estimated scope:** M: 2-4 files.

### Checkpoint: Composition boundaries

- [x] Developer-workflow integration tests pass.
- [x] Commit-message workflow still loads staged diff before runtime invocation.
- [x] No global/default model-callable git tools are introduced.

### Phase 5: Documentation and Quality Gate

#### Task 8: Update documentation for optional staged git tools

**Description:** Update project-facing documentation if the new composition helper
or optional tools are user-visible. Keep documentation concise and avoid
duplicating the full spec.

**Acceptance criteria:**

- [x] Documentation describes the tools as optional, read-only, staged-only, and
      explicitly composed.
- [x] Documentation states these tools are separate from deterministic
      `commit-message` staged diff loading.
- [x] Documentation does not imply arbitrary git execution, unstaged inspection,
      or repository mutation support.
- [x] Any environment/configuration changes are documented if introduced; if no
      configuration changes are introduced, note that no settings docs are needed.

**Verification:**

- [x] Documentation reviewed for consistency with
      `docs/specs/model-callable-staged-git-tools-spec.md`.

**Dependencies:** Task 7.

**Files likely touched:**

- `README.md`
- Possibly `docs/specs/model-callable-staged-git-tools-spec.md` only if
  implementation decisions need a small clarifying note.

**Estimated scope:** XS/S: 1-2 files.

#### Task 9: Run the full local quality gate

**Description:** Run focused checks first during implementation, then the full
project quality gate before handoff.

**Acceptance criteria:**

- [x] Formatting applied.
- [x] Lint passes.
- [x] Type check passes.
- [x] Full tests pass.
- [x] Any skipped, failing, or unavailable checks are documented with reason and
      next action.

**Verification:**

- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run ty check src tests`
- [x] `uv run pytest`

**Dependencies:** Tasks 1-8.

**Files likely touched:**

- None unless formatting changes files.

**Estimated scope:** XS operational task.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Tool adapter becomes arbitrary git execution | High | Keep exactly three fixed handlers; never pass model-supplied flags, cwd, or raw pathspecs. |
| Per-file diff path validation misses unsafe cases | High | Centralize safe relative path validation in DTO/application boundary tests and validate staged-list membership before per-file diff. |
| Rename handling becomes ambiguous | Medium | Parse rename/copy records explicitly; for v1, accept the canonical new path exposed by `git_staged_files` and defer old-path variants. |
| Commit-message workflow accidentally starts relying on tools | High | Keep `PrepareCommitMessageRun` on deterministic full diff loading and preserve composition tests. |
| Tool errors leak raw stderr, raw paths, or private diagnostics | Medium | Use normalized application-safe errors and safe metadata; keep verbose diagnostics explicit and non-secret. |
| Output bounds are applied inconsistently | Medium | Apply `GitStagedDiffBounds` before returning git diff DTOs and rely on `RegisteredToolExecutor`/`ToolLoopLimits` for final tool-loop bounding. |
| Tests accidentally depend on the developer's real staged files | Medium | Use fake git runners for unit tests and temporary repositories for integration tests only. |
| Composition helper construction performs I/O too early | Low | Keep construction lazy: tools run git only when their handlers are invoked. |

## Open Questions

- Should `git_staged_files` stay as plain `STATUS<TAB>path` text for v1, or use
  JSON-ish structured text? Recommendation: start with plain deterministic text.
- Should staged git tools be associated with selected skills, generic explicit
  tool-loop runtimes, or both? Recommendation: provide plain registered tools that
  can be used in either explicit composition path without enabling them by
  default.

## Parallelization Opportunities

- Tasks 1-2 should be sequential because the port depends on DTO shape.
- Tasks 3-4 should be sequential because per-file diff validation depends on file
  listing behavior.
- Task 5 can begin after the application boundary is stable, but final tests need
  adapter behavior from Tasks 3-4.
- Task 8 documentation can be drafted after Task 7 clarifies the final public
  helper names.
- Task 9 must run after all implementation and documentation tasks.

## Implementation Readiness Checklist

- [x] Source spec reviewed.
- [x] Existing staged diff DTO, port, subprocess adapter, tests, registered-tool
      adapter, and composition root inspected.
- [x] Tasks include acceptance criteria and verification steps.
- [x] Dependencies and sequencing constraints are identified.
- [x] No implementation task is larger than Medium.
- [x] Checkpoints are included between major phases.
- [x] Risks, mitigations, assumptions, and open questions are captured.
- [x] Plan states how progress checkboxes should be maintained during
      implementation.
