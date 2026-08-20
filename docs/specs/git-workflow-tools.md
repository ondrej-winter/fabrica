# Spec: Git Workflow Tools

## Objective

Define the git-related tool and adapter set for local developer and agent
workflows. These capabilities let a composed runtime inspect repository state,
staged changes, unstaged tracked changes, commit history, and ref/range changes;
create an explicitly approved git commit; and run explicitly composed developer
quality checks such as pre-commit hooks without granting arbitrary git or shell
command execution.

The tool set is intentionally small, atomic, intent-based, and separated by
safety category. Each tool or adapter exposes one stable capability with a
predictable argument schema, bounded output, explicit side-effect semantics, and
a single risk profile.

## Scope and safety categories

Git workflow tools provide local repository capabilities for:

- agent self-context during coding workflows;
- review and pull-request-like branch summarization;
- commit archaeology and debugging;
- staged-change inspection for explicitly composed model-callable tools;
- explicitly approved commit creation;
- explicitly composed pre-commit quality checks.

The tools are not ambient runtime powers. They are available only when the
composition root explicitly registers them for a runtime or workflow. Read-only
tools and mutating tools must be registered separately so a workflow can grant
inspection capabilities without also granting mutation.

`docs/specs/commit-workflows.md` owns the deterministic
`fabrica commit-message` preview workflow and the explicitly confirmed mutating
`fabrica commit` user flow. This spec owns the git subprocess and registered-tool
adapter contracts used by those workflows. Git workflow tools must not change the
staged-only, read-only safety contract of `fabrica commit-message`.

### Read-only tools

Read-only tools inspect repository state and must not change the index, working
tree, refs, remotes, or hook state. They include status, staged, unstaged,
commit-history, and ref/range inspection.

### Mutating tools and adapters

Mutating tools and adapters may change local developer state and therefore have a
stricter opt-in boundary. They include:

- approved git commit creation through the `fabrica commit` workflow; and
- pre-commit hook execution, because hooks may rewrite files and create or update
  pre-commit caches.

Mutating capabilities must be explicitly named, separately composed from
read-only tools, and documented with their side effects.

## Users and workflows

The primary users are:

- developers who want local agent workflows to understand the current worktree
  or branch context;
- model-driven coding agents that need bounded self-context before editing,
  reviewing, or explaining changes;
- review and debugging workflows that need commit metadata, changed-file lists,
  or bounded diffs for specific commits and ref ranges.

Typical workflows should start with cheap summary tools, then request narrower
diff tools only when needed. For example, an agent should inspect changed-file
lists before requesting a full diff, and should request a file-specific diff when
the full diff exceeds configured bounds.

## Tool and adapter model

Each model-callable git workflow tool and each git subprocess adapter must have:

- one stable intent;
- one predictable output shape;
- a narrow JSON argument schema;
- deterministic, bounded behavior;
- explicit read-only or mutating side-effect semantics;
- safe failure messages that do not expose private diagnostics or raw sensitive
  content.

Tools must be grouped by stable intent and safety category rather than
multiplexed through a generic git interface. Do not provide a generic `git`,
`git_context`, `git_readonly`, `git_mutate`, `pre_commit`, or shell-like tool
that accepts model-provided subcommands, flags, pathspecs, working directories,
or arbitrary refs without validation.

Tool results should use deterministic structured text that is easy for models and
humans to scan. Tab-separated sections are acceptable where they keep output
stable and compact. Strict JSON output may be introduced later only when a
workflow needs machine-validated structured results.

## Read-only tool contracts

### Status context

Status context tools inspect the current local repository state without changing
the index or working tree and without returning raw diffs.

#### `git_status_summary`

Return a bounded summary of the repository's local state.

The result includes, when available:

- current branch or detached HEAD state;
- HEAD short hash;
- upstream branch;
- counts for staged, unstaged, and untracked files;
- bounded path listings for staged, unstaged, and untracked files.

The result does not include raw diffs or file contents.

Argument schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

### Staged context

Staged context tools inspect changes currently staged in the index without
changing the index or working tree. These are the canonical model-callable staged
git tools. Deterministic commit-message evidence loading remains owned by the
commit-message workflow rather than by ambient model tool access.

#### `git_staged_files`

List staged file paths and staged change statuses.

The result:

- includes staged file paths and status metadata;
- is bounded;
- does not include unstaged-only changes;
- does not include raw diffs or file contents;
- fails clearly when there are no staged files.

Argument schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

#### `git_staged_diff`

Return the bounded full staged diff.

The result:

- includes only staged changes;
- is subject to git diff bounds and tool-loop result bounds;
- fails before returning output when there are no staged changes;
- fails before returning output when the staged diff exceeds configured bounds.

Argument schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

#### `git_staged_file_diff`

Return the bounded staged diff for one staged file path.

The tool accepts a single `path` argument. The path must be a safe relative path
and must appear in the staged file list for the same repository state.

The tool rejects:

- absolute paths;
- empty paths;
- parent-directory traversal;
- paths not present in the staged file list.

Argument schema:

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

Staged tools should not be split further by status category, such as `added`,
`modified`, or `deleted`, unless a future workflow demonstrates a concrete need.
`git_staged_files` carries the status metadata needed to choose narrower diffs.

### Unstaged context

Unstaged context tools inspect tracked worktree changes that are not staged,
without changing the index or working tree. They do not expose untracked file
contents.

#### `git_unstaged_files`

List unstaged tracked file paths and statuses.

The result:

- includes tracked files with unstaged changes;
- does not include staged-only changes;
- does not include untracked file contents;
- does not include raw diffs;
- fails clearly when no unstaged tracked changes exist.

Argument schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

#### `git_unstaged_diff`

Return the bounded full unstaged diff for tracked files.

The result:

- includes only unstaged tracked changes;
- is subject to git diff bounds and tool-loop result bounds;
- fails before returning output when there are no unstaged tracked changes;
- fails before returning output when the unstaged diff exceeds configured bounds.

Argument schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

#### `git_unstaged_file_diff`

Return the bounded unstaged diff for one tracked file.

The tool accepts a single `path` argument. The path must be a safe relative path
and must appear in the unstaged tracked file list for the same repository state.

The tool rejects:

- absolute paths;
- empty paths;
- parent-directory traversal;
- paths not present in the unstaged tracked file list.

Argument schema:

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
state. Commit arguments must resolve to commit objects before detail, changed
file, or diff commands are executed.

#### `git_commit_log`

List recent commits with bounded metadata.

The result includes, when available:

- full hash;
- short hash;
- subject;
- author date;
- ref decorations.

The result does not include full commit messages or raw diffs. The baseline log
scope is recent commits reachable from `HEAD`.

Argument schema:

```json
{
  "type": "object",
  "properties": {
    "count": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50,
      "description": "Maximum number of recent commits to return. Defaults to the configured recent commit count."
    }
  },
  "additionalProperties": false
}
```

#### `git_commit_details`

Return metadata and the full commit message for one commit.

The result includes, when available:

- full hash;
- short hash;
- parent hashes;
- author;
- author date;
- committer date;
- subject;
- body;
- refs.

The result does not include raw diff output.

Argument schema:

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

The result:

- includes paths and status metadata changed by the commit;
- may include old path metadata for renamed or copied files;
- does not include raw diffs.

Argument schema matches `git_commit_details`.

#### `git_commit_diff`

Return the bounded full diff for one commit.

The result:

- is subject to git diff bounds and tool-loop result bounds;
- fails before returning output when the commit diff exceeds configured bounds;
- suggests `git_commit_changed_files` followed by `git_commit_file_diff` when the
  full diff is too large.

Argument schema matches `git_commit_details`.

#### `git_commit_file_diff`

Return the bounded diff for one file in one commit.

The tool accepts `commit` and `path` arguments. The commit must resolve to a
commit object. The path must be a safe relative path and must appear in
`git_commit_changed_files` for the same commit.

For renamed and copied files, the accepted path is the destination or new path.
Old path metadata may appear in changed-file output for context.

Argument schema:

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
feature branch and a base branch, without changing refs or contacting remotes.

Range comparisons use three-dot semantics for pull-request-like review workflows
unless a future spec introduces an explicit comparison-mode argument.

#### `git_ref_changed_files`

List changed paths and statuses between two refs.

The result:

- includes paths and status metadata changed between `base_ref` and `head_ref`;
- may include old path metadata for renamed or copied files;
- does not include raw diffs.

Argument schema:

```json
{
  "type": "object",
  "properties": {
    "base_ref": {
      "type": "string",
      "description": "Base git ref for the comparison."
    },
    "head_ref": {
      "type": "string",
      "description": "Head git ref for the comparison."
    }
  },
  "required": ["base_ref", "head_ref"],
  "additionalProperties": false
}
```

#### `git_ref_diff`

Return the bounded full diff between two refs.

The result:

- is subject to git diff bounds and tool-loop result bounds;
- fails before returning output when the range diff exceeds configured bounds;
- suggests `git_ref_changed_files` followed by `git_ref_file_diff` when the full
  diff is too large.

Argument schema matches `git_ref_changed_files`.

#### `git_ref_file_diff`

Return the bounded diff for one file between two refs.

The tool accepts `base_ref`, `head_ref`, and `path` arguments. Both refs must
validate before inspection. The path must be safe and must appear in
`git_ref_changed_files` for the same ref pair.

For renamed and copied files, the accepted path is the destination or new path.
Old path metadata may appear in changed-file output for context.

Argument schema:

```json
{
  "type": "object",
  "properties": {
    "base_ref": {
      "type": "string",
      "description": "Base git ref for the comparison."
    },
    "head_ref": {
      "type": "string",
      "description": "Head git ref for the comparison."
    },
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

The result includes:

- current branch;
- base ref;
- ahead count;
- behind count.

The tool defaults to the current branch upstream when `base_ref` is omitted and
an upstream exists. It does not fetch from remotes.

Argument schema:

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

The result includes the merge-base full hash and short hash. The tool does not
mutate refs or contact remotes.

Argument schema matches `git_ref_changed_files`.

## Mutating adapter and tool contracts

Mutating capabilities are not read-only context tools. They may change local
developer state and must be composed separately from read-only git context tools.
They must never be exposed through a generic git or shell command surface.

### Approved git commit creation

The approved git commit adapter creates a commit from an already-approved commit
message. It is used by the `fabrica commit` workflow after
`docs/specs/commit-workflows.md` has generated a recommendation, displayed it to
the user, and received explicit approval.

The adapter contract:

- accepts an application command containing only the approved commit message;
- writes the approved message to a temporary commit-message file;
- runs `git --no-pager commit --file <tempfile>` with an explicit argument list
  and `shell=False`;
- starts the subprocess in a dedicated process group and, on timeout, terminates
  that group with a bounded cleanup grace period before reporting timeout;
- preserves subject, body, and Conventional Commits footers exactly;
- uses the composition-owned working directory;
- never stages files, amends commits, bypasses hooks, opens an editor, fetches,
  pulls, pushes, or accepts model-provided git flags;
- maps git unavailable, not-a-repository, no-staged-changes, hook failure,
  timeout, non-zero git failure, decode failure, and unsupported output to
  application-safe errors;
- returns a concise commit result with the new short hash when available.

The user-facing confirmation prompt, approval/rejection behavior, and terminal
output remain owned by `docs/specs/commit-workflows.md`. This spec owns only the
git subprocess adapter safety contract.

### `run_pre_commit`

Run explicitly selected pre-commit hooks through the project-managed
`pre-commit` executable.

When the composition-owned repository has no `.pre-commit-config.yaml`, the
adapter must not invoke `pre-commit`; it returns a non-failure skipped result so
callers can treat repositories without pre-commit configuration as valid.

The tool is mutating because hooks may rewrite tracked files and may create or
update pre-commit caches. It must be registered only when a workflow explicitly
requests mutating developer quality tools.

The default command is equivalent to:

```text
uv run pre-commit run
```

Argument schema:

```json
{
  "type": "object",
  "properties": {
    "hook_id": {
      "type": "string",
      "description": "Optional pre-commit hook id to run. Must be a simple hook identifier, not flags or shell syntax."
    },
    "all_files": {
      "type": "boolean",
      "description": "When true, run against all files using --all-files. Defaults to false."
    }
  },
  "additionalProperties": false
}
```

The adapter contract:

- runs `uv run pre-commit run` through an explicit argument list and
  `shell=False`;
- starts the subprocess in a dedicated process group and, on timeout, terminates
  that group with a bounded cleanup grace period before reporting timeout;
- appends a validated `hook_id` only as a positional hook id;
- appends `--all-files` only when `all_files` is true;
- never accepts arbitrary pre-commit args, arbitrary executables, environment
  overrides, repository paths, shell snippets, or model-provided flags;
- uses the composition-owned working directory;
- returns a skipped result without launching `pre-commit` when no
  `.pre-commit-config.yaml` exists in the repository root;
- bounds stdout and stderr before returning model-callable output;
- reports whether hooks passed, failed, modified files, timed out, or could not
  start;
- does not run `git add`, `git commit`, or any network git operation.

The result should be deterministic structured text that includes:

- status;
- exit code when available;
- bounded stdout and stderr sections;
- duration in seconds;
- a side-effect note when hooks may have modified files.

Failures must be application-safe and must not expose raw private diagnostics,
secrets, full file contents, or unbounded hook output.

## Shared output and bounds requirements

All tools must apply deterministic output bounds before returning model-callable
results. Diff-producing read-only tools are subject to both git diff bounds and
the runtime tool-loop result limit. Mutating adapters that return subprocess
output must bound stdout and stderr before exposing them to the application or
tool layer.

Default bounds:

- maximum diff output: 500,000 characters;
- default recent commit count: 20;
- maximum recent commit count: 50.

Changed-file outputs should represent renamed and copied files with the
destination or new `path` plus `old_path` metadata when available. File-diff tools
accept the destination or new path.

Tools must normalize common git failures into safe application-level errors,
including:

- `git` unavailable;
- working directory not inside a git repository;
- missing staged, unstaged, commit, or ref/range changes for the requested
  context;
- invalid commit or ref arguments;
- command timeout;
- non-zero git failure;
- output decode failure;
- output exceeding configured bounds.

Error messages must be useful for the caller without exposing raw command stderr,
private diagnostics, secrets, or raw file contents.

## Safety boundaries

- Always keep read-only git context tools read-only.
- Always execute git with explicit argument lists and `shell=False`.
- Always run subprocess commands in dedicated process groups when available, and
  terminate the group with bounded cleanup on timeout so hooks or tool descendants
  cannot continue after Fabrica reports the command as timed out.
- Always disable git paging with `--no-pager`.
- Always control the working directory through composition or application options,
  never through model arguments.
- Always validate commit-ish and ref arguments before commands that inspect
  details, changed files, or diffs.
- Always validate file paths as safe relative paths before passing them after
  `--` to git.
- Always place validated path arguments after `--` in git argv.
- Always separate staged, unstaged, commit, ref/range, commit-creation, and
  pre-commit capabilities by name.
- Always register model-callable git workflow tools through explicit composition.
- Always register mutating tools separately from read-only tools.
- Always document mutating tool side effects at the tool contract boundary.
- Never expose arbitrary git command execution.
- Never run mutating git operations such as `git add`, `git reset`,
  `git checkout`, `git switch`, `git stash`, merge, rebase, tag creation, or
  branch deletion.
- Never run `git commit` except through the approved commit creation adapter after
  the owning workflow has established explicit approval.
- Never run network git operations such as `git fetch`, `git pull`, or
  `git push`.
- Never let the model supply arbitrary git flags, command names, pathspecs,
  working directories, or unvalidated revision tokens.
- Never expose arbitrary pre-commit command execution or model-provided
  pre-commit flags.
- Never inspect unstaged changes inside staged commit-message workflows.
- Never change the staged-only behavior of `fabrica commit-message` through this
  tool set.

## Architecture and project structure

Implementation must preserve hexagonal boundaries in the
`developer_workflow` feature slice.

- Spec: `docs/specs/git-workflow-tools.md`.
- Developer-workflow DTOs:
  `src/fabrica/features/developer_workflow/application/dtos/`.
- Developer-workflow ports:
  `src/fabrica/features/developer_workflow/application/ports/`.
- Developer-workflow git subprocess adapters:
  `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/`.
- Developer-workflow registered-tool adapters:
  `src/fabrica/features/developer_workflow/adapters/outbound/` or another
  consistently named developer-workflow-owned adapter package.
- Composition wiring: `src/fabrica/bootstrap/`.
- Unit tests: `tests/unit/features/developer_workflow/`.
- Integration tests: `tests/integration/features/developer_workflow/`.

Application-facing abstractions should be focused by stable intent instead of a
broad catch-all git service. Suitable boundaries include staged context,
worktree context, commit context, ref/range context, commit creation, and
pre-commit execution ports. Port signatures must use application DTOs or
approved domain/application boundary types rather than subprocess results,
transport schemas, or model-provider schemas.

Git subprocess execution belongs in outbound adapters. Registered-tool adapters
bridge developer-workflow capabilities into the agent-runtime tool system and may
depend on agent-runtime tool DTOs at that adapter boundary. Composition helpers
must register read-only and mutating tools independently based on the composed
runtime's requested capabilities.

## Relationship to commit workflows

`fabrica commit-message` remains a deterministic, read-only staged-change
preview workflow. It may use staged git primitives internally, but it must not
silently expose broader worktree, unstaged, commit, or ref/range tools to the
model.

`fabrica commit` remains the explicitly confirmed mutating user workflow owned by
`docs/specs/commit-workflows.md`. The git commit subprocess adapter contract is
owned here so all git subprocess safety rules live in one spec.

## Non-goals

- Do not implement arbitrary read-only shell or git command execution.
- Do not add generic mutating git workflows in this spec.
- Do not add remote or network-backed operations such as fetch, pull, push, or
  hosting-provider API queries.
- Do not add blame or provenance tools in this spec.
- Do not add tag, release, or changelog tools in this spec.
- Do not replace focused staged, unstaged, commit, or ref/range tools with broader
  overloaded tools.
- Do not expose arbitrary pre-commit command execution.
- Do not expose raw private diagnostics, full command stderr, secrets, or raw file
  contents in error messages.

## Testing strategy

Automated tests must remain deterministic and offline. They must not depend on
the developer's ambient repository state.

Unit tests should cover DTO validation for:

- bounded counts;
- safe relative paths;
- commit/ref identifier validation shape;
- changed-file status parsing;
- renamed and copied path metadata;
- diff bounds.

Unit tests should cover subprocess command construction for:

- fixed argv only;
- `--no-pager` where applicable;
- path arguments placed only after `--`;
- no model-supplied flags;
- no mutating or network git commands.

Unit tests should cover subprocess adapters with injectable runners for:

- success for each tool group;
- git unavailable;
- not a repository;
- invalid commit/ref;
- no matching changes;
- timeout;
- non-zero git failure;
- decode failure;
- oversized output.

Unit tests should cover path validation for file-diff tools:

- rejects absolute paths;
- rejects empty paths;
- rejects `..` traversal;
- rejects unknown, non-staged, non-unstaged, or non-changed paths for the relevant
  tool group;
- accepts known changed paths with normal relative components.

Unit tests should cover registered-tool wrappers for:

- expected tool names, descriptions, and argument schemas;
- successful output mapping;
- invalid arguments mapped to safe failures;
- adapter failures mapped to safe tool failures;
- output remaining bounded by tool-loop limits.

Tests for staged-only commit-message behavior must prove that commit-message
workflows remain staged-only and do not gain broader read-only git context as
ambient model tools.

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency.
Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`
- Focused developer-workflow tests during iteration:
  `uv run pytest tests/unit/features/developer_workflow`

Manual verification for implementation changes may use a temporary local git
repository with staged changes, unstaged tracked changes, branches, and sample
commits.

## Success criteria

- The spec defines read-only git context capabilities for status, staged,
  unstaged, commit, and ref/range workflows.
- The tool set covers agent self-context, review summarization, and commit
  archaeology/debugging.
- Staged, unstaged, commit, and ref/range concerns are explicit and separately
  named.
- Arbitrary git command execution and all mutating or network git operations are
  forbidden.
- Model-callable git workflow tools require explicit composition.
- Tool outputs and diff results are bounded.
- Architecture boundaries keep git subprocess execution in developer-workflow
  outbound adapters and model tool registration behind explicit adapter and
  composition boundaries.
- Default automated tests remain deterministic and offline.
- `fabrica commit-message` remains staged-only and read-only.
