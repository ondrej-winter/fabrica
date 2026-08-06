# Spec: Interactive Confirmed Commit Flow

## Objective

Add an explicit interactive `fabrica commit` workflow that turns the existing
evidence-first commit-message recommendation into a real git commit only after
the developer gives explicit approval.

The primary user is a developer working in a local git repository who already
staged the intended changes and wants Fabrica to generate a Conventional Commit
message, show the recommendation, and create the commit without requiring manual
copy/paste. The workflow must make the mutating boundary obvious and preserve the
read-only safety contract of `fabrica commit-message`.

## Current context

- `fabrica commit-message` is the existing safe preview command. It generates a
  terminal-friendly recommendation from currently staged changes and does not run
  `git commit`, write commit-message files, stage files, modify the index, or
  inspect unstaged changes.
- The current evidence-first commit-message workflow is specified in
  `docs/specs/evidence-first-commit-message-generation-spec.md` and implemented
  under the `developer_workflow` feature slice.
- The CLI parser and runner live in
  `src/fabrica/features/agent_runtime/adapters/inbound/cli/parser.py` and
  `src/fabrica/features/agent_runtime/adapters/inbound/cli/runner.py`.
- The composed commit-message workflow is wired in
  `src/fabrica/bootstrap/local_agent_runtime.py` through
  `CommitMessageWorkflowOptions`, `CommitMessageWorkflow`,
  `create_commit_message_workflow()`, and
  `create_codex_commit_message_workflow()`.
- Read-only staged git access is exposed through the developer-workflow
  application port in
  `src/fabrica/features/developer_workflow/application/ports/git_staged_changes.py`
  and implemented by the subprocess adapter in
  `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/`.
- The current staged git subprocess adapter already uses explicit git argument
  lists, disables paging, applies bounds, supports a composition-owned working
  directory, and maps git failures to application-safe errors.
- Existing CLI and composition tests cover `commit-message` parser behavior,
  runner delegation, evidence-first workflow composition, model evidence
  propagation, and no-staged-changes failures.

## Assumptions

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

## Desired behavior

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

## Non-goals

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

## Commands and validation

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

## Project structure

- Spec: `docs/specs/interactive-confirmed-commit-flow-spec.md`.
- Source idea: `docs/ideas/interactive-confirmed-commit-flow.md`.
- CLI parser and parsed command DTOs:
  `src/fabrica/features/agent_runtime/adapters/inbound/cli/parser.py`.
- CLI runner, prompt handling, and terminal output:
  `src/fabrica/features/agent_runtime/adapters/inbound/cli/runner.py` and
  `src/fabrica/features/agent_runtime/adapters/inbound/cli/output.py` if output
  helpers are needed.
- Developer-workflow application DTOs:
  `src/fabrica/features/developer_workflow/application/dtos/`.
- Developer-workflow application ports:
  `src/fabrica/features/developer_workflow/application/ports/`.
- Developer-workflow application use cases:
  `src/fabrica/features/developer_workflow/application/use_cases/`.
- Git commit subprocess adapter:
  `src/fabrica/features/developer_workflow/adapters/outbound/` under a focused
  adapter package such as `git_commit_subprocess/`.
- Composition wiring: `src/fabrica/bootstrap/local_agent_runtime.py`.
- Unit tests:
  `tests/unit/features/agent_runtime/adapters/inbound/cli/` and
  `tests/unit/features/developer_workflow/`.
- Integration tests:
  `tests/integration/features/developer_workflow/` and, if CLI entrypoint behavior
  changes, `tests/integration/features/agent_runtime/`.
- README usage documentation: `README.md`.

## Conventions

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

## Testing strategy

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

## Boundaries

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

## Success criteria

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

## Confirmed decisions

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
