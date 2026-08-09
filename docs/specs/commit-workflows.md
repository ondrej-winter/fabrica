# Spec: Commit Workflows

This spec is the canonical source of truth for Fabrica's developer-facing commit
workflows. It defines the read-only `fabrica commit-message` preview workflow and
the explicitly confirmed mutating `fabrica commit` workflow.

`docs/specs/git-workflow-tools.md` owns git subprocess and registered-tool
adapter contracts, including approved commit creation and explicitly composed
pre-commit execution. This spec owns the user workflows, safety boundaries,
interaction model, and application orchestration expectations for commit-message
generation and confirmed commit creation.

## Purpose

Fabrica commit workflows help a developer turn currently staged git changes into
a specific, evidence-backed Conventional Commit message.

The workflows serve two related but distinct use cases:

- `fabrica commit-message` recommends a copyable commit message without mutating
  repository state.
- `fabrica commit` runs a conservative quality-and-confirmation flow and creates a
  git commit only after explicit approval.

Both workflows use staged changes only. Neither workflow stages files, inspects
unstaged content as commit evidence, rewrites the index, pushes, pulls, amends,
or lets model output choose git commands or flags.

## Workflow summary

### `fabrica commit-message`

`uv run fabrica commit-message` is a read-only staged-change preview command.

It:

1. discovers staged files;
2. analyzes staged diffs file by file;
3. synthesizes the collected evidence into one Conventional Commit
   recommendation;
4. prints terminal-friendly output that is easy to inspect and copy.

It never runs `git commit`, writes a commit-message file, runs pre-commit hooks,
stages files, edits files, or mutates repository state.

### `fabrica commit`

`uv run fabrica commit` is an explicitly confirmed mutating workflow.

It:

1. runs the configured pre-commit quality check before message generation;
2. stops before model invocation when pre-commit fails, times out, cannot run, or
   modifies files;
3. generates the same staged-only evidence-first commit-message recommendation as
   `fabrica commit-message`;
4. displays the generated recommendation once;
5. asks for explicit approval;
6. creates a git commit only when the user answers explicit yes.

Running pre-commit before message generation keeps the recommendation aligned
with the staged state that is ready to commit. When hooks modify files, the user
must review and stage the resulting changes before rerunning `fabrica commit`.

## Shared commit-message generation model

Commit-message generation is evidence-first and staged-only.

The generation flow has three phases:

1. **Staged file discovery**
   - List currently staged files through the developer-workflow staged-git port.
   - Fail before model invocation when there are no staged files.
   - Preserve staged file path and status metadata needed for evidence analysis.
   - Do not read unstaged changes or mutate repository state.

2. **Per-file evidence analysis**
   - Load only one staged file diff at a time through `load_file_diff(path)`.
   - Run one evidence analysis model call or session for each staged file.
   - Summarize each file's relevant staged change briefly and factually.
   - Classify each change using categories such as behavior, tests, docs,
     configuration, architecture, refactor, or maintenance.
   - Record public contract impact, migration concerns, validation relevance, and
     possible breaking changes when staged evidence supports them.
   - Return compact structured evidence for final synthesis.
   - Do not ask per-file analysis calls to produce the final commit message.

3. **Final synthesis**
   - Receive the complete ordered evidence bundle plus selected commit-message
     Agent Skill context.
   - Combine per-file evidence into higher-level themes.
   - Identify the dominant intent of the staged change set.
   - Separate primary behavior or contract changes from supporting tests, docs,
     wiring, or maintenance edits.
   - Apply Conventional Commits v1.0.0 through the selected commit-message skill.
   - Choose the Conventional Commits type that best fits the dominant intent, such
     as `feat`, `fix`, `docs`, `test`, `refactor`, or `chore`.
   - Choose an optional scope based on the affected capability or module when a
     scope improves specificity.
   - Write a concise subject that names the concrete change intent.
   - Add a body only when it explains behavior, motivation, validation, migration
     impact, or breaking-change context useful to a future reader.
   - Add a `BREAKING CHANGE:` footer when staged evidence requires it.

Final synthesis uses structured evidence by default, not the full raw staged diff.
The final message must describe the dominant change intent rather than a vague
activity, file list, or implementation changelog.

## Evidence shape

Per-file evidence is represented in compact application DTOs before final
synthesis. The canonical evidence bundle includes the following concepts:

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

Intermediate evidence may be shown only when it is concise and clearly separated
from the final recommendation. The user-facing output should make the final
recommended message easy to copy.

## `fabrica commit-message` behavior

`fabrica commit-message` is safe to run as a preview command in a repository with
staged changes.

The command:

- reads only staged git state;
- uses the evidence-first generation model described in this spec;
- defaults to the `conventional-commits` Agent Skill unless the user selects a
  different commit-message skill;
- returns terminal-friendly sections labeled `Summary:`, `Rationale:`, and
  `Commit message:`;
- fails before model invocation when no staged files are present;
- fails clearly when staged diff context exceeds configured bounds;
- does not run pre-commit hooks;
- does not run `git commit`;
- does not write commit-message files;
- does not stage, unstage, edit, or inspect unstaged files.

Manual verification:

```bash
git add <files>
uv run fabrica commit-message
```

## `fabrica commit` behavior

`fabrica commit` is a conservative interactive workflow for creating a commit
from a generated recommendation.

### Quality check before message generation

Before generating a commit-message recommendation, `fabrica commit` runs the
configured pre-commit quality check through the explicitly composed pre-commit
adapter described in `docs/specs/git-workflow-tools.md`.

The workflow stops before model invocation and does not prompt or commit when
pre-commit:

- fails;
- times out;
- cannot start;
- reports invalid configuration;
- modifies tracked files;
- produces an application-safe failure result.

When pre-commit modifies files, the command reports that the commit was not
created and the user must review and stage the changed files before retrying.

`fabrica commit-message` does not run this pre-commit step because it is a
read-only preview command.

### Recommendation generation and display

After pre-commit passes without modifying files, `fabrica commit` reuses the
shared evidence-first staged-only recommendation flow. It must not duplicate the
prompt/model orchestration independently.

The command prints the generated `Summary:`, `Rationale:`, and `Commit message:`
block before any git mutation. It shows the full generated recommendation block
once, then prompts. It does not repeat a second final-message-only block
immediately before the question.

`CommitMessageRecommendation.commit_message` is the application boundary value
passed exactly to git commit execution after approval, including subject, body,
and any valid Conventional Commits footer.

### Confirmation prompt

The confirmation prompt is CLI adapter behavior because it is interactive I/O.
The prompt uses a conservative default:

```text
Commit with this message? [y/N]
```

Only case-insensitive `y` or `yes` after trimming whitespace approves commit
creation.

The workflow treats `n`, `no`, empty input, EOF, interrupted input, and every
other answer as rejection. Explicit no, empty input, EOF, and default rejection
are successful no-ops and exit `0`. Interrupted input exits non-zero because the
command did not complete normally.

On rejection, the command prints a concise no-op message, creates no commit, and
leaves staged files untouched.

### Commit creation

Git commit execution lives behind a developer-workflow-owned outbound port and
subprocess adapter. The adapter contract is owned by
`docs/specs/git-workflow-tools.md`.

After explicit approval, the workflow:

- passes the generated commit message exactly to the approved commit creation
  port;
- creates a commit from the already-staged changes;
- preserves subject, body, and Conventional Commits footers;
- uses the composition-owned repository working directory;
- surfaces git commit failures as safe user-facing CLI failures;
- prints a concise success line with the new commit hash when available, such as
  `Committed as <short-sha>.`.

Manual verification should use a temporary or disposable git repository:

```bash
git add <files>
uv run fabrica commit
git log --oneline -n 1
```

Manual rejection verification should confirm that staged changes remain staged and
no commit is created after answering anything other than explicit yes.

## Safety boundaries

- Always keep `fabrica commit-message` read-only.
- Always keep both workflows staged-only for commit-message evidence.
- Always analyze staged files independently before final synthesis.
- Always synthesize the final commit message from collected evidence summaries.
- Always fail before final synthesis if required per-file evidence cannot be
  collected.
- Always keep the final recommendation centered on the dominant change intent.
- Always run the configured pre-commit quality check before message generation in
  the mutating `fabrica commit` workflow.
- Always stop `fabrica commit` before model invocation when pre-commit fails,
  times out, cannot run, or modifies files.
- Always require explicit interactive approval before running `git commit`.
- Always treat default, ambiguous, interrupted, or missing input as rejection.
- Always return exit code `0` for explicit no/default no-op rejection and non-zero
  for interrupted input.
- Always leave staged files untouched on rejection.
- Always reuse the existing evidence-first recommendation flow for
  `fabrica commit`.
- Always keep git commit execution in a developer-workflow outbound adapter.
- Always document mutating behavior in CLI help and README usage docs.
- Ask before changing the command name away from `fabrica commit`.
- Ask before adding edit, regenerate, JSON output, auto-staging, hook bypassing,
  auto-push, or non-interactive approval behavior.
- Ask before adding parallel per-file analysis, partial-evidence synthesis,
  chunked large-diff orchestration, or model-callable git tools to commit-message
  generation.
- Never mutate repository state in `fabrica commit-message`.
- Never silently fall back to unstaged changes.
- Never require the final commit body to list every changed file by default.
- Never add a `--yes` or equivalent non-interactive approval flag without a new
  explicit spec that revisits the human-confirmation safety boundary.
- Never let model output choose arbitrary git flags, pathspecs, repository paths,
  or shell commands.
- Never commit on EOF, Ctrl-C, empty input, or any answer other than explicit yes.

## Architecture and ownership

Implementation preserves hexagonal boundaries in the `developer_workflow` feature
slice.

- Spec: `docs/specs/commit-workflows.md`.
- Related git subprocess/tool adapter spec: `docs/specs/git-workflow-tools.md`.
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
- Agent-runtime-backed commit-message adapters:
  `src/fabrica/features/developer_workflow/adapters/outbound/commit_message_agent_runtime/`.
- Git and pre-commit subprocess adapters:
  `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/`.
- Composition wiring: `src/fabrica/bootstrap/composition.py`.
- Unit tests:
  `tests/unit/adapters/inbound/cli/` and
  `tests/unit/features/developer_workflow/`.
- Integration tests:
  `tests/integration/features/developer_workflow/` and, when CLI entrypoint
  behavior changes, `tests/integration/features/agent_runtime/`.
- README usage documentation: `README.md`.

Developer-workflow application code owns commit workflow orchestration, DTOs, and
ports. Subprocess git execution and pre-commit execution live in outbound
adapters. Terminal prompts live in inbound CLI adapters. Adapter code validates
and translates external I/O before calling application ports.

## Non-goals

- Do not change `fabrica commit-message` into a mutating command.
- Do not run pre-commit hooks from `fabrica commit-message`.
- Do not auto-stage unstaged files or otherwise modify the index before commit.
- Do not inspect unstaged changes as commit-message evidence.
- Do not auto-push after creating the commit.
- Do not bypass or customize git hooks.
- Do not open an editor or add edit-before-commit behavior.
- Do not regenerate a new recommendation after rejection.
- Do not add JSON output, scripting flags, or non-interactive approval flags.
- Do not plan a `--yes` or equivalent non-interactive approval flag as a near-term
  direction; automation should use `fabrica commit-message` plus explicit git
  commands under its own control.
- Do not expose arbitrary git command execution.

## Testing strategy

Automated tests must remain deterministic and offline. They must not call live
Codex backends, read real user skill directories, or depend on a developer's
ambient staged git state.

### Commit-message generation tests

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
- Preserve tests for default `conventional-commits` skill selection, skill override
  behavior, staged changes failure before model invocation, CLI parsing, and
  read-only command boundaries.

### Confirmed commit tests

- Unit-test CLI parser behavior:
  - `commit` is a distinct subcommand from `commit-message`;
  - relevant `commit-message` options are accepted by `commit` where intended;
  - help text clearly distinguishes read-only preview from mutating commit.
- Unit-test mutating workflow ordering:
  - pre-commit runs before recommendation generation;
  - pre-commit failure skips model invocation, prompting, and commit execution;
  - pre-commit timeout or startup failure skips model invocation, prompting, and
    commit execution;
  - pre-commit-modified files stop the workflow before model invocation and report
    that the user must review and stage changes before retrying.
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
  runner according to `docs/specs/git-workflow-tools.md`.
- Integration-test temporary git repositories:
  - approval creates exactly one commit with the generated message;
  - rejection creates no commit and preserves staged changes;
  - pre-commit failure or modification creates no commit;
  - no staged changes creates no commit and reports the staged-git failure;
  - git commit failure creates no successful commit and returns a non-zero CLI
    result.

## Validation

Documentation-only changes should be reviewed for clarity and consistency.
Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`
- Focused application tests during iteration:
  `uv run pytest tests/unit/features/developer_workflow/application/`
- Focused CLI tests during iteration:
  `uv run pytest tests/unit/adapters/inbound/cli/`
- Focused integration tests during iteration:
  `uv run pytest tests/integration/features/developer_workflow/`

## Success criteria

- The spec reads as the canonical source of truth, not as a proposal, diff,
  migration note, or implementation diary.
- `fabrica commit-message` is specified as read-only, staged-only, bounded, and
  deterministic under tests.
- `fabrica commit-message` does not run pre-commit hooks or mutate repository
  state.
- The evidence-first workflow is specified as multi-call orchestration, not only a
  stronger single prompt.
- Per-file analysis uses staged file diffs and produces structured evidence for
  final synthesis.
- Final synthesis receives the complete evidence bundle and selected
  commit-message skill context.
- The final recommended commit message describes the dominant change intent.
- `fabrica commit` is specified as a separate explicit mutating workflow while
  preserving `fabrica commit-message` as the read-only preview workflow.
- `fabrica commit` runs pre-commit before message generation and stops before
  model invocation when pre-commit fails or modifies files.
- The approval behavior is conservative: only explicit `y` or `yes` creates a
  commit.
- Rejection and cancellation paths leave repository state untouched.
- No-op rejection exits `0`; interrupted input exits non-zero.
- The generated `CommitMessageRecommendation.commit_message` is the exact message
  source for git commit execution.
- Interactive prompt handling belongs to the CLI adapter and git commit execution
  belongs to a developer-workflow outbound adapter behind an application port.
- Successful output includes a concise confirmation with the new commit hash when
  available.
- Non-goals, safety boundaries, project structure, validation commands, testing
  strategy, and related documentation ownership are explicit.
