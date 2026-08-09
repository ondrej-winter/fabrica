# Spec: Commit Workflows

This spec owns the developer-facing commit workflow surface. It separates the
read-only `fabrica commit-message` preview workflow from the explicitly confirmed
mutating `fabrica commit` workflow while preserving their shared staged-change
and Conventional Commits concerns.

## Read-only commit-message preview

### Objective

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

### Current context

- Earlier source ideas, prompt-level plans, and the one-shot full-diff MVP spec
  were temporary working artifacts and have been removed after promotion into this
  evidence-first spec and implementation.
- The current implementation lives in
  `src/fabrica/features/developer_workflow/application/use_cases/generate_commit_message.py`.
- The staged-git application port exposes the primitives needed
  for the desired flow:
  - `list_files()` to enumerate staged files;
  - `load_file_diff(path)` to load one file's staged diff;
  - `load_diff()` for full staged diff loading outside the default evidence-first
    commit-message path.
- The current built-in prompt asks the model to return terminal-friendly sections
  labeled `Summary:`, `Rationale:`, and `Commit message:`.
- The current command boundary remains intentionally read-only: it reads staged
  changes only, does not run `git commit`, does not write commit-message files,
  and does not mutate repository state.
- Oversized staged diff context and missing staged changes are already intended
  to fail before model invocation.

### Assumptions

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

### Desired behavior

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

### Commands and validation

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

### Project structure

- Spec: `docs/specs/commit-workflows.md`.
- Developer-workflow DTOs:
  `src/fabrica/features/developer_workflow/application/dtos/commit_message.py`.
- Developer-workflow ports:
  `src/fabrica/features/developer_workflow/application/ports/commit_message.py`.
- Developer-workflow use case:
  `src/fabrica/features/developer_workflow/application/use_cases/generate_commit_message.py`.
- Agent-runtime-backed adapters:
  `src/fabrica/features/developer_workflow/adapters/outbound/commit_message_agent_runtime/`.
- Composition wiring: `src/fabrica/bootstrap/local_agent_runtime.py`.
- Unit tests:
  `tests/unit/features/developer_workflow/application/`.
- Integration tests:
  `tests/integration/features/developer_workflow/`.
- README usage documentation, if command behavior visible to users changes:
  `README.md`.

### Conventions

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

### Testing strategy

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

### Boundaries

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

### Success criteria

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

### Open questions

- Should per-file analysis output be strict structured JSON from the model, or can
  the first implementation normalize text into application DTOs through an
  adapter-owned parser?
- Should final synthesis output remain the current `Summary:`, `Rationale:`, and
  `Commit message:` labels?
- Should a later version permit partial-evidence synthesis when one low-risk file
  analysis fails?
- What maximum staged file count should be allowed before requiring an explicit
  future chunking or batching strategy?

### Superseded decisions

The earlier prompt-level v1 decision to avoid multiple model calls is superseded.
The evidence-first workflow is now the target architecture for the commit-message
workflow.


## Interactive confirmed commit flow

### Objective

Add an explicit interactive `fabrica commit` workflow that turns the existing
evidence-first commit-message recommendation into a real git commit only after
the developer gives explicit approval.

The primary user is a developer working in a local git repository who already
staged the intended changes and wants Fabrica to generate a Conventional Commit
message, show the recommendation, and create the commit without requiring manual
copy/paste. The workflow must make the mutating boundary obvious and preserve the
read-only safety contract of `fabrica commit-message`.

### Current context

- `fabrica commit-message` is the existing safe preview command. It generates a
  terminal-friendly recommendation from currently staged changes and does not run
  `git commit`, write commit-message files, stage files, modify the index, or
  inspect unstaged changes.
- The current evidence-first commit-message workflow is specified in this spec and
  implemented under the `developer_workflow` feature slice.
- The CLI parser and runner live in `src/fabrica/adapters/inbound/cli/`, with
  developer-workflow command models and runner contracts under
  `src/fabrica/features/developer_workflow/adapters/inbound/cli/`.
- Commit-message and confirmed-commit composition are wired in
  `src/fabrica/bootstrap/composition.py` through explicit composition helpers.
- Read-only staged git access is exposed through developer-workflow application
  ports and implemented by subprocess adapters under
  `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/`.
- The current staged git subprocess adapter already uses explicit git argument
  lists, disables paging, applies bounds, supports a composition-owned working
  directory, and maps git failures to application-safe errors.
- Existing CLI and composition tests cover `commit-message` parser behavior,
  runner delegation, evidence-first workflow composition, model evidence
  propagation, and no-staged-changes failures.

### Assumptions

- The command should be named `fabrica commit` in the MVP so the mutating behavior
  is visible at the command boundary while `fabrica commit-message` remains the
  read-only preview command.
- `CommitMessageRecommendation.commit_message` is the application boundary value
  that should be passed exactly to git commit execution after approval, including
  body text and any valid Conventional Commits footer.
- The first version does not need edit-before-commit, regenerate-on-reject,
  machine-readable output, or non-interactive automation mode.
- Cancellation, EOF, empty input, and every response other than explicit `y` or
  `yes` should be treated as rejection and must not mutate repository state.
- Explicit no, empty input, EOF, and default rejection should exit `0` as a
  successful no-op; interrupted input such as Ctrl-C should exit non-zero because
  the command did not complete normally.
- The confirmation prompt can be implemented as CLI adapter behavior because it is
  interactive I/O, while git commit execution should remain behind a
  developer-workflow-owned outbound port and adapter.
- Git hook behavior should remain git's default behavior. The MVP should not add
  hook bypassing, hook customization, or special retry behavior around hooks.

### Desired behavior

`uv run fabrica commit` should run a conservative interactive commit workflow:

1. **Generate the recommendation**
   - Reuse the existing evidence-first staged-only commit-message workflow.
   - Fail before prompting when there are no staged changes or recommendation
     generation fails.
   - Preserve the same selected skill, model, reasoning effort, skill root,
     diagnostics, usage, and pricing options that are relevant to
     `fabrica commit-message`.

2. **Display the recommendation**
   - Print the generated `Summary:`, `Rationale:`, and `Commit message:` block
     before any git mutation.
   - Make the exact final commit message visible before confirmation.
   - Show the full generated recommendation block once, then prompt; do not repeat
     a second final-message-only block immediately before the question.
   - Keep output terminal-friendly and easy to inspect.

3. **Ask for explicit confirmation**
   - Prompt with a conservative default such as:

     ```text
     Commit with this message? [y/N]
     ```

   - Treat only case-insensitive `y` or `yes` after trimming whitespace as
     approval.
   - Treat `n`, `no`, empty input, EOF, interrupted input, and any other answer as
     rejection.
   - On rejection, print a concise no-op message and exit without creating a
     commit or changing staged files.
   - Return exit code `0` for explicit no/default no-op rejection and non-zero for
     interrupted input.

4. **Commit only after approval**
   - Run `git commit` with the generated commit message only after explicit
     approval.
   - Pass the generated commit message exactly, preserving subject, body, and
     footers.
   - Write the generated commit message to a temporary commit-message file and run
     `git commit --file <tempfile>` through a safe non-shell subprocess argument
     list for both single-line and multiline messages.
   - Use the same composition-owned repository working directory model as staged
     git inspection.
   - Surface git commit failures as safe user-facing CLI failures without hiding
     that the mutation was attempted.
   - After a successful commit, print a concise success line with the new commit
     hash when available, such as `Committed as <short-sha>.`.

### Non-goals

- Do not change `fabrica commit-message` into a mutating command.
- Do not auto-stage unstaged files or otherwise modify the index before commit.
- Do not inspect unstaged changes as part of this workflow.
- Do not auto-push after creating the commit.
- Do not bypass or customize git hooks.
- Do not open an editor or add edit-before-commit behavior in the MVP.
- Do not regenerate a new recommendation after rejection in the MVP.
- Do not add JSON output, scripting flags, or non-interactive approval flags in
  the MVP.
- Do not plan a `--yes` or equivalent non-interactive approval flag as a near-term
  direction; automation should keep using `fabrica commit-message` plus explicit
  git commands under its own control.
- Do not expose arbitrary git command execution.

### Commands and validation

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`
- Focused unit tests during iteration:
  - `uv run pytest tests/unit/features/agent_runtime/adapters/inbound/cli/`
  - `uv run pytest tests/unit/features/developer_workflow/`
- Focused integration tests during iteration:
  - `uv run pytest tests/integration/features/developer_workflow/`
  - `uv run pytest tests/integration/features/agent_runtime/test_cli_entrypoint.py`

Manual verification after implementation should use a temporary or disposable git
repository:

```bash
git add <files>
uv run fabrica commit
git log --oneline -n 1
```

Manual rejection verification should confirm that staged changes remain staged and
no commit is created after answering anything other than explicit yes.

Default automated tests must remain deterministic and offline. They must not call
live Codex backends, depend on real user skill directories, or depend on a
developer's ambient staged git state.

### Project structure

- Spec: `docs/specs/commit-workflows.md`.
- CLI parser and parsed command DTOs:
  `src/fabrica/adapters/inbound/cli/parser.py` and
  `src/fabrica/features/developer_workflow/adapters/inbound/cli/`.
- CLI runner, prompt handling, and terminal output:
  `src/fabrica/adapters/inbound/cli/runner.py`,
  `src/fabrica/adapters/inbound/cli/output.py`, and developer-workflow CLI
  adapter contracts.
- Developer-workflow application DTOs:
  `src/fabrica/features/developer_workflow/application/dtos/`.
- Developer-workflow application ports:
  `src/fabrica/features/developer_workflow/application/ports/`.
- Developer-workflow application use cases:
  `src/fabrica/features/developer_workflow/application/use_cases/`.
- Git commit subprocess adapter contract:
  `docs/specs/git-workflow-tools.md`.
- Composition wiring: `src/fabrica/bootstrap/composition.py`.
- Unit tests:
  `tests/unit/adapters/inbound/cli/` and
  `tests/unit/features/developer_workflow/`.
- Integration tests:
  `tests/integration/features/developer_workflow/` and, if CLI entrypoint behavior
  changes, `tests/integration/features/agent_runtime/`.
- README usage documentation: `README.md`.

### Conventions

- Preserve hexagonal boundaries: developer-workflow application code owns commit
  workflow orchestration, DTOs, and ports; subprocess git execution lives in an
  outbound adapter; terminal prompts live in the inbound CLI adapter.
- Keep mutating git execution explicit and isolated behind an application-owned
  port such as a focused `GitCommitCreator` protocol.
- Use explicit git argument lists with `shell=False` in subprocess adapters.
- Disable git paging with `--no-pager` where applicable.
- Keep the repository working directory controlled by composition/options, never
  by model output.
- Do not pass transport schemas, argparse namespaces, or framework objects into
  developer-workflow application ports.
- Do not log, print, or expose raw staged diffs or secret values in diagnostics.
- Follow Conventional Commits v1.0.0 through the selected commit-message skill.
- Update README because the new command creates git commits and changes the user
  workflow surface.

### Testing strategy

- Unit-test CLI parser behavior:
  - `commit` is a distinct subcommand from `commit-message`;
  - relevant `commit-message` options are accepted by `commit` where intended;
  - help text clearly distinguishes read-only preview from mutating commit.
- Unit-test CLI runner behavior with injected fakes:
  - recommendation output is shown before prompting;
  - the full recommendation block is shown once without duplicating a
    final-message-only block;
  - `y` and `yes` approve after trimming and case normalization;
  - `n`, `no`, empty input, EOF, interrupted input, and unrecognized answers
    reject without invoking the commit port;
  - explicit no/default no-op rejection exits `0`;
  - interrupted input exits non-zero;
  - usage and pricing evidence are still printed when requested and available;
  - recommendation-generation failures skip prompting and skip commit execution.
- Unit-test application DTOs and ports:
  - commit command/result DTOs validate required message text;
  - the commit execution port receives the exact generated commit message.
- Unit-test git commit subprocess adapter behavior with an injectable git command
  runner:
  - approved commit uses a safe non-shell `git commit --file <tempfile>` argument
    list;
  - single-line and multiline commit messages preserve subject, body, and footer
    text exactly through the temporary commit-message file;
  - successful commit output includes a concise success line with the new commit
    hash when available;
  - git unavailable, not a repository, no staged changes, hook failure, timeout,
    and non-zero git failures map to application-safe errors;
  - diagnostics do not expose secret or high-risk raw content.
- Integration-test temporary git repositories:
  - approval creates exactly one commit with the generated message;
  - rejection creates no commit and preserves staged changes;
  - no staged changes creates no commit and reports the staged-git failure;
  - git commit failure creates no successful commit and returns a non-zero CLI
    result.
- Preserve existing `commit-message` tests to prove the read-only command remains
  read-only and deterministic.

### Boundaries

- Always keep `fabrica commit-message` read-only.
- Always require explicit interactive approval before running `git commit`.
- Always treat default, ambiguous, interrupted, or missing input as rejection.
- Always return exit code `0` for explicit no/default no-op rejection and non-zero
  for interrupted input.
- Always leave staged files untouched on rejection.
- Always pass the approved generated commit message through a temporary
  commit-message file and `git commit --file <tempfile>`.
- Always reuse the existing evidence-first recommendation flow rather than
  duplicating prompt/model orchestration for `fabrica commit`.
- Always keep git commit execution in a developer-workflow outbound adapter.
- Always print a concise successful commit confirmation with the new commit hash
  when available.
- Always document the mutating behavior in CLI help and README usage docs.
- Ask before changing the command name away from `fabrica commit`.
- Ask before adding edit, regenerate, JSON output, auto-staging, hook bypassing,
  or auto-push behavior.
- Never add a `--yes` or equivalent non-interactive approval flag without a new
  explicit spec that revisits the human-confirmation safety boundary.
- Never let model output choose arbitrary git flags, pathspecs, repository paths,
  or shell commands.
- Never commit on EOF, Ctrl-C, empty input, or any answer other than explicit yes.

### Success criteria

- The spec defines `fabrica commit` as a separate explicit mutating workflow while
  preserving `fabrica commit-message` as the read-only preview workflow.
- The desired approval behavior is conservative: only explicit `y` or `yes`
  creates a commit.
- The spec requires rejection and cancellation paths to leave repository state
  untouched.
- The spec distinguishes exit codes for no-op rejection (`0`) and interrupted
  input (non-zero).
- The generated `CommitMessageRecommendation.commit_message` is identified as the
  exact message source for git commit execution.
- The spec requires `git commit --file <tempfile>` for exact commit-message
  preservation.
- The spec assigns interactive prompt handling to the CLI adapter and git commit
  execution to a developer-workflow outbound adapter behind an application port.
- The spec defines successful output as a concise confirmation with the new commit
  hash when available.
- The spec documents non-goals, boundaries, project structure, validation
  commands, testing strategy, and documentation requirements.

### Confirmed decisions

- Explicit no, empty input, EOF, and default rejection are successful no-ops and
  should exit `0`; interrupted input should exit non-zero.
- Generated commit messages should be written to a temporary commit-message file
  and passed to git with `git commit --file <tempfile>`.
- The CLI should show the full generated recommendation block once before the
  prompt and should not duplicate a final-message-only block.
- The product direction should not include a non-interactive approval flag;
  automation should use `fabrica commit-message` plus explicit git commands.
- Successful commit output should include a concise confirmation with the new
  commit hash when available, such as `Committed as <short-sha>.`.
