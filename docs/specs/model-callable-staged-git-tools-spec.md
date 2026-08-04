# Spec: Model-Callable Staged Git Tools

## Objective

Add optional model-callable tools for read-only staged git context so general
agent/tool-loop workflows can inspect staged changes on demand, while preserving
the existing deterministic `commit-message` workflow that loads staged diff
context before model invocation.

The primary user is a developer running Fabrica in a local git repository
who wants an agent workflow to inspect staged changes safely and selectively
without mutating repository state.

## Current context

- The existing commit-message workflow is implemented under
  `developer_workflow` and already reads staged git diff context
  deterministically.
- `GitStagedChangesSubprocessLoader` lives at
  `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/adapter.py`.
- The current outbound application port is
  `GitStagedChangesLoader.load() -> GitStagedDiff` in
  `src/fabrica/features/developer_workflow/application/ports/git_staged_changes.py`.
- `PrepareCommitMessageRun` calls the staged changes loader directly before
  creating a `LocalAgentRunCommand`.
- `src/fabrica/bootstrap/local_agent_runtime.py` wires the concrete
  subprocess loader into the commit-message workflow.
- The agent runtime already has an explicit registered-tool mechanism:
  - `RegisteredTool`
  - `RegisteredToolExecutor`
  - `ToolDefinition`
  - `ToolCallRequest`
  - `ToolCallResult`
- Current registered tools are opt-in composition-time capabilities, not
  ambient/global model powers.
- Previous specs explicitly kept model-callable git tools outside the
  commit-message MVP; this spec covers that future direction.

## Assumptions

- The existing deterministic commit-message workflow should remain deterministic
  and should not be rewritten to depend on model tool calls.
- Staged git tools should be exposed only through explicit composition/wiring,
  not globally to every model run.
- The first tool set should cover staged changes only, not unstaged changes,
  branch state, history, commit creation, or arbitrary git commands.
- Tool calls should use a configured working directory from composition, not a
  model-supplied repository path.
- Atomic tools should be split by stable model intent and output shape rather
  than by every low-level git command.

## Desired behavior

Add three read-only model-callable staged git tools.

### `git_staged_files`

List staged file paths and staged change statuses.

- Returns a bounded textual or structured-text representation of staged files.
- Uses a read-only git command such as
  `git --no-pager diff --staged --name-status`.
- Fails clearly when:
  - `git` is unavailable;
  - the working directory is not inside a git repository;
  - there are no staged files;
  - git execution times out or fails;
  - output cannot be decoded safely.

Initial argument schema should be empty.

### `git_staged_diff`

Return the full staged diff as bounded tool output.

- Reuses the existing staged diff loading capability where practical.
- Uses `git --no-pager diff --staged`.
- Applies existing or equivalent `GitStagedDiffBounds` before returning output.
- Also remains subject to `ToolLoopLimits.max_tool_result_chars` when returned
  through the tool loop.
- Fails before returning raw output when there are no staged changes or the
  staged diff exceeds configured bounds.

Initial argument schema should be empty.

### `git_staged_file_diff`

Return the staged diff for one staged file path.

- Accepts a single `path` argument.
- Validates that `path` is a safe relative path and refers to a file that is
  currently staged.
- Rejects absolute paths, parent-directory traversal, empty paths, and paths not
  present in the staged file list.
- Uses a read-only git command equivalent to
  `git --no-pager diff --staged -- <path>` after validation.
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

## Non-goals

- Do not expose arbitrary git command execution.
- Do not expose `git commit`, `git add`, `git reset`, checkout, branch
  switching, stash, push, pull, or any mutating git operation.
- Do not inspect unstaged changes in this spec.
- Do not let the model choose the repository working directory.
- Do not replace deterministic commit-message staged-diff loading with a model
  tool call.
- Do not add broad multi-purpose `git` or overloaded `git_staged_changes` tools.

## Tool atomicity rule

Use one tool per stable model/user intent, where each tool has:

- one clear risk profile;
- one predictable output shape;
- a narrow argument schema;
- bounded and deterministic behavior;
- no hidden mutation.

For staged git context, that maps to:

```text
git_staged_files      -> discover what is staged
git_staged_diff       -> inspect the whole staged patch
git_staged_file_diff  -> inspect one staged file patch
```

Do not split further by status category (`added`, `modified`, `deleted`) unless
a future workflow proves the need. `git_staged_files` can return status
metadata.

## Architecture and project structure

Implementation should preserve hexagonal boundaries:

- Application DTOs:
  - `src/fabrica/features/developer_workflow/application/dtos/`
  - Add staged file/status DTOs if needed, such as `GitStagedFile`,
    `GitStagedFileList`, or `GitStagedFileStatus`.
- Application ports:
  - `src/fabrica/features/developer_workflow/application/ports/git_staged_changes.py`
  - Generalize from only `load()` if needed, or add focused ports for staged
    file listing and per-file diff loading.
- Outbound subprocess adapter:
  - `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_subprocess/`
  - Continue to own all git subprocess execution.
- Tool adapter/factory:
  - Prefer a developer-workflow-owned adapter that converts staged git
    application capabilities into `RegisteredTool` instances.
  - Candidate location:
    `src/fabrica/features/developer_workflow/adapters/outbound/git_staged_changes_registered_tool/`.
  - This adapter may import agent-runtime tool DTOs because it is an adapter
    bridging developer-workflow capabilities into the agent-runtime tool system.
- Composition root:
  - `src/fabrica/bootstrap/local_agent_runtime.py`
  - Add explicit helpers that register staged git tools only when requested by a
    composed runtime.

## Desired API shape

A likely application-facing abstraction:

```python
class GitStagedChanges(Protocol):
    def list_files(self) -> GitStagedFileList: ...
    def load_diff(self) -> GitStagedDiff: ...
    def load_file_diff(self, path: str) -> GitStagedDiff: ...
```

Alternatively, keep smaller focused ports if that better matches existing style:

```python
class GitStagedFilesLister(Protocol): ...


class GitStagedDiffLoader(Protocol): ...


class GitStagedFileDiffLoader(Protocol): ...
```

The implementation plan should choose the smallest clear interface that avoids a
vague catch-all service.

## Commands and validation

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`
- Focused unit tests during iteration:
  - `uv run pytest tests/unit/features/developer_workflow`
  - `uv run pytest tests/unit/features/agent_runtime/application/test_run_tool_loop.py`
  - registered-tool adapter tests if touched

Manual verification after implementation may use a temporary or local git
repository:

```bash
git add <files>
uv run fabrica <future command or tool-loop smoke path>
```

Default automated tests must remain deterministic and offline. They must not
depend on the developer's ambient staged git state.

## Testing strategy

- Unit-test staged file DTO validation:
  - non-empty relative paths;
  - status parsing;
  - bounds on list/context output.
- Unit-test subprocess adapter behavior with an injectable git command runner:
  - staged file listing success;
  - full staged diff success;
  - per-file staged diff success;
  - no staged files;
  - not a git repository;
  - unavailable git executable;
  - timeout;
  - non-zero git failure;
  - decode failure;
  - oversized output.
- Unit-test path validation for `git_staged_file_diff`:
  - rejects absolute paths;
  - rejects `..` traversal;
  - rejects unknown/non-staged path;
  - accepts staged paths with normal relative components.
- Unit-test registered tool wrappers:
  - each tool has the expected `ToolDefinition` name, description, and argument
    schema;
  - successful handler output maps to tool result text;
  - invalid arguments map to invalid tool request behavior;
  - loader failures map to safe tool failures without raw sensitive diagnostics;
  - output is bounded by tool-loop limits.
- Preserve existing commit-message workflow tests to prove deterministic staged
  diff loading still happens before model invocation.

## Boundaries

- Always keep git operations read-only.
- Always use explicit git argument lists with `shell=False`.
- Always disable git paging with `--no-pager`.
- Always keep working directory controlled by composition/options, not model
  arguments.
- Always bound staged diff and tool result output.
- Always expose staged git tools only by explicit composition.
- Ask before adding unstaged-change tools, repository-status tools, commit
  creation, file mutation, arbitrary git command execution, or CLI flags for
  automatic tool exposure.
- Never mutate repository state.
- Never expose secrets or full private diagnostics in errors/observations.
- Never let the model supply arbitrary git flags or pathspecs.

## Success criteria

- A spec documents optional model-callable staged git tools separately from the
  deterministic commit-message workflow.
- The tool set is split into `git_staged_files`, `git_staged_diff`, and
  `git_staged_file_diff` with clear contracts.
- The spec preserves read-only, staged-only git boundaries.
- The spec requires explicit composition for tool exposure.
- The spec defines project structure, testing strategy, validation commands, and
  non-goals.
- Existing commit-message behavior remains deterministic and does not depend on
  model tool calls.

## Open questions

1. Should tool output be plain text only for model friendliness, or should we
   introduce a structured JSON-ish text format for `git_staged_files`?
2. Should `git_staged_diff` return `GitStagedDiff.to_context_block()` text, raw
   diff text, or a dedicated tool-oriented wrapper with a label and metadata?
3. Should per-file diff support renamed files in v1, and if so what path should
   the model pass: old path, new path, or both?
4. Should these tools be associated with selected skills only, or also be
   available to explicitly configured generic tool-loop runtimes?
5. Should we add a dedicated composition helper such as
   `create_staged_git_registered_tools(...)`, or fold this into an existing
   model-driven skill runtime options object?

## Proposed first implementation slice

For v1, implement the smallest coherent slice:

1. Extend the staged git adapter/application boundary to support file listing and
   per-file diff.
2. Add `git_staged_files`, `git_staged_diff`, and `git_staged_file_diff`
   registered-tool factories.
3. Add tests for adapter behavior, path validation, tool definitions, and safe
   error mapping.
4. Add explicit composition helpers, but do not enable these tools by default for
   every run.
