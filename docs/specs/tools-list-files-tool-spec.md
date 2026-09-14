# Spec: List Files Tool

## Status

- State: Draft.
- Implementation status: Not implemented.
- Proposed by: Maintainer-directed agent-design discussion.
- Proposed on: September 14, 2026.
- Acceptance basis: Not yet accepted. The maintainer authorized creation of this
  specification after identifying that initial workspace discovery currently
  falls back to approval-required shell commands such as `find`. On September 14,
  2026, the maintainer confirmed the binding Version 1 traversal, result-bounding,
  defaulting, truncation, and cancellation decisions recorded below; acceptance of
  the complete specification remains pending.
- Supersedes: Not applicable.

This document is the proposed canonical source of truth for a model-facing,
read-only `list_files` tool. It must be explicitly accepted before implementation
or changes to the accepted default coding-agent-session tool set.

## Objective

Define a safe, bounded, provider-neutral workspace-tree discovery primitive for
coding agents. The tool must let an agent discover directory structure and file
paths without executing approval-required shell commands such as `find`, `ls`,
`tree`, or `dir`.

The design goal is to fill the gap between `search_codebase`, which searches file
contents but deliberately does not search filenames or directories, and
`read_files`, which reads already-known files.

## Current Context

- `docs/specs/coding-agent-session-spec.md` owns the accepted Version 1 terminal
  session and its default tool set.
- `docs/specs/tools-read-files-tool-spec.md` owns inspection of known workspace
  file contents.
- `docs/specs/tools-search-codebase-tool-spec.md` owns bounded regex discovery in
  workspace file contents; filename and directory search are explicitly out of
  scope for that tool.
- `run_commands` can perform directory listing today, but all eligible commands
  require explicit terminal approval in Version 1.
- Workspace-local `.fabrica/` contains sensitive session records and must not be
  exposed by this discovery primitive.

## Scope

### In Scope

- Bounded, read-only listing of workspace-relative directory entries.
- Deterministic file-path and directory-path discovery.
- Explicit result-limit and depth-limit metadata.
- Workspace containment, cancellation, timeout, and stable error outcomes.
- A model-facing contract that instructs the agent to prefer `list_files` over
  shell commands when it only needs workspace structure.

### Out of Scope

- Reading file contents; use `read_files`.
- Searching file contents, symbols, filenames by regex, or Git history; use
  `search_codebase` or a future dedicated capability.
- Generic `find`, `tree`, `ls`, shell, glob-expression, or predicate-language
  compatibility.
- File mutation, permission changes, process execution, or Git operations.
- File hashes, timestamps, sizes, permissions, MIME types, ownership, or content
  previews.
- Following or traversing symlinks.
- Pagination tokens or persistent traversal state in Version 1.

## Requirements

- R1: The tool must list workspace structure without requiring command approval
  when the request is within its declared bounds.
- R2: All model-facing paths and returned paths must be normalized,
  workspace-relative POSIX paths; host-absolute paths must never be returned.
- R3: The tool must reject blank, absolute, backslash-containing, and
  parent-escaping request paths.
- R4: The tool must list only the requested directory or its descendants inside
  the configured workspace root.
- R5: The tool must produce a deterministic ascending order by returned relative
  path, independent of host filesystem enumeration order.
- R6: The tool must return only `file`, `directory`, `symlink`, or `other` entry
  kinds. It must not open regular files or traverse symlinks. Recursive traversal
  must use descriptor-relative, no-follow operations or an equivalently race-safe
  mechanism; the tool must not be exposed where that guarantee is unavailable.
- R7: Hidden entries must be excluded by default. `.fabrica` must be excluded
  always, including when hidden entries are requested.
- R8: The tool must apply configured depth, entry-count, output-size, and
  deadline bounds, and must clearly report any limiting condition. The output-size
  bound applies to the complete compact JSON text delivered to the model,
  including its envelope and required truncation metadata.
- R9: An empty directory must return a successful empty result, not an error.
- R10: The tool must translate filesystem failures into stable tool outcomes and
  must not leak host filesystem details. Cancellation and timeout must return
  unsuccessful outcomes without a partial entries payload.
- R11: The tool must be owned by a dedicated `workspace_listing` feature slice;
  its application core must not depend on POSIX APIs or registered-tool details.

## Desired Behavior

The intended agent workflow is:

```text
list_files
      ↓
search_codebase
      ↓
read_files
      ↓
run_commands only when execution or another unavailable capability is required
```

For a repository-orientation request such as “What do you think about this
repository?”, an agent should be able to call `list_files` before requesting any
command approval.

## Tool Interface

Tool name:

```text
list_files
```

Canonical model-facing JSON schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1,
      "default": "."
    },
    "max_depth": {
      "type": ["integer", "null"],
      "minimum": 0
    },
    "max_entries": {
      "type": ["integer", "null"],
      "minimum": 1
    },
    "include_hidden": {
      "type": "boolean",
      "default": false
    }
  },
  "additionalProperties": false
}
```

Defaults:

```text
path           = "."
max_depth      = 2
max_entries    = 200
include_hidden = false
```

An omitted `path` normalizes to `"."`. An omitted or explicit `null`
`max_depth` or `max_entries` normalizes to the corresponding default above; it
never requests an unbounded listing.

Version 1 hard bounds:

```text
max_depth      <= 8
max_entries    <= 1,000
output chars   <= 48,000
```

The output-character bound applies to the complete compact JSON text delivered
to the model, including the result envelope and truncation metadata. The adapter
must reserve space for required metadata before appending entries.

Example request:

```json
{
  "path": ".",
  "max_depth": 2,
  "max_entries": 200
}
```

## Model-Facing Description

```text
List files and directories within the workspace.

Use this tool to discover repository structure, filenames, and available paths
before reading files or searching file contents.

The requested path must be workspace-relative. Results are deterministic and
bounded by depth and entry limits. If the listing is truncated, narrow the path
or lower the requested depth.

Prefer list_files over shell commands such as find, ls, tree, or dir when you
only need workspace structure.
```

## Path, Visibility, and Traversal Semantics

### Request path

`path` identifies an existing directory relative to the workspace root. `"."`
identifies the root itself. The path must not be blank, absolute, contain `\\`,
or contain `..` components.

The requested directory itself is not included in `entries`; all returned paths
are relative to the workspace root.

### Hidden entries

An entry is hidden when any listed descendant component begins with `.`.

- When `include_hidden` is `false`, hidden entries and their descendants are
  omitted.
- When `include_hidden` is `true`, hidden entries may be included subject to all
  other limits and policy.
- `.fabrica` and all of its descendants are always omitted. This protects
  sensitive workspace-local session records from model-visible discovery.

### Symlinks and special files

The adapter must use descriptor-relative, no-follow directory-entry inspection
and recursive opening, or an equivalently race-safe mechanism. If the host
platform cannot provide that guarantee, bootstrap must not expose `list_files`.
Path validation alone is insufficient: a directory entry may be replaced with a
symlink after inspection and before recursive opening.

- A symlink is returned as `kind: "symlink"` but is never followed or traversed.
- Sockets, FIFOs, device nodes, and unrecognized filesystem objects are returned
  as `kind: "other"` and are never opened.
- Regular files are returned as `kind: "file"`; their contents are not read.

## Result Contract

Successful results must have this logical shape:

```json
{
  "path": ".",
  "entries": [
    { "path": "README.md", "kind": "file" },
    { "path": "docs", "kind": "directory" },
    { "path": "docs/specs", "kind": "directory" }
  ],
  "truncated": false,
  "truncation_reasons": []
}
```

`entries` must be sorted by `path` in ascending bytewise/Unicode code-point
order after normalized path construction.

Direct children of the requested directory have depth `1`. Entries at
`max_depth` are returned, but directories at that depth are not opened.

If one or more configured data bounds are reached, the result remains successful
and sets:

```text
truncated = true
truncation_reasons = [MAX_DEPTH, MAX_ENTRIES, MAX_OUTPUT_CHARS]
```

`truncation_reasons` contains every reached configured data bound in the fixed
order shown, omitting reasons that did not apply. The complete compact JSON
result, including this metadata, must remain within the 48,000-character output
bound.

The adapter must not claim that a truncated result is complete. Version 1 has no
continuation token; callers must narrow `path` or reduce `max_depth`.

Cancellation and deadline expiration are not successful truncations. They return
respectively `LIST_CANCELLED` or `LIST_TIMEOUT` with no `entries` payload, even
when traversal collected entries before the interruption.

## Stable Error Vocabulary

The application boundary must expose only these error codes for an unsuccessful
listing request:

```text
INVALID_INPUT
INVALID_PATH
PATH_OUTSIDE_WORKSPACE
NOT_FOUND
NOT_A_DIRECTORY
PERMISSION_DENIED
LIST_TIMEOUT
LIST_CANCELLED
IO_ERROR
```

The model-facing adapter must render failures as structured recoverable outcomes
where continued agent operation is safe.

## Architecture and Composition Boundaries

The implementation must introduce a dedicated vertical slice:

```text
src/fabrica/features/workspace_listing/
├── application/
│   ├── dtos/
│   ├── ports/
│   └── use_cases/
└── adapters/
    ├── inbound/registered_tool/
    └── outbound/posix_filesystem/
```

- The application layer owns list commands, limits, entries, results, and error
  vocabulary.
- The outbound POSIX adapter owns secure directory traversal and host filesystem
  behavior.
- The registered-tool inbound adapter owns argument parsing and rendering.
- Bootstrap owns construction and inclusion in the coding-agent session after
  this draft is accepted.
- `workspace_reading` and `workspace_searching` must not be expanded with this
  capability merely for convenience.

## Acceptance Checks

| Requirement         | Observable acceptance check                                                                                                                                                                                                                                                            |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Native discovery    | A repository-orientation evaluation invokes `list_files` without a `run_commands` approval request for `find`, `ls`, `tree`, or `dir`.                                                                                                                                                 |
| Bounds              | Tests prove omitted and `null` limits normalize to defaults; direct children are depth 1; boundary-depth directories are not opened; entry and output limits return every reached reason in the specified order; and the complete serialized JSON result is at most 48,000 characters. |
| Determinism         | Fixture listings remain lexically ordered despite shuffled host enumeration.                                                                                                                                                                                                           |
| Containment         | Tests reject escaping paths and prove no host-absolute path is returned.                                                                                                                                                                                                               |
| Symlink safety      | Integration tests prove inside, outside, cyclic, and replacement-race symlinks are reported but never traversed; composition omits the tool when the required race-safe traversal capability is unavailable.                                                                           |
| Sensitive state     | Tests prove `.fabrica` is omitted with both hidden-entry settings.                                                                                                                                                                                                                     |
| Interruption        | Tests prove cancellation and timeout return `LIST_CANCELLED` or `LIST_TIMEOUT` without partial entries payloads.                                                                                                                                                                       |
| Default composition | Once accepted and implemented, the session-composition test exposes `list_files` before `run_commands`.                                                                                                                                                                                |

## Testing and Validation

Implementation must include focused unit tests for DTO validation, depth and
entry accounting, complete-payload output truncation, ordered multi-reason
metadata, request-default normalization, ordering, and hidden-path policy;
integration tests for POSIX directory handling, containment, static and
replacement-race symlink behavior, permission errors where portable,
cancellation, and timeout; and composition tests for registered-tool exposure
and fail-closed omission when race-safe traversal is unavailable.

Before handoff, implementation must pass:

```bash
uv run ruff check .
uv run ty check .
uv run pytest
```

## Open Decisions

The following decisions are intentionally deferred and block implementation
details only if the draft is accepted without further amendment:

- Whether `include_hidden=true` should show `.git` names while still refusing to
  traverse the directory. This draft permits it; `.fabrica` remains always
  hidden.
- Whether a future revision needs include/exclude glob filters. Version 1 does
  not include them.
