# Implementation Plan: Read-Only Git Context Tools

## Overview

Implement the read-only git context capabilities described in
`docs/specs/read-only-git-context-tools-spec.md` as an explicit
`developer_workflow` extension. The implementation should add bounded,
non-mutating worktree, commit, and ref/range inspection through application-owned
DTOs and focused ports, read-only subprocess-backed outbound adapters,
registered-tool factories for opt-in model-callable exposure, and tests proving
safety boundaries and staged-only commit-message behavior remain unchanged.

This plan intentionally excludes a `fabrica git ...` CLI surface. Read-only git
context is exposed only as application contracts, outbound adapters, and
explicitly composed registered tools.

## Goal

Deliver explicit read-only git context adapters and model-callable tools for safe
repository inspection without exposing arbitrary git command execution,
repository mutation, network git operations, or ambient model powers.

## Deliverables

- Read-only git context DTOs under
  `src/fabrica/features/developer_workflow/application/dtos/`.
- Focused application ports under
  `src/fabrica/features/developer_workflow/application/ports/`, likely:
  - `GitWorktreeContextLoader`
  - `GitCommitContextLoader`
  - `GitRefContextLoader`
- Subprocess adapter code under
  `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/`
  with fixed argv builders, validation helpers, parsing, and safe error mapping.
- Developer-workflow-owned registered-tool adapter(s), likely under
  `src/fabrica/features/developer_workflow/adapters/outbound/git_context_registered_tool/`.
- Composition helpers in `src/fabrica/bootstrap/composition.py` for explicit
  opt-in registration.
- Unit tests mirroring the new source paths under
  `tests/unit/features/developer_workflow/` plus relevant composition tests.
- Updates to `docs/specs/read-only-git-context-tools-spec.md` and this plan.

## Success Criteria

- Worktree, commit, and ref/range context tools are separated by stable intent
  and output shape.
- All git invocations are read-only, use explicit argv lists, run with
  `shell=False`, disable paging, and use composition-owned working directories.
- Diff/log/tool result output is bounded and fails safely when bounds are
  exceeded.
- Commit-ish, ref, count, and path inputs are validated before inspection
  commands run.
- File path arguments are safe relative paths and are accepted only when present
  in the corresponding changed-file list.
- Registered tools are available only through explicit composition helpers and
  are not ambient/global runtime powers.
- Existing staged tools and `fabrica commit-message` remain staged-only and
  unchanged in safety contract.
- No `fabrica git ...` CLI commands are added for this capability.
- Default tests remain deterministic/offline and do not depend on the developer's
  current repository state.
- Full local quality gate passes:
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run ty check src tests`
  - `uv run pytest`

## Constraints and Non-Goals

- Do **not** expose arbitrary git command execution.
- Do **not** run mutating or network git operations: no `add`, `reset`,
  `checkout`, `switch`, `stash`, `commit`, `push`, `pull`, `fetch`, merge,
  rebase, tag creation, etc.
- Do **not** let model-supplied arguments choose git commands, flags, pathspecs,
  or working directories.
- Do **not** add human-facing `fabrica git ...` CLI commands for this capability.
- Do **not** silently broaden `commit-message` beyond staged evidence.
- Do **not** inspect unstaged changes inside staged commit-message workflows.
- Do **not** add blame/provenance, release/tag, changelog, or hosting-provider
  API tools in the MVP.
- Do **not** leak raw private diagnostics, full stderr, secrets, raw file
  contents, or high-cardinality unsafe values in errors.

## Architecture Decisions

- **Feature ownership:** Keep the capability in `developer_workflow`, matching
  existing staged-git ownership.
- **Incremental reuse:** Reuse proven staged-git patterns: immutable DTOs,
  `StrEnum` closed vocabularies, safe path validation, bounded diff DTOs,
  injectable git runner, command-builder unit tests, safe normalized application
  errors, and registered-tool factories.
- **Separate contexts:** Add separate DTOs/ports/adapters for worktree, commit,
  and ref/range context instead of one broad git service.
- **Subprocess consistency:** Keep all git subprocess behavior under
  `adapters/outbound/git_subprocess/`; add cohesive modules rather than a new
  unrelated adapter style.
- **Explicit tool bridge:** Registered-tool adapters may import agent-runtime tool
  DTOs/ports because they bridge developer workflow capabilities into the
  agent-runtime tool system.
- **Three-dot default for PR-like range diffs:** Use three-dot comparison
  semantics for ref/range diff tools in v1 because the spec prioritizes
  PR/review summarization. Record any deviation if implementation evidence or
  user direction changes it.
- **Structured text output first:** Use deterministic structured text for tool
  output initially, consistent with existing staged registered tools, unless
  strict JSON becomes a future requirement.
- **Commit log v1 scope:** Keep `git_commit_log` on `HEAD` with bounded `count`
  only in v1; defer optional `ref` until ref validation and UX are proven through
  range tools.
- **Rename/copy path contract:** Changed-file DTOs use the new/destination path
  as the canonical `path` accepted by per-file diff tools. Rename/copy records
  expose the source path as `old_path` metadata only.
- **Validation failure taxonomy:** Distinguish model/user argument validation from
  subprocess git failures with explicit `INVALID_ARGUMENT` and
  `NO_MATCHING_CHANGES` categories.
- **Internal composition in v1:** Keep read-only git context tool composition
  helpers internal in v1; do not export them from `fabrica.bootstrap.__all__`.
- **Status summary untracked paths:** Include a bounded untracked path list in
  `git_status_summary` by default.

## Progress Tracking Requirement

Treat this plan as a living artifact during implementation. After each completed
task or meaningful scope change:

- check off completed tasks, acceptance criteria, verification items, and
  checkpoints;
- leave unverified items unchecked;
- add newly discovered work or sequencing changes;
- record blockers, assumptions, deviations, and decisions that affect remaining
  work.

## Task List

### Phase 1: Application Contract Foundation

#### Task 1: Add shared read-only git context DTO primitives

**Description:** Add immutable DTO primitives and closed vocabularies for safe git
context values shared by worktree, commit, and ref/range tools.

**Acceptance criteria:**

- [x] Defines safe relative path validation for read-only git context without
  reusing staged-specific error wording.
- [x] Defines changed-file status DTOs that can represent name-status output,
  including renamed/copied paths when supported.
- [x] Rename/copy DTOs expose canonical `path` as the new/destination path and
  expose `old_path` as metadata for the source path.
- [x] Defines bounded diff/log/count settings with conservative defaults and
  maximums.
- [x] Defines normalized failure categories covering git unavailable, not
  repository, no matching changes, invalid ref/commit, oversized output, timeout,
  git failure, and decode failure.
- [x] Defines `INVALID_ARGUMENT` for invalid user/model inputs and
  `NO_MATCHING_CHANGES` for valid paths or refs that have no corresponding
  changed-file membership.
- [x] DTOs are immutable, typed, and exported from
  `developer_workflow.application.dtos`.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/test_git_context_dtos.py`
- [x] `uv run ty check src tests`

**Dependencies:** None

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/dtos/git_context.py`
- `src/fabrica/features/developer_workflow/application/dtos/__init__.py`
- `tests/unit/features/developer_workflow/application/test_git_context_dtos.py`

**Estimated scope:** Medium

#### Task 2: Add focused application ports and safe errors

**Description:** Add application-owned ports for worktree, commit, and ref/range
context inspection, plus layer-appropriate safe exceptions.

**Acceptance criteria:**

- [x] Adds focused protocols for worktree, commit, and ref/range context rather
  than a catch-all git service.
- [x] Port signatures use application DTOs and primitive validated inputs only;
  no subprocess, CLI, or framework types leak into ports.
- [x] Safe application error exposes normalized category and safe metadata.
- [x] Safe application errors distinguish validation failures from subprocess git
  failures with `INVALID_ARGUMENT` and `NO_MATCHING_CHANGES` categories.
- [x] Existing staged-git ports remain intact for staged-only workflows.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/test_git_context_ports.py`
- [x] `uv run pytest tests/unit/features/developer_workflow/application/test_git_staged_changes_dtos.py`

**Dependencies:** Task 1

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/ports/git_context.py`
- `src/fabrica/features/developer_workflow/application/ports/__init__.py`
- `tests/unit/features/developer_workflow/application/test_git_context_ports.py`

**Estimated scope:** Small

### Checkpoint: Application Contract

- [x] DTO and port tests pass.
- [x] No adapter/subprocess/framework imports appear in application DTOs or ports.
- [x] Staged-git public contracts remain available and staged-only.

### Phase 2: Subprocess Adapter Foundation

#### Task 3: Add fixed git context command builders and parsing helpers

**Description:** Add argv builders and parsers for read-only status, unstaged,
commit, and ref/range commands.

**Acceptance criteria:**

- [x] All argv builders include `git --no-pager` or the project's equivalent
  no-pager pattern.
- [x] No builder accepts arbitrary model/user git flags or command names.
- [x] Path arguments are placed only after `--` and only after validation.
- [x] Commit/ref validation builders use read-only inspection commands.
- [x] Name-status and log/detail parsers produce bounded application DTOs.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_commands.py`
- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_parsing.py`

**Dependencies:** Tasks 1-2

**Files likely touched:**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/context_commands.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/context_parsing.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_commands.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_parsing.py`

**Estimated scope:** Medium

#### Task 4: Add shared read-only git subprocess adapter error handling

**Description:** Factor reusable safe subprocess execution/error mapping for the
new context adapter without disrupting existing staged-git behavior.

**Acceptance criteria:**

- [x] Uses injectable `GitCommandRunner` and composition-owned working directory.
- [x] Maps git unavailable, timeout, decode failure, not-repository, invalid
  ref/commit, non-zero git failure, and oversized output to safe application
  errors.
- [x] Does not expose full stderr unless safe verbose diagnostics are explicitly
  enabled and still redacted/bounded.
- [x] Existing staged-git subprocess tests continue to pass.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context.py`
- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_staged_changes.py`

**Dependencies:** Tasks 1-3

**Files likely touched:**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/context.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/context_errors.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/__init__.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context.py`

**Estimated scope:** Medium

### Checkpoint: Subprocess Foundation

- [x] Command-builder and parser tests pass.
- [x] New adapter error mapping tests pass.
- [x] Existing staged subprocess tests pass unchanged.
- [x] Review confirms no mutating/network git command appears in argv builders.

### Phase 3: Worktree Context Slice

#### Task 5: Implement worktree status and unstaged context

**Description:** Implement `git_status_summary`, `git_unstaged_files`,
`git_unstaged_diff`, and `git_unstaged_file_diff` through the worktree context
port and subprocess adapter.

**Acceptance criteria:**

- [x] Status summary includes branch/detached state, HEAD short hash, upstream
  when available, staged/unstaged/untracked counts, and a bounded untracked path
  list by default.
- [x] Unstaged files list includes tracked unstaged paths/statuses and excludes
  staged-only changes.
- [x] Unstaged full diff is bounded and fails clearly when no unstaged tracked
  changes exist.
- [x] Unstaged file diff validates safe relative path and confirms the path
  appears in the unstaged file list before diffing.
- [x] Worktree tools do not affect existing staged commit-message evidence
  loading.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_worktree.py`
- [x] `uv run pytest tests/unit/features/developer_workflow/application/test_generate_commit_message.py`

**Dependencies:** Tasks 1-4

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/dtos/git_context.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/context.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_worktree.py`

**Estimated scope:** Medium

### Phase 4: Commit Context Slice

#### Task 6: Implement commit log and commit detail context

**Description:** Implement bounded commit history metadata and single-commit
detail inspection.

**Acceptance criteria:**

- [x] `git_commit_log` accepts optional bounded `count` and defaults to a
  conservative configured count.
- [x] Commit log returns hash, short hash, subject, author date, and decorations
  when available without raw diffs.
- [x] `git_commit_details` validates commit-ish as a commit object before
  inspection.
- [x] Commit details return hash, short hash, parents, author, author date,
  committer date, subject, body, and refs without raw diff output.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_commit.py`

**Dependencies:** Tasks 1-4

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/dtos/git_context.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/context.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_commit.py`

**Estimated scope:** Medium

#### Task 7: Implement commit changed-files and commit diff context

**Description:** Implement changed-file listing, bounded full commit diff, and
per-file commit diff for a validated commit.

**Acceptance criteria:**

- [x] `git_commit_changed_files` validates commit-ish and returns changed
  paths/statuses without raw diff.
- [x] `git_commit_diff` returns bounded full diff and fails with a safe narrowing
  suggestion when oversized.
- [x] `git_commit_file_diff` validates commit-ish, safe relative path, and
  changed-file membership before diffing.
- [x] Path validation accepts the canonical changed-file `path`; for
  renamed/copied files this is the new/destination path, while `old_path` remains
  metadata only.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_commit.py`

**Dependencies:** Task 6

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/dtos/git_context.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/context.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_commit.py`

**Estimated scope:** Medium

### Checkpoint: Commit Context

- [x] Commit context tests pass.
- [x] Commit validation runs before detail/diff commands.
- [x] Full diff failure suggests changed-files plus file-diff narrowing.

### Phase 5: Ref/Range Context Slice

#### Task 8: Implement ref changed-files, diff, file diff, ahead/behind, and merge-base

**Description:** Implement PR/review-style branch comparison tools using
validated refs and bounded output.

**Acceptance criteria:**

- [ ] `git_ref_changed_files` validates both refs and uses the chosen three-dot
  comparison semantics for v1.
- [ ] `git_ref_diff` validates refs, applies bounds, and suggests
  `git_ref_changed_files` plus `git_ref_file_diff` when oversized.
- [ ] `git_ref_file_diff` validates refs, safe path, and membership in changed
  files before diffing.
- [ ] Ref file-diff path membership follows the changed-file DTO contract:
  renamed/copied files are addressed by their new/destination `path` only.
- [ ] `git_branch_ahead_behind` defaults to upstream when available and never
  fetches.
- [ ] `git_merge_base` returns full and short merge-base hashes without mutating
  refs.

**Verification:**

- [ ] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_refs.py`

**Dependencies:** Tasks 1-4

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/dtos/git_context.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/context.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_subprocess/test_context_refs.py`

**Estimated scope:** Medium

### Checkpoint: Core Git Context Adapter

- [ ] Worktree, commit, and ref/range adapter tests pass.
- [ ] No mutating/network commands are present.
- [ ] All full diff paths have bounded-output behavior and narrowing guidance.

### Phase 6: Registered Tool Exposure

#### Task 9: Add registered-tool definitions and handlers for read-only git context

**Description:** Add atomic model-callable tools that wrap the application ports
and map safe results into deterministic text output.

**Acceptance criteria:**

- [ ] Adds one registered tool per spec-defined stable intent.
- [ ] Tool definitions use narrow JSON schemas with `additionalProperties: false`.
- [ ] Invalid arguments produce safe invalid request failures.
- [ ] Application errors map to safe tool failures without raw private
  diagnostics.
- [ ] Tool result text is bounded by existing tool-loop limits.
- [ ] Staged tools remain separate and are not replaced or overloaded.

**Verification:**

- [ ] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_context_registered_tool/test_adapter.py`
- [ ] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_staged_changes_registered_tool/test_adapter.py`

**Dependencies:** Tasks 5-8

**Files likely touched:**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_context_registered_tool/__init__.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_context_registered_tool/adapter.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_context_registered_tool/definitions.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_context_registered_tool/handlers.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_context_registered_tool/test_adapter.py`

**Estimated scope:** Medium

#### Task 10: Add explicit composition helpers for read-only git context tools

**Description:** Add bootstrap helpers/options to create read-only git context
registered tools only when requested.

**Acceptance criteria:**

- [ ] Adds composition options for working directory, bounds, timeout, and verbose
  diagnostics.
- [ ] Factory construction remains side-effect light and does not inspect git
  state.
- [ ] Tools are not globally enabled for every tool-loop or model-driven runtime.
- [ ] Read-only git context composition remains internal in v1 and is not exported
  from `fabrica.bootstrap.__all__`.
- [ ] Existing `create_staged_git_registered_tools` remains available and
  staged-only.

**Verification:**

- [ ] `uv run pytest tests/unit/test_bootstrap_api.py`
- [ ] `uv run pytest tests/integration/features/agent_runtime/test_tool_loop_composition.py`
- [ ] `uv run pytest tests/integration/features/developer_workflow/test_staged_git_tools_composition.py`
- [ ] `uv run pytest tests/integration/features/developer_workflow/test_read_only_git_context_tools_composition.py`

**Dependencies:** Task 9

**Files likely touched:**

- `src/fabrica/bootstrap/composition.py`
- `tests/unit/test_bootstrap_api.py` if internal helper placement changes the
  curated public bootstrap API contract
- `tests/integration/features/developer_workflow/test_read_only_git_context_tools_composition.py`

**Estimated scope:** Small to Medium

### Checkpoint: Model-Callable Exposure

- [ ] Registered-tool adapter tests pass.
- [ ] Composition tests prove explicit opt-in behavior.
- [ ] Existing staged-git registered-tool composition remains unchanged.
- [ ] No CLI command surface has been added.

### Phase 7: Documentation and Final Validation

#### Task 11: Update documentation for read-only git context tool behavior

**Description:** Document safety boundaries and explicit model-tool composition
behavior where user-facing or developer-facing documentation needs it.

**Acceptance criteria:**

- [ ] Documentation states read-only git context is adapters/tools only, not a
  `fabrica git ...` CLI surface.
- [ ] Documentation states registered tools are read-only and do not fetch or
  mutate repository state.
- [ ] Documentation clarifies that `commit-message` remains staged-only.
- [ ] `docs/README.md` continues to link to the spec and plan if the docs index
  pattern calls for it.

**Verification:**

- [ ] Documentation review against `docs/specs/read-only-git-context-tools-spec.md`.

**Dependencies:** Task 10

**Files likely touched:**

- `README.md` if tool/composition usage becomes user-facing
- `docs/README.md` if the docs index is updated
- `docs/plans/read-only-git-context-tools-plan.md`

**Estimated scope:** Small

#### Task 12: Run focused and full quality gates

**Description:** Run the configured validation commands and record any deviations.

**Acceptance criteria:**

- [ ] Focused developer workflow tests pass.
- [ ] Full formatting, linting, type checking, and tests pass.
- [ ] Handoff notes include files changed, validation performed, assumptions, and
  any deviations.

**Verification:**

- [ ] `uv run pytest tests/unit/features/developer_workflow`
- [ ] `uv run ruff format .`
- [ ] `uv run ruff check .`
- [ ] `uv run ty check src tests`
- [ ] `uv run pytest`

**Dependencies:** Tasks 1-11

**Files likely touched:**

- No new source files expected beyond previous tasks unless validation reveals
  fixes.

**Estimated scope:** Small

### Checkpoint: Complete

- [ ] All task acceptance criteria are complete.
- [ ] Full local quality gate passes or documented unrun/failing checks have clear
  reasons.
- [ ] Existing staged-only commit-message behavior is verified unchanged.
- [ ] No arbitrary, mutating, or network git capabilities were introduced.
- [ ] Tool exposure remains explicit opt-in.
- [ ] No `fabrica git ...` CLI commands were introduced.

## Dependency Graph

```text
Shared git context DTOs
  -> Focused application ports
    -> Command builders/parsers
      -> Subprocess adapter error handling
        -> Worktree context tools
        -> Commit context tools
        -> Ref/range context tools
          -> Registered-tool adapters
            -> Composition helper
              -> Documentation review
                -> Full quality gate
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Accidentally exposing arbitrary git execution | High | Use fixed argv builders only; unit-test no model/user-supplied flags or commands. |
| Mutating/network git command slips in | High | Keep command builders in one module; review/test command names against denylist. |
| `commit-message` safety contract changes | High | Preserve existing staged-git loader and run existing commit-message tests after each relevant phase. |
| Ref validation becomes too permissive | High | Validate refs/commit-ish with fixed read-only git validation commands before details/diffs. |
| Path traversal/pathspec injection | High | Validate safe relative paths, confirm membership in changed-file lists, pass paths only after `--`. |
| Full diffs overwhelm model/tool loop | Medium | Apply DTO diff bounds and rely on existing `ToolLoopLimits.max_tool_result_chars`. |
| Output format is hard for agents to parse | Medium | Use stable structured text in v1; leave strict JSON as a documented future option. |
| Adapter file grows too large | Medium | Split by responsibility if `context.py` exceeds cohesion/size thresholds: worktree, commit, refs. |
| Registered tools are enabled too broadly | Medium | Add explicit composition helper and tests proving tools are opt-in only. |
| CLI scope reappears during implementation | Medium | Keep CLI commands as a non-goal and include a checkpoint confirming no `fabrica git ...` surface was added. |

## Resolved v1 Decisions

The implementation plan can proceed with the following v1 decisions:

1. Use three-dot ref comparison semantics for PR-like workflows.
2. Keep `git_commit_log` limited to `HEAD` plus bounded `count` in v1; defer
   optional `ref`.
3. Include untracked file counts and a bounded untracked path list in
   `git_status_summary` by default.
4. Use stable structured text for registered-tool output rather than strict JSON
   in v1.
5. Start with conservative default bounds matching or below existing staged diff
   bounds, then tune only with evidence.
6. Address renamed/copied files by the new/destination path only; expose the
   source path as `old_path` metadata.
7. Keep read-only git context composition helpers internal in v1 and do not add
   them to `fabrica.bootstrap.__all__`.

## Parallelization Opportunities

- Tasks 6-7 (commit context) and Task 8 (ref/range context) can proceed in
  parallel after Tasks 1-4.
- Registered-tool tests can be drafted against agreed tool definitions once port
  contracts stabilize.
- Documentation can start after composition behavior is fixed.
- Task 12 must be last.
