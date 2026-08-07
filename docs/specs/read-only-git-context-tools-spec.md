# Spec: Read-Only Git Context Tools

## Objective

Add explicit read-only git context capabilities so developers and model-driven
agent workflows can inspect worktree state, commit history, and ref/range changes
without exposing arbitrary git command execution or mutating repository state.

The primary users are:

- an agent runtime using opt-in model-callable tools for self-context during
  coding;
- review and debugging workflows that need commit archaeology or PR-like branch
  comparison context.

The target design is a small set of atomic adapters and model-callable tools
grouped by stable intent, not a generic git wrapper.

## Current context

- The `developer_workflow` feature already owns git-oriented workflow behavior.
- Existing staged-git ports and DTOs live under
  `src/fabrica/features/developer_workflow/application/`.
- Existing git subprocess execution is isolated under
  `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/`.
- Existing staged tools cover:
  - `git_staged_files`;
  - `git_staged_diff`;
  - `git_staged_file_diff`.
- Existing staged-git subprocess behavior uses explicit argument lists, disables
  paging, controls the working directory through composition, applies output
  bounds, and normalizes safe application errors.
- The `commit-message` workflow must remain staged-only and read-only. Adding
  broader read-only git context must not silently change that command's safety
  contract.

## Assumptions

- Read-only git context should be exposed through explicit composition, not as
  ambient global model powers.
- Changed-file/status tools should exist before full-diff tools because they are
  cheaper, safer, and help the model decide whether a narrower diff is needed.
- Full-diff tools should be deliberately requested and bounded.
- Ref/range tools are required early because PR/review summarization often asks
  what changed between the current branch and a base ref.
- Unstaged worktree tools are useful, but they must remain separate from staged
  commit-message evidence.

## Desired behavior

Add read-only git context capabilities in three groups.

### Worktree context

Worktree tools inspect current local state without changing the index or working
tree.

#### `git_status_summary`

Return a bounded summary of the repository's current local state.

- Includes current branch or detached HEAD state when available.
- Includes HEAD short hash when available.
- Includes upstream branch when available.
- Includes counts and optionally paths for staged, unstaged, and untracked files.
- Does not include raw diffs.
- Uses read-only commands equivalent to `git status --short --branch` and related
  metadata lookups.

Initial argument schema should be empty.

#### `git_unstaged_files`

List unstaged tracked file paths and statuses.

- Does not include staged-only changes.
- Does not include untracked file contents.
- Uses a read-only command equivalent to `git diff --name-status`.
- Fails clearly when no unstaged tracked changes exist.

Initial argument schema should be empty.

#### `git_unstaged_diff`

Return the bounded full unstaged diff for tracked files.

- Uses a read-only command equivalent to `git diff`.
- Applies git diff bounds and tool-loop result bounds.
- Fails clearly when there are no unstaged tracked changes or output exceeds
  configured bounds.

Initial argument schema should be empty.

#### `git_unstaged_file_diff`

Return the bounded unstaged diff for one tracked file.

- Accepts a single `path` argument.
- Validates that `path` is a safe relative path and currently has unstaged tracked
  changes.
- Rejects absolute paths, parent-directory traversal, empty paths, and paths not
  present in the unstaged file list.
- Uses a read-only command equivalent to `git diff -- <path>` after validation.

Initial argument schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Relative path of an unstaged tracked file to inspect. Must be listed by git_unstaged_files."
    }
  },
  "required": ["path"],
  "additionalProperties": false
}
```

### Commit context

Commit context tools inspect committed history without changing refs or local
state.

#### `git_commit_log`

List recent commits with bounded metadata.

- Accepts an optional bounded `count` argument.
- May accept an optional `ref` argument after ref validation is implemented.
- Returns hash, short hash, subject, author date, and ref decorations when
  available.
- Does not include full commit messages or diffs.
- Uses a read-only command equivalent to `git log` with a fixed format and
  bounded count.

Initial argument schema:

```json
{
  "type": "object",
  "properties": {
    "count": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50,
      "description": "Maximum number of recent commits to return. Defaults to a small configured count."
    }
  },
  "additionalProperties": false
}
```

#### `git_commit_details`

Return metadata and the full message for one commit.

- Accepts a single `commit` argument.
- Validates the commit-ish as a commit object before inspection.
- Returns hash, short hash, parents, author, author date, committer date, subject,
  body, and refs when available.
- Does not include raw diff output.

#### `git_commit_changed_files`

List changed paths and statuses for one commit.

- Accepts a single `commit` argument.
- Validates the commit-ish as a commit object before inspection.
- Uses a read-only command equivalent to `git diff-tree --name-status` or
  `git show --name-status --format=...` with fixed arguments.
- Does not include raw diff output.

#### `git_commit_diff`

Return the bounded full diff for one commit.

- Accepts a single `commit` argument.
- Validates the commit-ish as a commit object before inspection.
- Applies git diff bounds and tool-loop result bounds.
- Fails clearly when the commit diff exceeds configured bounds and suggests using
  `git_commit_changed_files` followed by `git_commit_file_diff`.

#### `git_commit_file_diff`

Return the bounded diff for one file in one commit.

- Accepts `commit` and `path` arguments.
- Validates the commit-ish as a commit object.
- Validates that `path` is a safe relative path and is changed by the commit.
- Uses a read-only command equivalent to `git show <commit> -- <path>` after
  validation.

### Ref/range context

Ref/range context tools inspect differences between validated refs, such as a
feature branch and `main`, without changing refs or local state.

#### `git_ref_changed_files`

List changed paths and statuses between two refs.

- Accepts `base_ref` and `head_ref` arguments.
- Validates both refs before inspection.
- Uses a read-only command equivalent to `git diff --name-status <base_ref>...<head_ref>`
  or another explicitly chosen comparison form.
- Does not include raw diff output.

#### `git_ref_diff`

Return the bounded full diff between two refs.

- Accepts `base_ref` and `head_ref` arguments.
- Validates both refs before inspection.
- Applies git diff bounds and tool-loop result bounds.
- Fails clearly when the diff exceeds configured bounds and suggests using
  `git_ref_changed_files` followed by `git_ref_file_diff`.

#### `git_ref_file_diff`

Return the bounded diff for one file between two refs.

- Accepts `base_ref`, `head_ref`, and `path` arguments.
- Validates both refs before inspection.
- Validates that `path` is safe and appears in `git_ref_changed_files` for the
  same ref pair.

#### `git_branch_ahead_behind`

Return current branch ahead/behind counts against an upstream or explicit base.

- Accepts an optional `base_ref` argument.
- Defaults to upstream when one exists.
- Returns current branch, base ref, ahead count, and behind count.
- Does not fetch from remotes.

#### `git_merge_base`

Return the merge base for two refs.

- Accepts `base_ref` and `head_ref` arguments.
- Validates both refs.
- Returns the merge-base hash and short hash.
- Does not mutate refs or contact remotes.

## Tool atomicity rule

Use one tool per stable intent and output shape. Each tool must have:

- one clear risk profile;
- one predictable output shape;
- a narrow argument schema;
- bounded deterministic behavior;
- no hidden mutation.

Do not add a generic `git`, `git_context`, or `git_readonly` tool that multiplexes
subcommands through model-provided arguments.

## Architecture and project structure

Implementation should preserve hexagonal boundaries:

- Application DTOs:
  - `src/fabrica/features/developer_workflow/application/dtos/`
  - Add read-only git context DTOs for status summaries, changed files, commit
    metadata, ref comparisons, and bounded diffs.
- Application ports:
  - `src/fabrica/features/developer_workflow/application/ports/`
  - Prefer focused protocols such as `GitWorktreeContextLoader`,
    `GitCommitContextLoader`, and `GitRefContextLoader` over a broad catch-all
    git service.
- Outbound subprocess adapters:
  - `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/`
  - Keep all git subprocess execution here or in consistently named subpackages.
- Registered-tool adapters:
  - Add developer-workflow-owned adapters that convert read-only git context ports
    into `RegisteredTool` instances.
  - These adapters may import agent-runtime tool DTOs because they bridge
    developer-workflow capabilities into the agent-runtime tool system.
- Composition root:
  - Add explicit helpers that register read-only git context tools only when a
    composed runtime requests them.

## Safety boundaries

- Always keep these tools read-only.
- Always use explicit git argument lists with `shell=False`.
- Always disable git paging with `--no-pager`.
- Always keep the working directory controlled by composition/options, not model
  arguments.
- Always bound diff output and tool result output.
- Always validate commit-ish and ref arguments before running diff/detail commands.
- Always validate file paths as safe relative paths before passing them after
  `--` to git.
- Always separate staged, unstaged, commit, and ref/range tools by name.
- Never expose arbitrary git command execution.
- Never run `git add`, `git reset`, `git checkout`, `git switch`, `git stash`,
  `git commit`, `git push`, `git pull`, `git fetch`, merge, rebase, tag creation,
  or any other mutating or network operation in this capability.
- Never let the model supply arbitrary git flags, pathspecs, working directories,
  or command names.
- Never change the staged-only behavior of `fabrica commit-message`.
- Never silently inspect unstaged changes inside staged commit-message workflows.

## Non-goals

- Do not implement arbitrary read-only shell or git command execution.
- Do not add mutating git workflows in this spec.
- Do not add remote/network-backed operations such as fetch, pull, or querying a
  hosting provider API.
- Do not add blame/provenance tools in the MVP.
- Do not add tag/release/changelog tools in the MVP.
- Do not replace existing staged-git tools with broader overloaded tools.
- Do not expose raw private diagnostics, full command stderr, secrets, or raw file
  contents in error messages.

## Testing strategy

- Unit-test DTO validation:
  - bounded counts;
  - safe relative paths;
  - commit/ref identifier validation shape;
  - changed-file status parsing;
  - diff bounds.
- Unit-test subprocess command builders:
  - fixed argv only;
  - `--no-pager` where applicable;
  - path arguments placed only after `--`;
  - no model-supplied flags.
- Unit-test subprocess adapters with injectable runners:
  - success for each tool group;
  - git unavailable;
  - not a repository;
  - invalid commit/ref;
  - no matching changes;
  - timeout;
  - non-zero git failure;
  - decode failure;
  - oversized output.
- Unit-test registered-tool wrappers:
  - expected tool names, descriptions, and argument schemas;
  - successful output mapping;
  - invalid arguments map to safe failures;
  - adapter failures map to safe tool failures;
  - output remains bounded by tool-loop limits.
- Preserve existing staged git and commit-message tests to prove staged-only
  workflows remain unchanged.

Default automated tests must remain deterministic and offline. They must not
depend on the developer's ambient repository state.

## Commands and validation

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`
- Focused tests during iteration:
  - `uv run pytest tests/unit/features/developer_workflow`

Manual verification after implementation may use a temporary local git
repository with staged changes, unstaged changes, branches, and sample commits.

## Open questions

1. Should ref comparisons use two-dot or three-dot diff semantics by default for
   PR-like review workflows?
2. Should `git_commit_log` accept a validated `ref` argument in v1, or only list
   recent commits from `HEAD`?
3. Should untracked file names appear in `git_status_summary`, or only counts to
   avoid exposing unexpected local paths to the model?
4. Should tool outputs be plain text, JSON-ish structured text, or strict JSON
   strings for easier parsing by agents?
5. What default diff and log bounds should apply before asking the user to narrow
   by file or count?

## Proposed implementation slices

1. Add this spec and keep existing behavior unchanged.
2. Add read-only git context DTOs and focused application ports.
3. Implement commit context adapter behavior and tests.
4. Implement ref/range context adapter behavior and tests.
5. Implement unstaged/worktree context adapter behavior and tests.
6. Add registered-tool factories for explicit model-callable exposure.
7. Update README usage documentation and docs index if registered-tool exposure
   changes user-facing or developer-facing documentation.

## Success criteria

- The spec defines read-only git context capabilities for worktree, commit, and
  ref/range workflows.
- The proposed tool set covers agent self-context, PR/review summarization, and
  commit archaeology/debugging.
- The spec keeps staged, unstaged, commit, and ref/range concerns explicit and
  separately named.
- The spec forbids arbitrary git command execution and all mutating/network git
  operations.
- The spec requires explicit composition for model-callable tools.
- The spec defines architecture boundaries, testing strategy, validation commands,
  non-goals, and open questions.
- Existing staged-only `commit-message` behavior remains unchanged.
