# Spec: Selected Skill Commit Message Workflow

## Objective

Productize the first selected-skill agent workflow by adding a specialized CLI
command that reads staged git changes, loads a commit-message Agent Skill, and
asks the existing local agent runtime to propose a structured commit message.

The primary user is a developer working in a local git repository who wants
Fabrica to turn the currently staged changes into a useful commit-message
recommendation without automatically committing anything.

## Current context

- The existing local CLI entrypoint is implemented in
  `src/fabrica/features/agent_runtime/adapters/inbound/cli/`.
- The existing `run` command already supports explicit selected Agent Skills via
  `--skill`, selected resources via `--resource`, and skill root overrides via
  `--skill-root`.
- Selected skill loading is already implemented as bounded `SKILL.md` context
  through the `agent_runtime` application layer and filesystem-backed outbound
  adapters.
- `LocalAgentRunCommand` supports bounded context blocks, with each
  `LocalAgentContextBlock` limited by `MAX_CONTEXT_TEXT_CHARS`.
- The project already contains a tool-loop foundation, but this workflow is not
  intended to expose git as a model-callable tool in the MVP.
- The project is in an initial raw development stage, so code clarity is preferred
  over compatibility shims.

## Assumptions

- `staged changes` means the patch produced by `git diff --staged` in the
  current working directory.
- The command is run from inside the repository whose staged changes should be
  summarized.
- The selected commit-message skill exists under the configured skill root. The
  default skill ID is `conventional-commits`.
- The existing Codex-backed runtime remains the first model execution path for
  the CLI command.
- The model can be instructed through a fixed prompt to produce markdown sections
  named `Summary`, `Rationale`, and `Commit Message`.
- Future automation may create commits, write commit-message files, accept extra
  user instructions, or expose git context in the generic `run` command, but those
  behaviors are intentionally outside this MVP.

## Desired behavior

Add a specialized command:

```bash
uv run fabrica commit-message
```

By default, the command should load the `conventional-commits` skill. Callers may
override the selected skill:

```bash
uv run fabrica commit-message --skill <skill_id>
```

The command should also support the existing selected-skill root and diagnostics
patterns where relevant, plus Codex model and reasoning effort overrides:

```bash
uv run fabrica commit-message \
  --skill conventional-commits \
  --model gpt-5.3-codex-spark \
  --reasoning-effort low \
  --skill-root .agents/skills \
  --verbose-diagnostics
```

The command must:

- read staged git changes only;
- load the selected commit-message skill as bounded context;
- add the staged diff as a separate bounded runtime context block;
- call the existing runtime with a fixed built-in prompt;
- default the Codex-backed workflow to `gpt-5.3-codex-spark` with `low`
  reasoning effort while allowing command-level overrides;
- ask the model to return markdown with these sections:

```markdown
## Summary
...

## Rationale
...

## Commit Message
...
```

The command must not:

- run `git commit`;
- write a commit-message file;
- modify staged or unstaged repository state;
- fall back to unstaged changes;
- ask the model for a commit message when there are no staged changes;
- ask the model for a commit message when staged diff context is too large.

## Failure behavior

The command should fail before calling the model when:

- `git` is unavailable;
- the command is not run inside a git repository;
- there are no staged changes;
- the staged diff exceeds the configured context limit;
- git execution times out or fails unexpectedly;
- selected skill loading fails.

Failures should be normalized into existing CLI/application result patterns where
practical and should produce clear user-facing messages. Diagnostics must avoid
printing private absolute paths unless verbose diagnostics are explicitly enabled.

## Commands and validation

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`
- Focused tests during iteration: `uv run pytest tests/unit/features/agent_runtime`

Manual verification after implementation:

```bash
git add <files>
uv run fabrica commit-message
```

Default automated tests must remain deterministic and offline. They must not read
real user skill directories, call live Codex backends, or depend on a developer's
ambient git repository state.

## Project structure

- Spec: `docs/specs/selected-skill-commit-message-spec.md`.
- CLI parser/runner changes:
  `src/fabrica/features/agent_runtime/adapters/inbound/cli/`.
- Application DTOs:
  `src/fabrica/features/agent_runtime/application/dtos/`.
- Application ports:
  `src/fabrica/features/agent_runtime/application/ports/`.
- Application use cases:
  `src/fabrica/features/agent_runtime/application/use_cases/`.
- Git subprocess adapter:
  `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/`.
- Composition wiring: `src/fabrica/bootstrap/local_agent_runtime.py`.
- Tests: mirrored under `tests/unit/features/agent_runtime/` and, if useful,
  focused integration tests under `tests/integration/features/agent_runtime/`.
- Documentation updates: `README.md`.

## Conventions

- Preserve hexagonal boundaries: application code owns DTOs, ports, and use-case
  orchestration; subprocess execution belongs in an outbound adapter.
- Use explicit, typed application DTOs and port protocols for the staged git
  context boundary.
- Execute git with explicit argument lists and `shell=False`.
- Use non-interactive git commands and disable paging with `--no-pager`.
- Keep git access read-only.
- Do not log or expose raw full diffs as diagnostics on failures. The diff may be
  passed to the model as selected runtime context only after validation succeeds.
- Keep default tests offline and deterministic by injecting fakes for git command
  execution and model/runtime dependencies.

## Testing strategy

- Unit-test staged git DTO validation for non-empty and oversized diff behavior.
- Unit-test the application use case for:
  - successful command construction;
  - no staged changes;
  - oversized staged diff;
  - git unavailable/not-repository/failure mapping;
  - selected skill configuration handoff.
- Unit-test the git subprocess adapter with an injectable command runner or fake
  process result rather than invoking ambient git.
- Unit-test CLI parsing for defaults and overrides:
  - `commit-message` defaults to `conventional-commits`;
  - `commit-message --skill <skill_id>` overrides the default;
  - `--skill-root` and `--verbose-diagnostics` are accepted.
- Unit-test CLI runner behavior to prove invalid staged state fails before the
  runtime/model is called.
- Add a narrow integration test with a temporary git repository only if it can be
  deterministic, local, and fast.

## Boundaries

- Always read staged changes only.
- Always fail before model invocation when there are no staged changes.
- Always fail before model invocation when staged diff text exceeds the configured
  context bound.
- Always default to the `conventional-commits` selected skill and allow `--skill`
  override.
- Always default the Codex-backed workflow to `gpt-5.3-codex-spark` with `low`
  reasoning effort and allow `--model`/`--reasoning-effort` overrides.
- Always produce a markdown-oriented model prompt requesting `Summary`,
  `Rationale`, and `Commit Message` sections.
- Ask before adding automatic `git commit`, commit-message file writing, JSON
  output, generic `run --include-staged-diff`, model-callable git tools, or extra
  user instruction flags.
- Never modify repository state in the MVP.
- Never silently fall back to unstaged changes.

## Success criteria

- `uv run fabrica commit-message` is documented as the first productized
  selected-skill workflow.
- The command defaults to the `conventional-commits` skill and supports `--skill`
  override.
- The Codex-backed command defaults to `gpt-5.3-codex-spark` with `low` reasoning
  effort and supports command-level model/effort overrides.
- Staged git diff is loaded through an application-owned port and outbound
  subprocess adapter.
- The model receives selected skill context and staged diff context as separate
  bounded context blocks.
- No staged changes and oversized staged diff both fail before model invocation
  with clear user-facing messages.
- The MVP never commits, writes commit-message files, or mutates git state.
- Unit tests cover command parsing, use-case behavior, adapter normalization, and
  no-model-call failure paths.
- README usage documentation is updated.
- The project quality gate passes or any unrun checks are explicitly documented.

## Open questions

- Should a later version support `--instruction` for additional tone or scope
  guidance?
- Should a later version add `--json` for machine-readable structured output?
- Should a later version write the proposed commit message to a temporary file or
  directly run `git commit -F <file>` behind explicit approval?
- Should the generic `run` command later gain an explicit `--include-staged-diff`
  option for non-commit selected-skill workflows?
