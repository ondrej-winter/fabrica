# Implementation Plan: Interactive Confirmed Commit Flow

## Overview

Implement the MVP `fabrica commit` workflow described in
`docs/specs/interactive-confirmed-commit-flow-spec.md`. The command will reuse
the existing staged-only evidence-first commit-message generation path, print
the generated recommendation once, prompt the developer for explicit approval,
and only then create a real git commit using the exact generated
`CommitMessageRecommendation.commit_message`. The existing
`fabrica commit-message` command remains read-only.

## Goal

Deliver a conservative interactive git commit workflow that turns Fabrica's
generated Conventional Commit recommendation into a commit only after explicit
human confirmation.

## Deliverables

- A new `fabrica commit` CLI subcommand with the same relevant model/skill
  options as `commit-message`.
- Developer-workflow application DTOs, a thin application use case, and an
  outbound port for safe git commit creation.
- A git commit subprocess adapter using `git commit --file <tempfile>` with
  explicit non-shell argv.
- Composition wiring in `src/fabrica/bootstrap/local_agent_runtime.py` for the
  confirmed commit workflow.
- CLI runner prompt handling for approval/rejection/cancellation.
- Unit and integration tests covering parser, runner, application boundary,
  adapter behavior, composition, approval, rejection, and failure paths.
- README updates documenting the mutating command and preserving
  `commit-message` as the read-only preview command.

## Success Criteria

- `uv run fabrica commit` generates and displays the same recommendation block
  format as `fabrica commit-message` before prompting.
- Only trimmed, case-insensitive `y` or `yes` creates a commit.
- `n`, `no`, empty input, EOF, and unknown answers create no commit and exit
  `0`.
- Ctrl-C/interrupted input creates no commit and exits non-zero.
- The git commit adapter passes the exact generated message through a temporary
  commit-message file and `git commit --file <tempfile>`.
- Successful commits print `Committed as <short-sha>.` when the short hash is
  available.
- `fabrica commit-message` remains read-only and its existing tests continue to
  pass.
- Default automated tests remain deterministic and offline.
- Full quality gate passes: `uv run ruff format .`, `uv run ruff check .`,
  `uv run ty check src tests`, `uv run pytest`.

## Constraints and Non-Goals

- Do not mutate `fabrica commit-message` into a committing command.
- Do not auto-stage unstaged files, inspect unstaged changes, auto-push, bypass
  hooks, open an editor, regenerate on rejection, add JSON output, or add
  `--yes`/non-interactive approval flags.
- Keep prompt handling in the inbound CLI adapter.
- Keep git commit orchestration behind a developer-workflow-owned application
  use case and git commit execution behind a developer-workflow-owned outbound
  port and adapter.
- Never let model output choose git flags, repository paths, pathspecs, or shell
  commands.
- Preserve the composition-owned working directory model already used by staged
  git inspection.

## Architecture Decisions

- **Separate CLI command:** Add `CliCommitCommand` rather than overloading
  `CliCommitMessageCommand`, making the mutating boundary explicit.
- **Shared options shape:** Let `commit` mirror the relevant `commit-message`
  options: `--skill`, `--model`, `--reasoning-effort`, and `--skill-root`.
- **Application-owned git commit boundary:** Add DTOs such as
  `CreateGitCommitCommand` and `GitCommitResult`, plus a `GitCommitCreator`
  outbound port, `GitCommitError` application-safe exception, and a thin
  application use case such as `CreateGitCommit`.
- **Adapter-owned subprocess details:** Implement `git_commit_subprocess/`
  separately from the read-only staged-git adapter to keep mutating behavior
  isolated and obvious.
- **CLI-owned confirmation:** The CLI runner prints the recommendation, prompts
  `[y/N]`, and calls the commit workflow only after explicit approval.
- **Composition wrapper:** Add a composed workflow that first generates the
  recommendation through the existing `CommitMessageWorkflow`, then commits
  through the new git commit port after CLI approval.
- **No output parsing:** The confirmed commit flow must access the original
  `CommitMessageRecommendation.commit_message` object/value and must not derive
  the final git message by parsing formatted terminal output.

## Progress Tracking Requirement

Treat this plan as a living artifact during implementation. After each completed
task or meaningful scope change:

- check off completed tasks, acceptance criteria, verification items, and
  checkpoints;
- leave unfinished or unverified items unchecked;
- add discovered work or sequencing changes;
- record blockers, assumptions, and deviations that affect remaining work.

## Task List

### Phase 1: Application Commit Boundary

#### Task 1: Add git commit DTOs and outbound port

**Description:** Define the application boundary for creating a git commit from
an already-approved generated message.

**Acceptance criteria:**

- [x] Adds immutable DTOs for commit creation and result, e.g.
  `CreateGitCommitCommand(message: str)` and
  `GitCommitResult(short_hash: str | None = None)`.
- [x] `CreateGitCommitCommand` rejects empty or whitespace-only commit messages
  while storing valid message text unchanged, including leading/trailing
  newlines or multiline body/footer formatting when present.
- [x] Adds a focused `GitCommitCreator` protocol and `GitCommitError` with safe
  metadata.
- [x] Adds a thin application use case, e.g. `CreateGitCommit`, that validates
  the application command/result boundary and delegates execution to the
  `GitCommitCreator` outbound port.
- [x] Exports the new DTOs and port from developer-workflow application
  `__init__.py` files.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/`
- [x] `uv run ty check src tests`

**Dependencies:** None

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/dtos/git_commit.py`
- `src/fabrica/features/developer_workflow/application/dtos/__init__.py`
- `src/fabrica/features/developer_workflow/application/ports/git_commit.py`
- `src/fabrica/features/developer_workflow/application/ports/__init__.py`
- `src/fabrica/features/developer_workflow/application/use_cases/create_git_commit.py`
- `src/fabrica/features/developer_workflow/application/use_cases/__init__.py`
- `tests/unit/features/developer_workflow/application/test_git_commit_dtos.py`
- `tests/unit/features/developer_workflow/application/test_create_git_commit.py`

**Estimated scope:** Medium

#### Task 2: Add git commit subprocess adapter

**Description:** Implement the mutating outbound adapter that writes the approved
commit message to a temporary file and invokes git safely.

**Acceptance criteria:**

- [x] Adapter uses explicit argv with `shell=False` through an injectable runner
  boundary.
- [x] Adapter writes the exact approved message to a temporary UTF-8
  commit-message file.
- [x] Adapter runs `git --no-pager commit --file <tempfile>` from the
  composition-owned working directory.
- [x] Single-line and multiline messages, including bodies and footers, are
  preserved exactly in the temp file.
- [x] The temporary commit-message file is cleaned up after success, git
  non-zero failure, timeout, and subprocess start failure.
- [x] Git unavailable, not a repository, no staged changes, hook failure,
  timeout, and generic non-zero failures map to `GitCommitError` with safe
  metadata.
- [x] On success, adapter obtains the new short hash when available, likely
  through a second safe `git --no-pager rev-parse --short HEAD` call.
- [x] If `git commit --file <tempfile>` succeeds but short-hash lookup fails,
  the adapter returns success with `short_hash=None` and safe diagnostic
  metadata rather than reporting the commit itself as failed.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/adapters/outbound/git_commit_subprocess/`
- [x] `uv run ty check src tests`

**Dependencies:** Task 1

**Files likely touched:**

- `src/fabrica/features/developer_workflow/adapters/outbound/git_commit_subprocess/__init__.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_commit_subprocess/adapter.py`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_commit_subprocess/command_runner.py`
  or reuse-compatible local runner types
- `src/fabrica/features/developer_workflow/adapters/outbound/git_commit_subprocess/commands.py`
- `tests/unit/features/developer_workflow/adapters/outbound/git_commit_subprocess/test_adapter.py`

**Estimated scope:** Medium

### Checkpoint: Commit Boundary

- [x] Developer-workflow application tests pass.
- [x] Git commit subprocess adapter unit tests pass.
- [x] Mutating git behavior is isolated under `git_commit_subprocess/` and not
  mixed into read-only staged-git modules.

### Phase 2: Composed Confirmed Commit Workflow

#### Task 3: Add confirmed commit workflow composition

**Description:** Wire a composed workflow that can generate a recommendation and
create a git commit after the CLI confirms approval.

**Acceptance criteria:**

- [x] Adds a workflow class/result shape for the confirmed commit path, distinct
  from read-only `CommitMessageWorkflow`.
- [x] Reuses the existing `CommitMessageWorkflow` or `GenerateCommitMessage` path
  rather than duplicating model orchestration.
- [x] Passes exactly `CommitMessageRecommendation.commit_message` into
  `CreateGitCommitCommand`.
- [x] Carries the original recommendation object/value through the confirmed
  commit path; implementation does not parse the commit message back out of
  formatted `LocalAgentRunResult.output_text`.
- [x] Preserves usage and cost evidence from recommendation generation for
  optional CLI evidence output.
- [x] Maps `GitCommitError` to safe user-facing runtime failure results that
  indicate commit mutation was attempted.

**Verification:**

- [x] `uv run pytest tests/integration/features/developer_workflow/test_confirmed_commit_composition.py`
- [x] `uv run pytest tests/integration/features/developer_workflow/test_commit_message_composition.py`

**Dependencies:** Tasks 1-2

**Files likely touched:**

- `src/fabrica/bootstrap/local_agent_runtime.py`
- `src/fabrica/bootstrap/__init__.py`
- Developer-workflow application use-case files from Task 1 as needed
- `tests/integration/features/developer_workflow/test_confirmed_commit_composition.py`
- `tests/integration/features/developer_workflow/test_commit_message_composition.py`

**Estimated scope:** Medium

#### Task 4: Add temporary-repository integration tests for commit creation

**Description:** Prove with disposable git repositories that approval creates
exactly one commit and rejection/failure paths do not create successful commits.

**Acceptance criteria:**

- [x] Approval path creates exactly one commit with the generated
  subject/body/footer.
- [ ] Rejection path creates no commit and preserves staged changes.
- [x] No staged changes fails before prompting and creates no commit.
- [x] Git commit failure returns non-zero and does not report success.
- [x] Tests configure local git identity only inside the temporary repository
  when required.

**Note:** Rejection is intentionally left for the CLI-owned prompt behavior in
Task 6 because the confirmed commit workflow is the already-approved application
path and does not model rejection input.

**Verification:**

- [x] `uv run pytest tests/integration/features/developer_workflow/`

**Dependencies:** Tasks 2-3

**Files likely touched:**

- `tests/integration/features/developer_workflow/test_confirmed_commit_composition.py`
- Possibly shared local helper code inside that test module only

**Estimated scope:** Small to Medium

### Checkpoint: End-to-End Commit Core

- [x] Recommendation generation remains staged-only.
- [x] Approved generated message creates a real commit in a temporary repo.
- [x] Failure and rejection paths do not create commits.
- [x] Existing `commit-message` composition tests still pass.

### Phase 3: CLI Parser and Runner

#### Task 5: Add `fabrica commit` parser support

**Description:** Add a distinct CLI parsed command for the mutating interactive
workflow.

**Acceptance criteria:**

- [x] Parser recognizes `commit` as a separate subcommand from
  `commit-message`.
- [x] `commit` accepts `--skill`, `--model`, `--reasoning-effort`, and
  `--skill-root` consistently with `commit-message`.
- [x] Help text clearly marks `commit-message` as read-only and `commit` as
  mutating after confirmation.
- [x] Parsed command DTOs remain immutable.

**Verification:**

- [x] `uv run pytest tests/unit/features/agent_runtime/adapters/inbound/cli/test_parser.py`

**Dependencies:** None, but should land after Task 1 to align names.

**Files likely touched:**

- `src/fabrica/features/agent_runtime/adapters/inbound/cli/parser.py`
- `src/fabrica/features/agent_runtime/adapters/inbound/cli/__init__.py`
- `tests/unit/features/agent_runtime/adapters/inbound/cli/test_parser.py`

**Estimated scope:** Small

#### Task 6: Add CLI runner prompt and approval behavior

**Description:** Implement terminal confirmation handling in the inbound CLI
adapter with deterministic fakes for unit tests.

**Acceptance criteria:**

- [x] Runner prints the full recommendation block once before prompting.
- [x] Prompt text is `Commit with this message? [y/N]` or equivalent
  conservative default.
- [x] Prompt handling uses injected input/prompt dependencies or an explicit
  `stdin` boundary so approval, EOF, empty input, and interrupted input are
  deterministic in unit tests.
- [x] Only trimmed, case-insensitive `y` or `yes` invokes the git commit
  workflow.
- [x] `n`, `no`, empty input, EOF, and unrecognized answers print a concise
  no-op message, do not call the commit port/workflow, and exit `0`.
- [x] Keyboard interrupt prints/returns a failure path and exits non-zero without
  committing.
- [x] Recommendation-generation failures skip prompting and skip commit
  execution.
- [x] `--print-usage` and `--print-prices` append recommendation-generation
  evidence when requested and available after generation failure, rejection,
  approval success, and approval commit failure, without duplicating the
  recommendation block.

**Verification:**

- [x] `uv run pytest tests/unit/features/agent_runtime/adapters/inbound/cli/test_commit_command.py`
- [x] `uv run pytest tests/unit/features/agent_runtime/adapters/inbound/cli/test_commit_message_command.py`

**Dependencies:** Tasks 3 and 5

**Files likely touched:**

- `src/fabrica/features/agent_runtime/adapters/inbound/cli/runner.py`
- `src/fabrica/features/agent_runtime/adapters/inbound/cli/output.py` if output
  helpers are added
- `tests/unit/features/agent_runtime/adapters/inbound/cli/test_commit_command.py`
- `tests/unit/features/agent_runtime/adapters/inbound/cli/test_commit_message_command.py`

**Estimated scope:** Medium

#### Task 7: Wire default CLI composition for `fabrica commit`

**Description:** Connect the parsed `commit` command to the Codex-backed
confirmed commit workflow.

**Acceptance criteria:**

- [x] Default CLI runner creates the confirmed commit workflow through bootstrap
  composition.
- [x] Model, reasoning effort, skill roots, verbose diagnostics, and git working
  directory behavior match `commit-message` where applicable.
- [x] CLI entrypoint tests cover `commit` without live Codex or ambient git
  state.
- [x] Existing `commit-message` CLI behavior remains unchanged.

**Verification:**

- [x] `uv run pytest tests/integration/features/agent_runtime/test_cli_entrypoint.py`
- [x] `uv run pytest tests/unit/features/agent_runtime/adapters/inbound/cli/`

**Dependencies:** Tasks 3, 5, and 6

**Files likely touched:**

- `src/fabrica/features/agent_runtime/adapters/inbound/cli/runner.py`
- `src/fabrica/bootstrap/local_agent_runtime.py`
- `tests/integration/features/agent_runtime/test_cli_entrypoint.py`
- CLI unit tests as needed

**Estimated scope:** Small to Medium

### Checkpoint: CLI Workflow

- [x] `commit` parser, help, and runner tests pass.
- [x] CLI runner tests prove rejection and interrupted input do not invoke commit
  execution.
- [x] CLI entrypoint remains deterministic and offline.
- [x] `commit-message` remains read-only and tested.

### Phase 4: Documentation and Final Validation

#### Task 8: Update README usage documentation

**Description:** Document the new mutating command and the safety distinction
between `commit-message` and `commit`.

**Acceptance criteria:**

- [x] README shows `uv run fabrica commit-message` as the read-only preview
  command.
- [x] README shows `uv run fabrica commit` as the interactive mutating command.
- [x] README states that `commit` requires explicit `y`/`yes` approval before
  `git commit`.
- [x] README states that rejection/default no-op leaves staged changes
  untouched.
- [x] README does not document unsupported `--yes`, edit, regenerate,
  auto-stage, hook-bypass, JSON, or auto-push behavior.

**Verification:**

- [x] Documentation review against
  `docs/specs/interactive-confirmed-commit-flow-spec.md`.

**Dependencies:** Tasks 5-7

**Files likely touched:**

- `README.md`

**Estimated scope:** Small

#### Task 9: Run full quality gate and update plan status

**Description:** Format, lint, type-check, test, and mark the implementation plan
with completed/verified items.

**Acceptance criteria:**

- [x] `uv run ruff format .` passes.
- [x] `uv run ruff check .` passes.
- [x] `uv run ty check src tests` passes.
- [x] `uv run pytest` passes.
- [x] Plan checkboxes reflect completed tasks and any deviations.
- [x] Handoff notes list files changed, validation run, assumptions, and
  deviations.

**Verification:**

- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run ty check src tests`
- [x] `uv run pytest`

**Dependencies:** Tasks 1-8

**Files likely touched:**

- `docs/plans/interactive-confirmed-commit-flow-plan.md`
- Any files updated by formatting

**Estimated scope:** Small

### Checkpoint: Complete

- [ ] All task acceptance criteria are complete.
- [x] Full local quality gate passes or any unrun/failing checks are documented
  with reasons.
- [x] README and CLI help accurately describe the mutating safety boundary.
- [x] No `--yes`/non-interactive approval path exists.
- [x] No model output can influence git flags, paths, or shell commands.

**Remaining documented deviation:** Task 4's temporary-repository rejection-path
acceptance criterion remains unchecked because rejection is owned and covered by
the CLI prompt tests in Task 6; the confirmed commit workflow models the
already-approved application path and has no rejection input.

## Dependency Graph

```text
Application commit DTOs and port
  -> Git commit subprocess adapter
    -> Confirmed commit composition
      -> Temporary-repository integration tests

CLI commit parser
  -> CLI runner confirmation behavior
    -> Default CLI composition
      -> CLI entrypoint coverage

Core workflow + CLI surface
  -> README documentation
  -> Full quality gate
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Accidentally weakening `commit-message` read-only behavior | High | Keep `commit` as a separate parsed command and preserve existing `commit-message` tests. |
| Committing without explicit approval on EOF/empty/Ctrl-C | High | Unit-test each input case with injected stdin/fakes before wiring default CLI behavior. |
| Multiline commit messages are altered by shell quoting or `-m` splitting | High | Use temp file plus `git commit --file <tempfile>` and adapter tests that inspect file content. |
| Commit flow accidentally parses formatted CLI output to recover the final message | High | Carry the original `CommitMessageRecommendation` or equivalent application result through composition and test that `commit_message` is passed directly. |
| Successful commit is reported as failed because post-commit hash lookup fails | Medium | Treat hash lookup as best-effort after successful `git commit`; return success with `short_hash=None` and safe diagnostics. |
| Temporary commit-message files are left behind | Medium | Use a managed temp file/directory and test cleanup on success and representative failures. |
| Git hooks fail after approval and confuse users | Medium | Surface safe failure that makes clear the commit was attempted; do not bypass hooks. |
| Temporary repo tests depend on developer git config | Medium | Configure test-local `user.name` and `user.email` inside each temp repository. |
| CLI output duplicates the recommendation block | Medium | Centralize recommendation display and test exact stdout for the prompt flow. |
| Commit adapter leaks raw stderr or sensitive paths | Medium | Use safe metadata defaults and only include verbose working directory diagnostics when explicitly enabled. |

## Open Questions

None blocking. The spec resolves command name, rejection/cancellation exit
behavior, temp-file commit message handling, output shape, and non-interactive
approval policy.

## Assumptions

- `CommitMessageRecommendation.commit_message` is the canonical approved message
  source.
- The confirmed commit implementation can expose or carry the original
  recommendation object/value through composition without parsing terminal
  output.
- `fabrica commit` can reuse the same selected skill/model/reasoning/skill-root
  options as `fabrica commit-message`.
- The first implementation can add a new plan file at
  `docs/plans/interactive-confirmed-commit-flow-plan.md` and keep it updated
  during implementation.
- Git hook behavior remains git default behavior.

## Parallelization Opportunities

- Task 5 parser work can proceed in parallel with Tasks 1-2 once command naming
  is fixed.
- Task 8 documentation can start after parser/help wording is known, but should
  finish after runner behavior is implemented.
- Task 9 must remain last.
