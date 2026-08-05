# Spec: Evidence-First Commit Message Generation

## Objective

Improve `fabrica commit-message` so generated commit messages are specific,
evidence-backed, and centered on the dominant intent of the currently staged git
changes.

The primary user is a developer working in a local git repository who wants the
currently staged changes translated into a specific, copyable Conventional
Commit recommendation without automatically committing, writing a commit-message
file, or mutating repository state.

The target workflow is a multi-call evidence-first architecture: inspect each
staged file independently, collect structured evidence from those per-file
analyses, then run one final synthesis call that applies the selected
commit-message Agent Skill to produce the final recommendation.

## Current context

- The source idea is documented in
  `docs/ideas/evidence-first-commit-message-generation.md`.
- The first selected-skill commit-message workflow is specified in
  `docs/specs/selected-skill-commit-message-spec.md`.
- The completed prompt-level implementation plan is documented in
  `docs/plans/evidence-first-commit-message-generation-plan.md` and is now
  superseded for future evidence-first architecture work.
- The current implemented commit-message preparation use case is
  `src/fabrica/features/developer_workflow/application/use_cases/prepare_commit_message_run.py`.
- The current use case reads full staged git diff context through an
  application-owned `GitStagedChangesLoader`, builds one `LocalAgentRunCommand`,
  and augments it with the selected commit-message Agent Skill. This one-shot
  shape is no longer the target evidence-first architecture.
- The existing staged-git application port already exposes the primitives needed
  for the desired flow:
  - `list_files()` to enumerate staged files;
  - `load_file_diff(path)` to load one file's staged diff;
  - `load_diff()` for full staged diff loading, which should no longer be the
    default evidence-first path.
- The current built-in prompt asks the model to return terminal-friendly sections
  labeled `Summary:`, `Rationale:`, and `Commit message:`.
- The current command boundary remains intentionally read-only: it reads staged
  changes only, does not run `git commit`, does not write commit-message files,
  and does not mutate repository state.
- Oversized staged diff context and missing staged changes are already intended
  to fail before model invocation.

## Assumptions

- Per-file evidence analysis should use one model session/call per staged file in
  the first multi-call implementation.
- Per-file analysis should run sequentially by default. Parallel analysis may be
  added later after the sequential behavior is correct and observable.
- Final synthesis should receive compact structured evidence summaries, not all
  raw per-file diffs again by default.
- If any per-file analysis fails, the first implementation should fail the
  workflow rather than synthesize from partial evidence.
- The existing selected skill, defaulting to `conventional-commits`, remains the
  source of Conventional Commits rules and final message formatting guidance.
- Intermediate evidence should guide synthesis, but the final commit message body
  should not normally become a file-by-file changelog.
- The near-term goal is better specificity in the final recommendation, not a
  new interactive review workflow.
- Large-diff and large-file-count chunking remain future concerns; the first
  multi-call implementation should keep explicit bounds and fail clearly when the
  staged input exceeds them.

## Desired behavior

`uv run fabrica commit-message` should execute an evidence-first workflow with
three architectural phases before recommending a commit message:

1. **Staged file discovery**
   - List currently staged files through the developer-workflow staged-git port.
   - Fail before model invocation when there are no staged files.
   - Preserve staged file path and status metadata needed for evidence analysis.
   - Avoid reading unstaged changes or mutating repository state.

2. **Per-file evidence analysis**
   - Load only one file's staged diff through `load_file_diff(path)`.
   - Run one per-file evidence analysis model call/session for each staged file.
   - Summarize the relevant change in that file briefly and factually.
   - Classify the change using categories such as behavior, tests, docs,
     configuration, architecture, refactor, or maintenance.
   - Note public contract impact, migration concerns, validation relevance, and
     possible breaking changes when the staged evidence supports them.
   - Return structured evidence for final synthesis.
   - Do not ask per-file analysis calls to produce the final commit message.

3. **Final synthesis pass**
   - Receive the complete ordered evidence bundle plus selected commit-message
     Agent Skill context.
   - Combine per-file evidence into higher-level themes.
   - Identify the dominant intent of the staged change set.
   - Separate primary behavior or contract changes from supporting tests, docs,
     wiring, or maintenance edits.
   - Avoid treating the final commit as a list of touched files.
   - Use the selected commit-message skill after the dominant intent is clear.
   - Choose the Conventional Commits type that best fits the dominant intent,
     such as `feat`, `fix`, `docs`, `test`, `refactor`, or `chore`.
   - Choose an optional scope based on the affected capability or module when a
     scope improves specificity.
   - Write a concise subject that names the concrete change intent.
   - Add a body only when it explains behavior, motivation, validation, migration
     impact, or breaking-change context that is useful to a future reader.
   - Add a `BREAKING CHANGE:` footer when the staged evidence requires it.

Per-file evidence should be represented in compact application DTOs before final
synthesis. A candidate evidence bundle shape is:

```text
Per-file evidence:
- path/to/file.py
  - Status: modified
  - Summary: ...
  - Change category: behavior | tests | docs | configuration | architecture | refactor | maintenance
  - Public contract impact: yes/no
  - Validation relevance: yes/no
  - Migration concern: yes/no
  - Breaking risk: yes/no

Final synthesis requirements:
- Group evidence into dominant and supporting themes
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
  `uv run pytest tests/unit/features/developer_workflow/application/`

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
- Implementation plan:
  `docs/plans/multi-call-evidence-first-commit-message-generation-plan.md`.
- Source idea: `docs/ideas/evidence-first-commit-message-generation.md`.
- Existing one-shot use case, likely to be replaced:
  `src/fabrica/features/developer_workflow/application/use_cases/prepare_commit_message_run.py`.
- New developer-workflow DTOs, likely:
  `src/fabrica/features/developer_workflow/application/dtos/commit_message.py`.
- New developer-workflow ports, likely:
  `src/fabrica/features/developer_workflow/application/ports/commit_message.py`.
- New developer-workflow use cases, likely:
  - `src/fabrica/features/developer_workflow/application/use_cases/analyze_staged_file_for_commit_message.py`;
  - `src/fabrica/features/developer_workflow/application/use_cases/synthesize_commit_message.py`;
  - `src/fabrica/features/developer_workflow/application/use_cases/generate_commit_message.py`.
- Agent-runtime-backed adapters, if needed:
  `src/fabrica/features/developer_workflow/adapters/outbound/`.
- Composition wiring: `src/fabrica/bootstrap/local_agent_runtime.py`.
- Unit tests:
  `tests/unit/features/developer_workflow/application/`.
- Integration tests:
  `tests/integration/features/developer_workflow/`.
- README usage documentation, if command behavior visible to users changes:
  `README.md`.

## Conventions

- Preserve hexagonal boundaries: developer-workflow application use cases own the
  commit-message workflow language, DTOs, ports, and orchestration.
- Keep agent-runtime specifics behind developer-workflow-owned ports or adapters
  where practical; the multi-call workflow should not be expressed merely as one
  prepared `LocalAgentRunCommand`.
- Keep git subprocess execution in the staged-git outbound adapter.
- Keep git access read-only and staged-diff-only.
- Keep raw staged diffs scoped to per-file analysis calls; final synthesis should
  use structured evidence rather than full raw diffs by default.
- Use explicit, terminal-friendly labels in model output.
- Do not log, print, or expose raw staged diffs in diagnostics on failure.
- Do not require a file-by-file changelog in the final commit message.
- Follow Conventional Commits v1.0.0 through the selected commit-message skill.

## Testing strategy

- Unit-test staged file discovery and orchestration:
  - staged files are listed before per-file diffs are loaded;
  - one per-file analysis is requested for each staged file;
  - per-file diffs are loaded by validated staged path;
  - final synthesis is invoked only after all per-file evidence succeeds.
- Unit-test failure behavior:
  - no staged files fails before model invocation;
  - per-file diff load failure stops the workflow;
  - per-file evidence analysis failure stops the workflow;
  - final synthesis failure is normalized into the existing result/error pattern.
- Unit-test evidence and result DTO validation.
- Unit-test that final synthesis receives structured evidence, not raw full staged
  diff context, in the default path.
- Preserve existing tests for:
  - default `conventional-commits` skill selection;
  - skill override behavior;
  - staged changes failure before model invocation;
  - CLI parsing and read-only command boundaries.
- Add integration tests with fakes for per-file analyzer and synthesizer ports.

## Boundaries

- Always use staged git diff context only.
- Always analyze staged files independently before final synthesis.
- Always synthesize the final commit message from collected evidence summaries.
- Always fail before final synthesis if required per-file evidence cannot be
  collected in the first implementation.
- Always keep the final recommendation centered on the dominant change intent.
- Always use evidence to improve specificity before applying Conventional Commits
  formatting.
- Ask before adding new CLI flags such as concise/explanatory modes,
  machine-readable JSON output, interactive evidence review, automatic commit
  creation, or commit-message file writing.
- Ask before adding parallel per-file analysis, partial-evidence synthesis,
  chunked large-diff orchestration, or model-callable git tools.
- Never mutate repository state in this workflow.
- Never silently fall back to unstaged changes.
- Never require the final commit body to list every changed file by default.

## Success criteria

- The evidence-first workflow is specified as multi-call orchestration, not only a
  stronger single prompt.
- Staged file discovery uses `list_files()` as the workflow entry point.
- Per-file analysis uses `load_file_diff(path)` and produces structured evidence
  for each staged file.
- Final synthesis receives the complete evidence bundle and selected
  commit-message skill context.
- The final recommended commit message is required to describe the dominant
  change intent rather than a vague activity or touched-file list.
- The workflow remains read-only, staged-only, bounded, deterministic under tests,
  and explicit about failure before final synthesis when evidence collection
  fails.
- Implementation validation commands and likely test locations are documented.

## Open questions

- Should per-file analysis output be strict structured JSON from the model, or can
  the first implementation normalize text into application DTOs through an
  adapter-owned parser?
- Should final synthesis output remain the current `Summary:`, `Rationale:`, and
  `Commit message:` labels?
- Should a later version permit partial-evidence synthesis when one low-risk file
  analysis fails?
- What maximum staged file count should be allowed before requiring an explicit
  future chunking or batching strategy?

## Superseded decisions

The earlier prompt-level v1 decision to avoid multiple model calls is superseded
for future evidence-first work. The prompt-level implementation may remain useful
as a temporary fallback or historical spike, but it is no longer the target
architecture for the commit-message workflow.
