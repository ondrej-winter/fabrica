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
- This spec is the canonical home for model-callable read-only git context tools,
  including the staged tools originally described in
  `docs/specs/model-callable-staged-git-tools-spec.md`.

## Relationship to other git workflow specs

- `docs/specs/model-callable-staged-git-tools-spec.md` is superseded by this
  spec for canonical read-only staged tool contracts. It remains useful as
  historical context for why staged model-callable tools were introduced.
- `docs/specs/evidence-first-commit-message-generation-spec.md` continues to own
  the deterministic `fabrica commit-message` workflow. That workflow may use
  staged git primitives internally, but it must not silently expose broader
  read-only worktree, unstaged, commit, or ref/range tools to the model.
- `docs/specs/interactive-confirmed-commit-flow-spec.md` remains separate because
  it describes the explicitly mutating, human-confirmed `fabrica commit` workflow.
  Mutating commit creation is not part of this read-only tool set.

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

Add read-only git context capabilities in five groups.

### Status context

Status tools inspect current local state without changing the index or working
tree and without returning raw diffs.

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

### Staged context

Staged context tools inspect currently staged changes without changing the index
or working tree. These are the canonical model-callable staged git tools and must
remain separate from deterministic `fabrica commit-message` evidence loading.

#### `git_staged_files`

List staged file paths and staged change statuses.

- Returns a bounded textual or structured-text representation of staged files.
- Uses a read-only command equivalent to `git diff --staged --name-status`.
- Fails clearly when:
  - `git` is unavailable;
  - the working directory is not inside a git repository;
  - there are no staged files;
  - git execution times out or fails;
  - output cannot be decoded safely.
- Does not include unstaged-only changes.
- Does not include raw diffs.

Initial argument schema should be empty.

#### `git_staged_diff`

Return the full staged diff as bounded tool output.

- Reuses existing staged diff loading capability where practical.
- Uses a read-only command equivalent to `git diff --staged`.
- Applies existing or equivalent `GitStagedDiffBounds` before returning output.
- Also remains subject to `ToolLoopLimits.max_tool_result_chars` when returned
  through the tool loop.
- Fails before returning raw output when there are no staged changes or the staged
  diff exceeds configured bounds.

Initial argument schema should be empty.

#### `git_staged_file_diff`

Return the staged diff for one staged file path.

- Accepts a single `path` argument.
- Validates that `path` is a safe relative path and refers to a file that is
  currently staged.
- Rejects absolute paths, parent-directory traversal, empty paths, and paths not
  present in the staged file list.
- Uses a read-only command equivalent to `git diff --staged -- <path>` after
  validation.
- Applies staged diff and tool output bounds.
- Fails clearly when the requested path is not staged or the output is empty.

Initial argument schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Relative path of a staged file to inspect. Must be listed by git_staged_files."
    }
  },
  "required": ["path"],
  "additionalProperties": false
}
```

Do not split staged tools further by status category, such as `added`,
`modified`, or `deleted`, unless a future workflow proves the need.
`git_staged_files` can return status metadata.

### Unstaged context

Unstaged context tools inspect current tracked worktree changes that are not
staged, without changing the index or working tree.

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

Initial argument schema:

```json
{
  "type": "object",
  "properties": {
    "commit": {
      "type": "string",
      "description": "Commit-ish to inspect as a commit object."
    }
  },
  "required": ["commit"],
  "additionalProperties": false
}
```

#### `git_commit_changed_files`

List changed paths and statuses for one commit.

- Accepts a single `commit` argument.
- Validates the commit-ish as a commit object before inspection.
- Uses a read-only command equivalent to `git diff-tree --name-status` or
  `git show --name-status --format=...` with fixed arguments.
- Does not include raw diff output.

Initial argument schema should match `git_commit_details`.

#### `git_commit_diff`

Return the bounded full diff for one commit.

- Accepts a single `commit` argument.
- Validates the commit-ish as a commit object before inspection.
- Applies git diff bounds and tool-loop result bounds.
- Fails clearly when the commit diff exceeds configured bounds and suggests using
  `git_commit_changed_files` followed by `git_commit_file_diff`.

Initial argument schema should match `git_commit_details`.

#### `git_commit_file_diff`

Return the bounded diff for one file in one commit.

- Accepts `commit` and `path` arguments.
- Validates the commit-ish as a commit object.
- Validates that `path` is a safe relative path and is changed by the commit.
- Uses a read-only command equivalent to `git show <commit> -- <path>` after
  validation.

Initial argument schema:

```json
{
  "type": "object",
  "properties": {
    "commit": {
      "type": "string",
      "description": "Commit-ish to inspect as a commit object."
    },
    "path": {
      "type": "string",
      "description": "Relative path changed by the commit. Must be listed by git_commit_changed_files."
    }
  },
  "required": ["commit", "path"],
  "additionalProperties": false
}
```

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

Initial argument schema:

```json
{
  "type": "object",
  "properties": {
    "base_ref": {"type": "string", "description": "Base git ref for the comparison."},
    "head_ref": {"type": "string", "description": "Head git ref for the comparison."}
  },
  "required": ["base_ref", "head_ref"],
  "additionalProperties": false
}
```

#### `git_ref_diff`

Return the bounded full diff between two refs.

- Accepts `base_ref` and `head_ref` arguments.
- Validates both refs before inspection.
- Applies git diff bounds and tool-loop result bounds.
- Fails clearly when the diff exceeds configured bounds and suggests using
  `git_ref_changed_files` followed by `git_ref_file_diff`.

Initial argument schema should match `git_ref_changed_files`.

#### `git_ref_file_diff`

Return the bounded diff for one file between two refs.

- Accepts `base_ref`, `head_ref`, and `path` arguments.
- Validates both refs before inspection.
- Validates that `path` is safe and appears in `git_ref_changed_files` for the
  same ref pair.

Initial argument schema:

```json
{
  "type": "object",
  "properties": {
    "base_ref": {"type": "string", "description": "Base git ref for the comparison."},
    "head_ref": {"type": "string", "description": "Head git ref for the comparison."},
    "path": {
      "type": "string",
      "description": "Relative path changed between refs. Must be listed by git_ref_changed_files."
    }
  },
  "required": ["base_ref", "head_ref", "path"],
  "additionalProperties": false
}
```

#### `git_branch_ahead_behind`

Return current branch ahead/behind counts against an upstream or explicit base.

- Accepts an optional `base_ref` argument.
- Defaults to upstream when one exists.
- Returns current branch, base ref, ahead count, and behind count.
- Does not fetch from remotes.

Initial argument schema:

```json
{
  "type": "object",
  "properties": {
    "base_ref": {
      "type": "string",
      "description": "Optional base ref. Defaults to the current branch upstream when omitted."
    }
  },
  "additionalProperties": false
}
```

#### `git_merge_base`

Return the merge base for two refs.

- Accepts `base_ref` and `head_ref` arguments.
- Validates both refs.
- Returns the merge-base hash and short hash.
- Does not mutate refs or contact remotes.

Initial argument schema should match `git_ref_changed_files`.

## Implemented v1 decisions

- Ref/range comparisons use three-dot semantics by default for PR-like review
  workflows.
- `git_commit_log` lists recent commits from `HEAD` only in v1.
- `git_status_summary` may include bounded untracked path names as well as the
  untracked count.
- Registered-tool outputs use deterministic tab-separated structured text rather
  than strict JSON strings.
- Default implementation bounds are 500,000 diff characters, 20 default recent
  commits, and 50 maximum recent commits.
- Renamed and copied files are represented by destination/new `path` plus
  `old_path` metadata. File-diff tools accept the destination/new path in v1.
- Broader read-only git context tools may be composed into explicitly configured
  generic tool-loop runtimes. They are not ambient global powers.
- V1 composition uses a helper named
  `create_read_only_git_context_registered_tools(...)` in
  `fabrica.bootstrap.composition`; the broader helper is intentionally not part
  of the curated `fabrica.bootstrap` package API unless a future API decision
  promotes it.

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
  - Add read-only git context DTOs for status summaries, staged and unstaged
    changed files, commit metadata, ref comparisons, and bounded diffs.
  - Add staged file/status DTOs if needed, such as `GitStagedFile`,
    `GitStagedFileList`, or `GitStagedFileStatus`.
- Application ports:
  - `src/fabrica/features/developer_workflow/application/ports/`
  - Prefer focused protocols such as `GitWorktreeContextLoader`,
    `GitStagedContextLoader`, `GitCommitContextLoader`, and
    `GitRefContextLoader` over a broad catch-all git service.
  - The staged application boundary may generalize the existing staged changes
    port or keep smaller focused ports for staged file listing, full staged diff,
    and per-file staged diff loading.
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

## Desired API shape

Prefer small, focused application-facing abstractions that avoid a vague catch-all
git service. A coherent staged boundary may look like:

```python
class GitStagedChanges(Protocol):
    def list_files(self) -> GitStagedFileList: ...
    def load_diff(self) -> GitStagedDiff: ...
    def load_file_diff(self, path: str) -> GitStagedDiff: ...
```

Alternatively, keep smaller protocols such as `GitStagedFilesLister`,
`GitStagedDiffLoader`, and `GitStagedFileDiffLoader` if that better matches the
implementation. Commit, ref/range, and unstaged/worktree capabilities should use
similarly narrow protocols by stable intent and output shape.

## Safety boundaries

- Always keep these tools read-only.
- Always use explicit git argument lists with `shell=False`.
- Always disable git paging with `--no-pager`.
- Always keep the working directory controlled by composition/options, not model
  arguments.
- Always bound diff output and tool result output.
- Always expose staged git tools only by explicit composition.
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
  - staged file/status DTO validation, including non-empty relative paths and
    bounded list/context output.
- Unit-test subprocess command builders:
  - fixed argv only;
  - `--no-pager` where applicable;
  - path arguments placed only after `--`;
  - no model-supplied flags.
- Unit-test subprocess adapters with injectable runners:
  - success for each tool group;
  - staged file listing success;
  - full staged diff success;
  - per-file staged diff success;
  - git unavailable;
  - not a repository;
  - invalid commit/ref;
  - no matching changes;
  - timeout;
  - non-zero git failure;
  - decode failure;
  - oversized output.
- Unit-test path validation for file-diff tools:
  - rejects absolute paths;
  - rejects `..` traversal;
  - rejects unknown, non-staged, non-unstaged, or non-changed paths for the
    relevant tool group;
  - accepts known changed paths with normal relative components.
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

## Remaining cleanup backlog

1. Keep commit-ish and ref argument validation explicit before git argv
   construction so option-like or whitespace/control-character values cannot be
   interpreted as model-supplied flags or malformed revision tokens.
2. Keep staged and read-only context file-diff command builders validating safe
   relative paths before appending them after `--`.
3. Consider splitting the concrete read-only context subprocess adapter into
   smaller worktree, commit, and ref modules if future changes make the current
   shared adapter difficult to review.
4. Update README usage documentation and docs index if registered-tool exposure
   changes user-facing or developer-facing documentation.

## Success criteria

- The spec defines read-only git context capabilities for status, staged,
  unstaged, commit, and ref/range workflows.
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
