# Spec: Evidence-First Commit Message Generation

## Objective

Improve `fabrica commit-message` so generated commit messages are less vague
and generic by requiring an evidence-first analysis workflow before final
Conventional Commit synthesis.

The primary user is a developer working in a local git repository who wants the
currently staged changes translated into a specific, copyable commit message that
captures the dominant intent of the change instead of a broad summary or a
file-by-file changelog.

## Current context

- The source idea is documented in
  `docs/ideas/evidence-first-commit-message-generation.md`.
- The first selected-skill commit-message workflow is specified in
  `docs/specs/selected-skill-commit-message-spec.md`.
- The implemented commit-message preparation use case is
  `src/fabrica/features/developer_workflow/application/use_cases/prepare_commit_message_run.py`.
- The current use case reads staged git diff context through an
  application-owned `GitStagedChangesLoader`, builds a `LocalAgentRunCommand`,
  and augments it with the selected commit-message Agent Skill.
- The current built-in prompt asks the model to return terminal-friendly sections
  labeled `Summary:`, `Rationale:`, and `Commit message:`.
- The current command boundary remains intentionally read-only: it reads staged
  changes only, does not run `git commit`, does not write commit-message files,
  and does not mutate repository state.
- Oversized staged diff context and missing staged changes are already intended
  to fail before model invocation.

## Assumptions

- The first implementation can improve commit-message quality through a stronger
  built-in prompt and output contract rather than introducing multiple model
  calls or a new orchestration engine.
- The existing selected skill, defaulting to `conventional-commits`, remains the
  source of Conventional Commits rules and final message formatting guidance.
- Intermediate evidence should guide synthesis, but the final commit message body
  should not normally become a file-by-file changelog.
- The near-term goal is better specificity in the final recommendation, not a
  new interactive review workflow.
- Large-diff chunking remains outside the first implementation because the
  current command rejects staged diff context that exceeds the configured bound.

## Desired behavior

`uv run fabrica commit-message` should analyze staged changes in three
conceptual passes before recommending a commit message:

1. **File-level evidence pass**
   - Inspect each staged file independently from the staged diff context.
   - Summarize the relevant change in that file briefly and factually.
   - Classify the change using categories such as behavior, tests, docs,
     configuration, architecture, refactor, or maintenance.
   - Note public contract impact, migration concerns, validation relevance, and
     possible breaking changes when the staged evidence supports them.

2. **Intent grouping pass**
   - Combine file-level observations into higher-level themes.
   - Identify the dominant intent of the staged change set.
   - Separate primary behavior or contract changes from supporting tests, docs,
     wiring, or maintenance edits.
   - Avoid treating the final commit as a list of touched files.

3. **Conventional Commit synthesis pass**
   - Use the selected commit-message skill after the dominant intent is clear.
   - Choose the Conventional Commits type that best fits the dominant intent,
     such as `feat`, `fix`, `docs`, `test`, `refactor`, or `chore`.
   - Choose an optional scope based on the affected capability or module when a
     scope improves specificity.
   - Write a concise subject that names the concrete change intent.
   - Add a body only when it explains behavior, motivation, validation, migration
     impact, or breaking-change context that is useful to a future reader.
   - Add a `BREAKING CHANGE:` footer when the staged evidence requires it.

The model-facing context should make the evidence workflow explicit. A candidate
analysis shape is:

```text
Staged change overview:
- Files changed: N
- Dominant change type: feature | fix | docs | refactor | test | chore
- Candidate scope: <scope>

Per-file observations:
- path/to/file.py
  - Summary: ...
  - Change category: application behavior
  - Public contract impact: yes/no
  - Breaking risk: yes/no

Grouped intent:
- Main intent: ...
- Supporting changes: ...
- Validation changes: ...

Commit message requirements:
- Follow Conventional Commits v1.0.0
- Prefer one dominant type and optional scope
- Include body only if it adds useful context
- Include breaking-change footer when required
```

The user-facing output should remain easy to read in terminal output and should
make the final recommended message easy to copy. If intermediate evidence is
shown, it should be concise and clearly separated from the final recommendation.

## Commands and validation

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`
- Focused application tests during iteration:
  `uv run pytest tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`

Manual verification after implementation:

```bash
git add <files>
uv run fabrica commit-message
```

Default automated tests must remain deterministic and offline. They must not
call live Codex backends, read real user skill directories, or depend on a
developer's ambient staged git state.

## Project structure

- Spec: `docs/specs/evidence-first-commit-message-generation-spec.md`.
- Source idea: `docs/ideas/evidence-first-commit-message-generation.md`.
- Prompt/use-case behavior:
  `src/fabrica/features/developer_workflow/application/use_cases/prepare_commit_message_run.py`.
- Unit tests:
  `tests/unit/features/developer_workflow/application/test_prepare_commit_message_run.py`.
- CLI/output tests, if the visible output contract changes:
  `tests/unit/features/agent_runtime/adapters/inbound/cli/`.
- README usage documentation, if command behavior visible to users changes:
  `README.md`.

## Conventions

- Preserve hexagonal boundaries: application use cases own prompt construction
  and orchestration; git subprocess execution remains in the outbound adapter.
- Keep git access read-only and staged-diff-only.
- Keep the selected Agent Skill as bounded context separate from staged diff
  context.
- Use explicit, terminal-friendly labels in model output.
- Do not log, print, or expose raw staged diffs in diagnostics on failure.
- Do not require a file-by-file changelog in the final commit message.
- Follow Conventional Commits v1.0.0 through the selected commit-message skill.

## Testing strategy

- Unit-test the commit-message preparation prompt to prove it instructs the model
  to perform:
  - file-level evidence analysis;
  - intent grouping;
  - Conventional Commit synthesis.
- Unit-test that the prompt discourages vague summaries and file-by-file final
  changelogs.
- Unit-test that staged diff context and selected skill context remain distinct
  bounded context blocks.
- Preserve existing tests for:
  - default `conventional-commits` skill selection;
  - skill override behavior;
  - staged changes failure before skill loading/model invocation;
  - CLI parsing and read-only command boundaries.
- Add or update CLI/output tests only if the user-visible output labels or shape
  change.

## Boundaries

- Always use staged git diff context only.
- Always fail before model invocation when there are no staged changes or the
  staged diff exceeds the configured context limit.
- Always keep the final recommendation centered on the dominant change intent.
- Always use evidence to improve specificity before applying Conventional
  Commits formatting.
- Ask before adding new CLI flags such as concise/explanatory modes,
  machine-readable JSON output, interactive evidence review, automatic commit
  creation, or commit-message file writing.
- Ask before replacing the prompt-level workflow with multiple model calls,
  chunked large-diff orchestration, or model-callable git tools.
- Never mutate repository state in this workflow.
- Never silently fall back to unstaged changes.
- Never require the final commit body to list every changed file by default.

## Success criteria

- The commit-message workflow has a documented evidence-first specification based
  on `docs/ideas/evidence-first-commit-message-generation.md`.
- The desired model workflow explicitly includes file-level evidence, intent
  grouping, and Conventional Commit synthesis.
- The final recommended commit message is required to describe the dominant
  change intent rather than a vague activity or touched-file list.
- The spec preserves existing selected-skill commit-message command boundaries:
  staged changes only, read-only git access, bounded context, no automatic
  commits, and pre-model failures for invalid staged state.
- Open design questions from the idea are recorded without blocking a prompt-level
  first implementation.
- Implementation validation commands and likely test locations are documented.

## Resolved v1 decisions and future directions

### V1 decisions

- Keep intermediate per-file evidence model-facing by default. Preserve the
  concise, copy-oriented terminal output shape rather than exposing a full
  evidence report in the first implementation.
- Ask the model for concise per-file evidence, using details such as change
  category, public contract impact, breaking risk, migration concerns, and
  validation relevance only when the staged evidence makes them useful.
- Do not require a fixed observation block for every changed file when fields are
  irrelevant or would add noise.
- Include validation notes in the final commit message body only when validation
  evidence materially improves the explanation of behavior, motivation, risk, or
  confidence. Routine test or documentation updates should inform synthesis
  without becoming boilerplate in the commit body.

### Deferred future directions

- A future explanatory output mode may expose concise intermediate evidence for
  users who want to audit why a commit message was recommended.
- A future concise/explanatory mode split should be introduced through an
  explicit CLI/output design rather than by making the default output verbose.
- Future large-diff chunking should preserve cross-file intent grouping and the
  dominant change intent instead of summarizing chunks independently.
- Interactive evidence review, machine-readable output, automatic commit
  creation, commit-message file writing, multiple model calls, chunked
  orchestration, and model-callable git tools remain outside the prompt-level v1
  implementation.
