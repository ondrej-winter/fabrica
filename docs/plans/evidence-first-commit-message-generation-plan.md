# Implementation Plan: Evidence-First Commit Message Generation

## Overview

Improve `fabrica commit-message` by replacing the current generic built-in
prompt with an evidence-first prompt that instructs the model to analyze staged
changes in three conceptual passes: file-level evidence, intent grouping, and
Conventional Commit synthesis. The implementation should preserve the existing
selected-skill workflow boundaries: staged changes only, read-only git access,
selected skill context as a separate bounded block, no repository mutation, and
deterministic offline tests.

## Goal

Deliver a prompt-level v1 implementation of evidence-first commit-message
generation so final recommendations describe the dominant intent of the staged
changes rather than vague summaries or file-by-file changelogs.

## Deliverables

- Updated implementation plan document under `docs/plans/`.
- Updated prompt construction in
  `src/fabrica/features/developer_workflow/application/use_cases/prepare_commit_message_run.py`.
- Updated focused unit tests in
  `tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`.
- Updated README note describing the staged-change, evidence-first,
  dominant-intent recommendation behavior without promising verbose evidence
  output.

## Success Criteria

- Prompt explicitly requires file-level evidence analysis, intent grouping, and
  Conventional Commit synthesis.
- Prompt requires final commit message to center dominant change intent, not a
  vague activity or touched-file list.
- Prompt discourages file-by-file final changelogs while allowing useful body
  context for behavior, motivation, validation, migration impact, or breaking
  changes.
- Staged diff context and selected skill context remain separate bounded context
  blocks.
- Existing defaults and failure boundaries remain unchanged: default
  `conventional-commits`, skill override, staged-changes failure before skill
  loading/model invocation.
- Focused application tests pass:
  `uv run pytest tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`.
- Full quality gate passes before handoff: `uv run ruff format .`,
  `uv run ruff check .`, `uv run ty check src tests`, and `uv run pytest`.
- Optional manual smoke verification is documented and, when appropriate, run
  after deterministic checks for prompt-quality confidence.

## Constraints

- Do not add CLI flags, JSON output, interactive review, automatic commits,
  commit-message file writing, model-callable git tools, large-diff chunking, or
  multiple model calls.
- Do not expose raw staged diffs in diagnostics.
- Do not mutate repository state or fall back to unstaged changes.
- Preserve hexagonal boundaries: application use case owns prompt construction;
  git subprocess access remains in outbound adapter; CLI remains a driving
  adapter.
- Keep default terminal output copy-oriented and concise; intermediate evidence
  should be model-facing by default for v1.

## Architecture Decisions

- **Prompt-only v1:** Implement the evidence-first workflow by strengthening
  `COMMIT_MESSAGE_PROMPT`, not by adding orchestration state or multiple model
  calls. This matches the spec's assumption and keeps the change low-risk.
- **Preserve output labels:** Keep terminal-friendly labels `Summary:`,
  `Rationale:`, and `Commit message:` to avoid CLI/output test churn and
  preserve the current copy-oriented UX.
- **Model-facing evidence:** Instruct the model to perform concise evidence
  analysis internally and use it in `Summary`/`Rationale`, but do not require a
  verbose per-file evidence report in the default output.
- **Selected skill remains authoritative:** The prompt should tell the model to
  apply the selected Agent Skill after identifying dominant intent, preserving
  `conventional-commits` as the default formatting/rules context.

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

### Phase 1: Prompt Contract Foundation

#### Task 1: Strengthen the commit-message prompt for evidence-first analysis

**Description:** Update `COMMIT_MESSAGE_PROMPT` in
`prepare_commit_message_run.py` so the model is instructed to inspect staged
files, group intent, then synthesize a Conventional Commit using the selected
skill. Preserve the existing output labels and no-mutation instructions.

**Acceptance criteria:**

- [x] Prompt instructs a file-level evidence pass over each staged file.
- [x] Prompt instructs classification of changes such as behavior, tests, docs,
      configuration, architecture, refactor, or maintenance.
- [x] Prompt instructs intent grouping and dominant intent selection.
- [x] Prompt instructs Conventional Commit synthesis using the selected skill
      after intent is clear.
- [x] Prompt tells the model not to make the final message a file-by-file
      changelog.
- [x] Prompt tells the model to use intermediate evidence to inform `Summary:`
      and `Rationale:` while keeping final output concise and not requiring a
      full per-file evidence report.
- [x] Prompt preserves `Summary:`, `Rationale:`, and `Commit message:` labels.
- [x] Prompt preserves no git commands, no file writes, no commits, and no
      unstaged-change assumptions.

**Verification:**

- [x] Focused prompt tests pass:
      `uv run pytest tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`.

**Dependencies:** None.

**Files likely touched:**

- `src/fabrica/features/developer_workflow/application/use_cases/prepare_commit_message_run.py`

**Estimated scope:** XS: 1 file.

#### Task 2: Update prompt-focused application tests

**Description:** Update `test_prepare_commit_message_run.py` to assert the new
prompt contract. Keep tests focused on observable use-case behavior rather than
checking the whole prompt string.

**Acceptance criteria:**

- [x] Tests assert the prompt includes file-level evidence analysis language.
- [x] Tests assert the prompt includes intent grouping / dominant intent
      language.
- [x] Tests assert the prompt includes Conventional Commit synthesis via selected
      Agent Skill.
- [x] Tests assert the prompt discourages vague summaries and file-by-file final
      changelogs.
- [x] Existing assertions for distinct staged diff and selected skill context
      remain.
- [x] Existing assertions for default skill, skill override, and pre-skill
      staged-change failure remain.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`

**Dependencies:** Task 1.

**Files likely touched:**

- `tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`

**Estimated scope:** S: 1 test file.

### Checkpoint: Prompt-level workflow

- [x] Focused application tests pass.
- [x] No CLI/parser/output tests require changes because user-visible labels
      remain stable.
- [x] Review prompt wording against
      `docs/specs/evidence-first-commit-message-generation-spec.md` boundaries.

### Phase 2: Integration and Documentation Review

#### Task 3: Confirm CLI and composition boundaries remain unchanged

**Description:** Inspect whether any CLI or composition changes are needed after
the prompt update. The expected outcome is no code changes outside the
application prompt/tests because the spec is prompt-level v1.

**Acceptance criteria:**

- [x] `CliCommitMessageCommand` behavior remains unchanged.
- [x] `CommitMessageWorkflow` still fails before runtime invocation for
      staged-git or skill-context load errors.
- [x] `create_codex_commit_message_workflow` defaults remain unchanged.
- [x] CLI output remains pass-through and copy-oriented.
- [x] Any decision not to change CLI/output docs is recorded in the plan or
      handoff notes.

**Verification:**

- [x] `uv run pytest tests/unit/features/agent_runtime/adapters/inbound/cli/test_commit_message_command.py tests/unit/features/agent_runtime/adapters/inbound/cli/test_parser.py`
- [x] `uv run pytest tests/integration/features/developer_workflow/test_commit_message_composition.py`

**Dependencies:** Tasks 1-2.

**Files likely touched:**

- Usually none; inspect only.
- Potentially `README.md` only if wording needs to document evidence-first
  behavior.

**Estimated scope:** XS/S depending on whether docs need updates.

#### Task 4: Update README with a brief behavior note

**Description:** Update the README's commit-message workflow section with a
concise note that `commit-message` analyzes staged changes and the selected skill
to recommend a Conventional Commit centered on dominant intent. Avoid duplicating
the full spec or promising verbose evidence output.

**Acceptance criteria:**

- [x] README describes evidence-first, dominant-intent recommendation behavior in
      one concise note.
- [x] README keeps usage examples concise and does not promise verbose evidence
      output.
- [x] README continues to document staged-only, read-only git behavior.

**Verification:**

- [x] Run formatting/lint/type/test gate as normal; no special doc build
      identified.

**Dependencies:** Task 3.

**Files likely touched:**

- `README.md`

**Estimated scope:** XS.

### Checkpoint: Boundary and docs review

- [x] CLI/parser/output tests pass if run.
- [x] Documentation decision recorded.
- [x] No out-of-scope behavior introduced.

### Phase 3: Quality Gate and Handoff

#### Task 5: Run local quality gate

**Description:** Run focused validation first, then the full project quality gate
before handoff. After deterministic checks, optionally run a manual smoke check
against real staged changes for prompt-quality confidence.

**Acceptance criteria:**

- [x] Focused application test passes.
- [x] Formatting applied with `uv run ruff format .`.
- [x] Lint passes with `uv run ruff check .`.
- [x] Type check passes with `uv run ty check src tests`.
- [x] Full tests pass with `uv run pytest`.
- [x] Optional manual smoke verification is either run or explicitly skipped with
      a reason. Run for the final documentation slice with representative staged
      README and plan updates via `make commit-message`.
- [x] Any unrun or failing checks are documented with reason and next action.
      Full quality gate passed after fixing prompt line wrapping, and Phase 2
      CLI/composition plus README verification tasks are complete.

**Verification:**

- [x] `uv run pytest tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`
- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run ty check src tests`
- [x] `uv run pytest`
- [x] Optional/manual: stage representative files, then run
      `uv run fabrica commit-message`. Run via `make commit-message` for
      staged README and plan documentation updates.

**Dependencies:** Tasks 1-4.

**Files likely touched:**

- None unless formatting changes files.

**Estimated scope:** XS operational task.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Prompt becomes too verbose and causes noisy output | Medium | Keep output labels unchanged and instruct concise evidence use rather than full evidence report. |
| Tests overfit exact prompt wording | Medium | Assert key phrases/concepts, not full prompt equality. |
| Model still emits vague messages despite prompt | Medium | Make dominant intent, anti-vagueness, and anti-file-changelog requirements explicit. Manual verification can assess quality after implementation. |
| Accidental scope expansion into CLI flags or orchestration | Medium | Keep implementation limited to prompt/tests unless README is clearly stale. |
| Documentation promises evidence output not shown by default | Low | If README changes, describe improved recommendation behavior, not a verbose evidence report. |
| Manual smoke verification depends on live credentials and staged state | Low | Keep it optional and document whether it was run or skipped; deterministic tests remain the required gate. |

## Open Questions

- Should the final output remain exactly `Summary:`, `Rationale:`, and
  `Commit message:`? Recommendation: yes, preserve labels for v1.

## Parallelization Opportunities

- Tasks 1 and 2 are best done sequentially because tests should reflect the final
  prompt.
- Task 4 documentation review can happen after Task 1, but should wait until the
  prompt's final behavior is known.
- Quality gate must be sequential after implementation.

## Implementation Readiness Checklist

- [x] Spec and related idea reviewed.
- [x] Current use case and tests inspected.
- [x] CLI/output/composition boundaries inspected.
- [x] Plan keeps work prompt-level and within v1 boundaries.
- [x] Tasks include acceptance criteria and verification steps.
- [x] No task is larger than Medium.
- [x] Checkpoints are included.
- [x] Open questions and assumptions are captured.
- [x] Plan review resolved README and optional manual smoke verification
      decisions.
