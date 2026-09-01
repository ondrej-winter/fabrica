# Spec: Apply Patch Tool

## Status

- State: Accepted.
- Accepted by: Ondřej Winter
- Accepted on: September 1, 2026
- Revision: Accepted on September 1, 2026.
- Supersedes: Not applicable.

This document is the canonical source of truth for the requirements it defines. Derived plans and implementation must preserve its objective, constraints, execution boundaries, and success criteria; material changes require an updated and re-confirmed specification.

## Objective

Define the model-facing and host-facing specification for an `apply_patch`
filesystem mutation tool.

The tool is for autonomous coding agents that need one preferred model-facing
primitive for creating, modifying, deleting, and moving UTF-8 text files in a
configured workspace. It must favor contextual, reviewable patches over
line-number edits, shell text rewrites, whole-file replacement, or multiple
operation-specific mutation tools.

`apply_patch` is the sole public model-facing filesystem mutation tool in v1.
Add, Update, Delete, and Move are protocol operations inside this one tool, not
separately registered `create_file`, `delete_file`, `move_file`, or `mkdir`
tools. Implementations may still use operation-specific internal components and
DTOs as long as the model observes one immutable patch plan, one authorization
decision, one workspace mutation lease, and one final result.

Version 1 intentionally optimizes for safety and deterministic behavior over
implementation simplicity and broad portability. Unsupported cases must fail
before mutation rather than silently degrade to weaker guarantees.

## Current Context

- Project: `fabrica`, a Python 3.13 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime-spec.md`.
- Read-only file inspection is owned by `docs/specs/tools-read-files-tool-spec.md`.
- Textual source discovery is owned by `docs/specs/tools-search-codebase-tool-spec.md`.
- Command execution is owned by `docs/specs/tools-run-commands-tool-spec.md`.
- This spec defines the durable `apply_patch` tool contract. The implementation
  is owned by the `workspace_editing` feature and bootstrap composition.

## Design principles

`apply_patch` must allow a model to:

- create regular UTF-8 text files;
- modify existing regular UTF-8 text files with context-based hunks;
- delete regular files;
- move or rename regular files, optionally while modifying their contents;
- change multiple files in one tool call.

The implementation must separate:

- parsing;
- validation;
- hunk matching;
- change planning;
- derived effect planning;
- authorization and approval;
- staging;
- filesystem commit;
- result formatting.

Operation-specific internal tools, use cases, DTOs, validators, and filesystem
adapter methods are encouraged when they keep the implementation clear. They must
compose into the single public `apply_patch` operation before authorization.

Add and Move destination parent directories are created automatically when they
are missing. These directory creations are derived planned effects, not separate
model-authored actions. They must be validated, authorized, journaled before they
become visible, reported, rolled back, and recovered with the same rigor as
explicit file actions.

All expected rejections must be structured and recoverable when no mutation, or
only successfully removed reversible preparation effects, occurred. Indeterminate,
partial, or retained visible mutation outcomes must stop the agent loop and
require inspection or recovery unless the result contract explicitly marks them as
safe to continue.

## Mutation lifecycle

Every `apply_patch` call follows one ordered lifecycle. The implementation must
not blur these phases when reporting cancellation, rollback, or recovery results.

1. **Side-effect-free planning** acquires the workspace mutation lease, parses the
   patch, snapshots sources and destination evidence, matches hunks, derives
   directory effects, builds the immutable plan, evaluates policy, and obtains any
   required approval. No filesystem mutation occurs in this phase.
2. **Reversible preparation** begins only after approval and revalidation. Before
   the first planned parent directory is created, the implementation must durably
   record recovery intent for that directory effect. Planned directories are then
   created shallowest-first through pinned handles and their identities are
   recorded. Staging artifacts may be created and populated in the same phase.
   These are visible or recoverable effects, but they are still before the file
   commit point.
3. **File commit** begins immediately before the first visible file rename,
   replacement, or deletion. This is the explicit commit point for file actions.
   From this point forward, the operation must complete bounded commit or
   rollback and report the actual terminal state.
4. **Cleanup and recovery** removes stage artifacts and rollback-eligible created
   directories when safe. While the process is active, the operation owns cleanup.
   After interruption or restart, the durable journal and startup recovery own the
   remaining cleanup or operator-facing recovery decision.

The host must never return while unmanaged mutation can continue in the
background. If cleanup cannot prove that all visible preparation effects were
removed, the final result must report each created directory as retained, failed
to remove, or uncertain rather than claiming a clean no-mutation outcome.

## Tool interface

Tool name:

```text
apply_patch
```

Canonical model-facing JSON schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "input": {
      "type": "string",
      "minLength": 1,
      "maxLength": 262144
    }
  },
  "required": ["input"],
  "additionalProperties": false
}
```

The public model-facing schema remains `{ "input": string }`. A compatibility
adapter may accept provider-specific raw string input and normalize it before
canonical validation, but the core parser receives a string from the canonical
schema.

The operation is not automatically retried. Filesystem edits are stateful, and
automatic retry after an indeterminate failure can duplicate or incorrectly
reapply an operation. Duplicate model tool delivery is handled by the runtime
call ledger described below, not by re-executing the patch engine.

No other v1 model-facing filesystem mutation tool may overlap with
`apply_patch`. Hosts may expose lower-level internal commands only behind the
workspace editing application boundary; they must not be registered as separate
model-callable create, update, delete, move, or directory tools.

## Model-facing description

Recommended concise tool description:

```text
Apply context-based patches to UTF-8 text files in the workspace.

Pass the raw patch body directly in `input`.

Supported operations:
- *** Add File: <path>
- *** Update File: <path>
- *** Delete File: <path>
- *** Move to: <new-path> immediately after an Update File header

Use context lines with one leading space, deleted lines with -, and inserted
lines with +. Use @@ or @@ <anchor> to separate hunks. Use
@@ before <anchor> or @@ after <anchor> for insertion-only hunks.

Do not use line numbers. Prefer small, focused patches.

Add File and Move destinations automatically create missing parent directories
inside the workspace. Created directories are shown in the planned changes and
approval preview.

The full patch is planned and authorized before commit. If any hunk cannot be
matched safely, the patch is rejected and no intended changes are applied.
```

The model should use raw patch bodies, not shell wrappers such as
`apply_patch <<"EOF"`.

## Patch protocol

Canonical patch form:

```text
*** Begin Patch
<action>
<action>
...
*** End Patch
```

Both sentinels are required by the core v1 parser. Sentinel-less bodies, legacy
shell wrappers, and unprefixed context lines are compatibility forms only. A
separate adapter may normalize them before invoking the core parser, but they are
not v1 conformance.

### Add file

Syntax:

```diff
*** Add File: src/example.py
+def example():
+    return 42
```

Every content line in a non-empty `Add File` block must begin with `+`. The
leading `+` is syntax and is not written to the resulting file. `Add File` means
create a new file only; it must never overwrite an existing path.

If the destination parent directory does not exist, the implementation creates
the missing parent directory chain as derived planned effects. The nearest
existing ancestor must be a real directory inside the workspace, and every new
directory component must pass the same path, policy, alias, symlink, and
filesystem capability validation as file paths.

An `Add File` block with no content lines creates an explicit zero-byte file. A
non-empty added file ends with a terminal newline by default. A zero-byte added
file has no terminal newline. Added files are UTF-8 without BOM, use LF line
endings, and receive base mode `0666` filtered by the configured workspace umask.
The tool must not infer executable mode from filename, extension, or shebang.

### Delete file

Syntax:

```diff
*** Delete File: src/obsolete.py
```

The target must exist and must be a regular file. Deletion does not include file
contents in the patch. Preflight snapshots the exact file identity and content
hash, authorization displays the deletion, and commit revalidates identity and
hash before deletion.

### Update file

Syntax:

```diff
*** Update File: src/example.py
@@
 def example():
-    return 41
+    return 42
```

Update hunk bodies are ordered tagged lines. Each body line must start with one
of:

- one space for context;
- `-` for deleted lines;
- `+` for inserted lines.

The parser removes exactly one syntax prefix. File content that literally begins
with protocol-looking text, such as `*** End Patch`, remains unambiguous when it
is prefixed as content. Unprefixed non-header lines inside an action are invalid.

An ordinary `Update File` without `Move to` must contain at least one effective
hunk and must change the resulting bytes. No-op updates fail with `NO_OP_ACTION`.

### Move or rename

Syntax:

```diff
*** Update File: src/old.py
*** Move to: src/new.py
@@
-old_name = True
+new_name = True
```

The move directive must occur immediately after the corresponding `Update File`
header. A zero-hunk `Update File` with `Move to` is a valid pure rename when the
source and destination paths differ. A move with hunks has these logical
semantics:

```text
read source snapshot
→ apply update hunks to planned content
→ write resulting contents to destination
→ remove source
```

The destination must be inside the workspace, must not exist, must not collide
with another path in the patch, and must be on a filesystem that supports the
same atomic rename and durability guarantees required by the commit protocol.
Cross-device moves fail with `CROSS_DEVICE_MOVE_UNSUPPORTED`.

If the destination parent directory does not exist, the implementation creates
the missing parent directory chain as derived planned effects before writing the
moved content. A Move may not create or replace its destination file implicitly;
only missing destination parent directories are eligible for automatic creation.

### Hunk headers and anchors

A replacement hunk may begin with either:

```text
@@
```

or:

```text
@@ <anchor>
```

`@@ <anchor>` requires exactly one complete source line matching `<anchor>` in
the allowed search region. Zero matches fail with `ANCHOR_NOT_FOUND`; multiple
matches fail with `AMBIGUOUS_ANCHOR`. The anchor is not a line number and is not
implicitly part of the old sequence. Ordinary anchored replacement searches after
the anchor line unless the anchor line is repeated as a space-prefixed context
line.

Insertion-only hunks are valid only with explicit placement:

```diff
@@ before class UserService:
+# inserted before the anchor line
```

```diff
@@ after class UserService:
+# inserted after the anchor line
```

The remainder after `before` or `after` is the exact unique anchor line. A plain
`@@` hunk with only `+` lines is invalid because it has no safe source span.

### End-of-file assertion

Syntax:

```text
*** End of File
```

`*** End of File` is a strict postcondition and may appear only after the final
hunk of an `Update File` action. After applying that final hunk, the hunk's
resulting span must terminate at logical EOF. For `@@ after <anchor>` insertion,
the assertion is valid only when the anchor is the final source line.

### Terminal newline marker

Update and move actions preserve the source file's terminal-newline state unless
the final hunk explicitly changes it with:

```text
*** No Newline at End of File
```

The marker makes adding or removing the terminal newline intentional and
testable. It is not inferred from the patch container's final newline.

## Parsing model

Parsing is side-effect free and produces an ordered intermediate representation.

Suggested representation:

```text
Patch
  actions: list[FileAction]

FileAction
  type: ADD | UPDATE | DELETE
  source_path: WorkspaceRelativePath
  destination_path: WorkspaceRelativePath | null
  new_file_lines: list[PatchContentLine] | null
  hunks: list[Hunk]

Hunk
  header: UNANCHORED | ANCHORED | INSERT_BEFORE | INSERT_AFTER
  anchor: str | null
  lines: list[HunkLine]
  eof_required: bool
  terminal_newline_directive: PRESERVE | ENSURE_PRESENT | ENSURE_ABSENT

HunkLine
  type: CONTEXT | DELETE | INSERT
  text: str
```

Implementations may store ordered `old_lines` and `new_lines` in addition to the
tagged body, but they must not lose the order of context, deletion, and insertion
lines.

## Matching strategy

Matching is over complete logical source lines, not substrings within a line.
Every hunk is matched against the same immutable source snapshot for its file.

### Pass 1: exact match

Match the complete ordered old sequence exactly. The old sequence consists of the
hunk's `CONTEXT` and `DELETE` lines in order.

### Pass 2: trailing-whitespace tolerance

If exact matching fails, the matcher may accept a candidate where:

```text
rstrip(source_line) == rstrip(patch_line)
```

for every old-sequence line. The result records
`match_quality = "trailing_whitespace"`.

Trailing-whitespace tolerance must not rewrite untouched context. Only source
spans identified by `DELETE` lines are replaced; unchanged context bytes come
from the source snapshot. Inserted `+` lines are written exactly as supplied,
apart from the file's EOL encoding.

### No other fuzzy matching

Version 1 omits indentation-normalized, fuzzy, approximate, or semantic matching
entirely. These modes are not merely disabled; they are outside v1.

### Uniqueness and ambiguity

There is no fixed minimum number of context lines. A deletion/replacement-only
hunk may be accepted if its complete ordered old sequence has exactly one match
in the allowed region. Multiple candidate regions fail with `AMBIGUOUS_HUNK`.

After all hunks match against the snapshot, their source spans must be strictly
ordered and non-overlapping. Overlap, reversed order, or competing insertion
positions fail before mutation.

## Path and action validation

A patch must not contain multiple top-level actions for the same source path.
Multiple hunks for one file must appear inside a single `Update File` action.

In v1, every canonical or aliased path mentioned anywhere in the patch must be
globally disjoint, except for the source/destination pair belonging to the same
move action. Move chains, swaps, delete-then-add replacement, and shared
source/destination graph nodes fail preflight.

The implementation must reject:

- absolute paths;
- empty paths;
- parent-directory traversal;
- paths outside the configured workspace;
- any symlink or reparse-point component, including contained symlinks;
- path aliases under host filesystem case or Unicode-normalization behavior;
- case-only or normalization-only renames;
- existing parent path components that are not directories;
- missing parent directories for `Update` and `Delete` sources;
- directories and non-regular files;
- files with multiple hard links;
- special files such as FIFOs, sockets, devices, and platform equivalents.

Missing parent directories for `Add File` targets and `Move to` destinations are
not rejected. Instead, the planner derives directory-creation effects from the
destination path. It must find the nearest existing ancestor, validate that the
ancestor is a real directory inside the workspace, validate that every missing
component is absent and safe to create, and collapse shared parent directories so
one patch creates each planned directory at most once.

Read/search tools may be more permissive for workspace-contained symlinks because
they do not mutate. `apply_patch` is stricter.

## File loading and snapshot phase

Before context-dependent operations, the implementation must acquire the
workspace mutation lease and then:

1. resolve every referenced path through the mutating path resolver;
2. validate workspace containment and no symlink/reparse components;
3. validate globally disjoint source and destination path identities;
4. read all `Update` and `Delete` source files;
5. check all `Add` and `Move` destinations are absent;
6. derive and validate missing parent directories for `Add` and `Move`
   destinations;
7. capture source, destination-parent, nearest-existing-ancestor, and planned
   directory absence evidence;
8. capture source metadata.

A source snapshot contains at least:

- requested path;
- canonical workspace-relative path;
- parent-directory identity;
- file identity;
- content bytes;
- encoding and BOM state;
- line-ending style;
- terminal-newline state;
- portable permission/mode bits;
- link count;
- content hash.

For each planned directory creation, the plan records at least:

- requested destination path that required the directory;
- canonical workspace-relative directory path;
- nearest existing ancestor identity;
- expected absence evidence before commit;
- planned mode bits based on host policy and workspace umask;
- creation order and rollback order.

All matching and change computation use the immutable snapshot.

## Text, encoding, and line endings

Version 1 supports UTF-8 and UTF-8 with BOM only. Update and move preserve BOM
state. Add emits UTF-8 without BOM. Other encodings fail with
`UNSUPPORTED_ENCODING`.

Binary files fail, including NUL-containing files. The implementation must not
silently decode arbitrary binary data as UTF-8 and rewrite it.

Update and move preserve uniform LF or CRLF line endings. Mixed-EOL files fail
with `MIXED_LINE_ENDINGS_UNSUPPORTED`. Add uses LF.

## Resource limits

Hosts may lower limits but must not exceed v1 hard ceilings without a protocol
revision.

| Resource                      |           Default |      Hard ceiling |
| ----------------------------- | ----------------: | ----------------: |
| Patch input                   |           256 KiB |           256 KiB |
| File actions per patch        |                50 |               200 |
| Total hunks per patch         |               500 |             2,000 |
| Path length                   | 1,024 UTF-8 bytes | 4,096 UTF-8 bytes |
| Source or resulting file size |            10 MiB |            50 MiB |
| Aggregate source snapshots    |            50 MiB |           200 MiB |
| Aggregate staged bytes        |           100 MiB |           400 MiB |

Limit failures are recoverable no-mutation rejections and must identify the
exceeded limit without echoing large content.

## Authorization and approval

The model-facing tool remains one call. Internally, every call builds an
immutable `PatchPlan` before commit. The plan contains:

- normalized actions and input order;
- canonical paths and identity evidence;
- source hashes and destination absence evidence;
- derived directory creations and ancestor evidence;
- resulting bytes and planned modes;
- bounded preview diff;
- deterministic commit schedule;
- resource usage;
- plan digest.

The host-owned policy evaluator sees the immutable plan and returns:

```text
ALLOW
REQUIRE_APPROVAL
DENY
```

Default policy is `REQUIRE_APPROVAL`. Trusted autonomous workflows may opt into
`ALLOW`. Protected paths such as `.git/**`, patch staging/journal directories,
and paths outside the pinned workspace are denied by default host policy. The
model cannot override policy.

Approval preview shows a bounded full unified diff for Add, Update, and Move
content plus explicit delete, rename, and created-directory summaries. Derived
directory creations must be visible even though the model did not author separate
directory actions. The preview is generated from the immutable plan. If the diff
exceeds the approval-preview bound, the host must not approve from a truncated
preview; it must require a narrower patch or an external full-diff viewer bound
to the same plan digest.

If approval was granted but source, destination, nearest-existing-ancestor,
planned-directory absence, parent, policy, or plan state changes before commit,
the operation fails with recoverable `STALE_PLAN`; staged artifacts are discarded
and a new model call and approval decision are required.

## Concurrency and duplicate delivery

All `apply_patch` calls for one workspace are serialized by a host-owned
exclusive mutation lease. The lease is acquired before snapshotting and held
through approval, staging, commit, rollback, or cleanup. Waiting for the lease
observes cancellation and the planning deadline. No plan snapshot is taken before
the lease is acquired.

The runtime keeps a per-agent-run ledger keyed by model `call_id` plus a digest
of normalized arguments. Exact duplicate delivery returns the recorded terminal
result without re-execution. Reusing the same `call_id` with different arguments
fails before handler execution. Only completed terminal outcomes are replayable.
After process restart, incomplete journal discovery, or an indeterminate commit
outcome, no replay occurs automatically; mutation remains recovery-gated and the
agent must inspect or wait for operator recovery before issuing a new call.

## Deadlines and cancellation

Hosts may lower deadlines but must not exceed v1 hard ceilings.

| Phase                                   |    Default | Hard ceiling |
| --------------------------------------- | ---------: | -----------: |
| Planning                                | 30 seconds |  120 seconds |
| Approval wait                           |  5 minutes |   30 minutes |
| Post-approval staging/revalidation      | 30 seconds |  120 seconds |
| Non-cancellable commit/rollback cleanup | 10 seconds |   30 seconds |

Cancellation applies during lease wait, parse, snapshot, matching, planning,
approval wait, and pre-visible-effect revalidation. Cancellation before any
visible reversible preparation effect returns a no-mutation outcome. Once a
planned parent directory has been created, cancellation requests are observed by
entering bounded cleanup instead of abandoning the operation. If cleanup removes
all plan-created directories and stage artifacts with matching identity evidence,
the result may report `mutation_guarantee = "no_mutation"`. If any directory is
retained, failed to remove, or uncertain, the result must report the directory
outcome and must not claim no mutation.

Immediately before the first visible file rename, replacement, or deletion, the
operation crosses the explicit file commit point and enters a short
non-cancellable section. After the file commit point, the implementation must
finish bounded commit or rollback and report the actual terminal state. The host
must never return while background mutation can continue.

Hitting the commit/rollback cleanup hard ceiling yields
`INDETERMINATE_COMMIT_STATE`, stops the runtime loop, and requires inspection.

## Staging and commit semantics

Preflight, planning, and authorization are side-effect-free and all-or-nothing.
Reversible preparation is journaled before visible effects, but visible directory
creation can still require cleanup or recovery. The tool does not claim
cross-file atomic commit. The documented guarantee is:

```text
side-effect-free planning
+ journaled reversible preparation
+ best-effort file commit with explicit final-state reporting
```

After approval, the implementation:

1. revalidates source identities, source hashes, nearest-existing-ancestor
   identities, parent identities, destination absence, planned-directory absence,
   policy, and plan digest;
2. durably records metadata-only recovery intent for planned directory creations,
   stage artifacts, and the approved plan digest before any derived directory is
   created;
3. creates any planned parent directories shallowest-first through pinned
   directory handles and records their resulting identities durably;
4. creates host-managed same-filesystem staging artifacts through pinned
   directory handles;
5. writes and durably flushes complete staged file contents;
6. applies required mode bits;
7. durably records the prepared commit journal;
8. revalidates again;
9. crosses the explicit file commit point;
10. executes a deterministic planner-owned commit schedule;
11. flushes affected file and parent-directory durability barriers;
12. cleans up stage, journal, and rollback-eligible created-directory artifacts
    when safe.

Staging directories are hidden, host-managed, on the same filesystem as each
affected destination parent, created/opened through pinned directory handles, and
excluded from patch targets. Staged names are not model-controlled and use strict
permissions such as `0600` or platform equivalents. Planned parent directories
are ordinary workspace directories, but their creation identities are tracked so
rollback and recovery can distinguish them from unrelated external work. The
durable journal contains metadata only: plan digest, operation state, identities,
hashes, planned directory creations, and stage/backup references. It must not
contain file contents.

Successful commit requires file-content durability barriers and parent-directory
durability barriers where supported, including barriers for newly created parent
directories and their ancestors. If required durability primitives are
unavailable, the host fails the filesystem capability probe. If durability fails
during commit, the operation enters rollback or reports the final state.

Rollback must never overwrite or remove an independently changed path. Directory
rollback removes only directories created by the current plan, deepest-first, and
only when they are still empty and their identity matches the journaled creation
evidence. If a created directory now contains external work, rollback must leave
it in place and report it as retained. If directory identity or removal status
cannot be proven, rollback must report it as uncertain and treat the overall
mutation guarantee as partial or uncertain. Terminal states must distinguish at
least:

- `COMMITTED`;
- `REJECTED`;
- `COMMIT_FAILED_ROLLED_BACK`;
- `PARTIAL_COMMIT`;
- `ROLLBACK_FAILED`;
- `INDETERMINATE_COMMIT_STATE`.

Every non-committed post-visible-effect state must include per-path and
per-directory evidence sufficient for a user or recovery routine to understand
what changed.

Created-directory outcomes are reported separately from file outcomes so users
can distinguish retained empty or externally populated directories from file edit
failures.

## Startup recovery

When Fabrica starts and finds an incomplete patch journal, `apply_patch` must not
be exposed for that workspace until recovery inspects the durable journal,
planned-directory records, and stage/backup artifacts. Recovery may finish
rollback automatically only when identity and hash preconditions prove it cannot
overwrite or remove later external work. Created directories may be removed during
recovery only when they are still empty and match the journaled identity;
otherwise they are retained and reported. If the journal proves that all visible
preparation effects were removed, recovery may mark the interrupted call as
no-mutation. Otherwise the workspace is marked `RECOVERY_REQUIRED`, mutation
remains blocked, and explicit operator resolution is required. Recovery must not
silently resume forward commit or delete evidence.

## Filesystem and platform scope

Version 1 supports capability-probed macOS and Linux POSIX filesystems only. The
filesystem adapter must verify required primitives before exposing mutation:

- workspace-root and directory-handle-relative traversal;
- no-follow and no-replace operations;
- pinned file and directory identities;
- link-count inspection;
- mode-bit inspection and application;
- file and parent-directory durability barriers;
- regular-file and special-file classification.

If these guarantees are unavailable for the platform or workspace filesystem, the
tool fails before mutation with `UNSUPPORTED_FILESYSTEM_GUARANTEE`. Windows and
filesystems that fail the probe are outside v1.

## Result contract

The patch engine returns typed feature DTOs. The current model-facing registered
tool adapter serializes those DTOs as compact canonical JSON in the runtime text
channel. Stable status and error fields must be preserved before optional detail
when output is bounded.

Every result includes a mutation guarantee. `no_mutation` is valid only when no
visible effect occurred or all visible reversible preparation effects were proven
removed. `reversible_effects_retained` means no file action crossed the file
commit point, but one or more plan-created directories remain and are reported
with identity evidence. `partial_or_uncertain_mutation` covers any crossed file
commit point, failed rollback, uncertain directory cleanup, or indeterminate
state. Results with retained or uncertain visible effects are fatal to the runtime
loop unless a future spec explicitly defines a safe continuation status.

Success example:

```json
{
  "status": "committed",
  "success": true,
  "mutation_guarantee": "committed",
  "plan_digest": "sha256:...",
  "changes": [
    {
      "index": 0,
      "operation": "update",
      "path": "src/example.py",
      "hunks": 2,
      "match_quality": "exact"
    },
    {
      "index": 1,
      "operation": "add",
      "path": "tests/test_example.py"
    }
  ],
  "created_directories": [
    {
      "path": "tests",
      "reason": "parent_for_add",
      "final_state": "created"
    }
  ],
  "warnings": []
}
```

Recoverable rejection example:

```json
{
  "status": "rejected",
  "success": false,
  "mutation_guarantee": "no_mutation",
  "error": {
    "code": "HUNK_CONTEXT_NOT_FOUND",
    "phase": "matching",
    "retryable": true,
    "path": "src/example.py",
    "hunk": 2,
    "anchor": null,
    "old_sequence_digest": "sha256:...",
    "candidate_count": 0,
    "excerpt": "...bounded sanitized excerpt..."
  }
}
```

Cancelled preparation with a retained directory example:

```json
{
  "status": "rejected",
  "success": false,
  "mutation_guarantee": "reversible_effects_retained",
  "error": {
    "code": "CREATED_DIRECTORY_RETAINED",
    "phase": "cleanup",
    "retryable": false
  },
  "directory_outcomes": [
    {
      "path": "src/generated",
      "planned_effect": "create_directory",
      "final_state": "retained_external_content"
    }
  ]
}
```

Post-commit failure example:

```json
{
  "status": "partial_commit",
  "success": false,
  "mutation_guarantee": "partial_or_uncertain_mutation",
  "plan_digest": "sha256:...",
  "error": {
    "code": "ROLLBACK_FAILED",
    "phase": "rollback",
    "retryable": false
  },
  "directory_outcomes": [
    {
      "path": "src/generated",
      "planned_effect": "create_directory",
      "final_state": "retained_external_content"
    }
  ],
  "path_outcomes": [
    {
      "path": "src/a.py",
      "planned_operation": "update",
      "final_state": "committed"
    },
    {
      "path": "src/b.py",
      "planned_operation": "update",
      "final_state": "unknown"
    }
  ]
}
```

Failed-hunk diagnostics must not echo arbitrary source blocks. They may include
path, one-based hunk index, anchor, old-sequence digest, candidate count, and at
most a sanitized three-line or 500-character excerpt when host policy permits.

## Error codes

The implementation must maintain an exhaustive error table. Each code must define
phase, retryability, mutation guarantee, required metadata, and runtime mapping.

Required v1 codes include:

- `INVALID_PATCH`;
- `INCOMPLETE_SENTINELS`;
- `UNKNOWN_ACTION`;
- `INVALID_HUNK`;
- `NO_OP_ACTION`;
- `DUPLICATE_ACTION`;
- `PATH_ALIAS_COLLISION`;
- `SOURCE_NOT_FOUND`;
- `ADD_TARGET_EXISTS`;
- `MOVE_TARGET_EXISTS`;
- `DESTINATION_COLLISION`;
- `PATH_OUTSIDE_WORKSPACE`;
- `PROTECTED_PATH_DENIED`;
- `SYMLINK_PATH_UNSUPPORTED`;
- `NOT_A_REGULAR_FILE`;
- `PARENT_PATH_NOT_DIRECTORY`;
- `SPECIAL_FILE_UNSUPPORTED`;
- `MULTIPLE_HARD_LINKS_UNSUPPORTED`;
- `DIRECTORY_CREATION_UNSAFE`;
- `CREATED_DIRECTORY_RETAINED`;
- `CREATED_DIRECTORY_REMOVAL_UNCERTAIN`;
- `CROSS_DEVICE_MOVE_UNSUPPORTED`;
- `UNSUPPORTED_FILESYSTEM_GUARANTEE`;
- `BINARY_FILE`;
- `UNSUPPORTED_ENCODING`;
- `MIXED_LINE_ENDINGS_UNSUPPORTED`;
- `UNSUPPORTED_METADATA`;
- `ANCHOR_NOT_FOUND`;
- `AMBIGUOUS_ANCHOR`;
- `HUNK_CONTEXT_NOT_FOUND`;
- `AMBIGUOUS_HUNK`;
- `HUNK_OVERLAP`;
- `HUNK_ORDER_CONFLICT`;
- `EOF_ASSERTION_FAILED`;
- `LIMIT_EXCEEDED`;
- `APPROVAL_DENIED`;
- `APPROVAL_TIMEOUT`;
- `STALE_PLAN`;
- `IO_ERROR`;
- `PLANNING_TIMEOUT`;
- `STAGING_TIMEOUT`;
- `COMMIT_FAILED_ROLLED_BACK`;
- `PARTIAL_COMMIT`;
- `ROLLBACK_FAILED`;
- `INDETERMINATE_COMMIT_STATE`;
- `RECOVERY_REQUIRED`.

Recoverable no-mutation rejections map to the generic runtime status
`REJECTED`. Successful commits map to `SUCCESS`. Internal adapter failures map to
`TOOL_FAILURE` or `ADAPTER_ERROR`. Retained reversible effects, indeterminate
cleanup, or partial mutation outcomes are fatal to the runtime loop and must not
be treated as recoverable model mistakes.

## Runtime integration

Implementing `apply_patch` requires upgrading the generic registered-tool
boundary from a synchronous `Callable[..., str]` style to an async,
cancellation-aware contract. The handler context must carry cancellation,
deadlines, call identity, and host policy hooks. Existing synchronous
deterministic tools may be adapted through thin wrappers.

The `workspace_editing` feature owns patch DTOs, parser, matcher, planner,
application ports, and use cases. Filesystem mutation lives behind outbound
ports/adapters in that slice. `agent_runtime` adapts the application port as a
model-callable tool. Bootstrap wires workspace roots, capability probes, policy,
approval UI, leases, and recovery.

## Architecture and project structure

Likely implementation ownership:

- Spec: `docs/specs/tools-apply-patch-tool-spec.md`.
- Patch capability source: `src/fabrica/features/workspace_editing/`.
- Application DTOs: `src/fabrica/features/workspace_editing/application/dtos/`.
- Application ports: `src/fabrica/features/workspace_editing/application/ports/`.
- Use cases: `src/fabrica/features/workspace_editing/application/use_cases/`.
- Filesystem adapter: `src/fabrica/features/workspace_editing/adapters/outbound/`.
- Runtime registered-tool adapter: an adapter or composition component that
  connects `workspace_editing` to `agent_runtime` without leaking filesystem
  details into the runtime core.
- Unit tests: mirrored under `tests/unit/features/workspace_editing/`.
- Integration tests: mirrored under `tests/integration/features/workspace_editing/`
  for real filesystem behavior, capability probing, durability, staging,
  symlink rejection, and recovery.

Implementation must preserve hexagonal boundaries: domain and application code
must not perform filesystem I/O directly, and adapter-specific filesystem or UI
approval details must not leak into stable application ports or DTOs.

## Testing Strategy

Future acceptance tests must cover at least these scenarios.

### Basic operations

- Add a new non-empty file.
- Add a zero-byte file.
- Update one line.
- Delete one file.
- Pure move with zero hunks.
- Move and modify simultaneously.
- Apply a multi-file patch.
- Apply multiple hunks in one file.

### Grammar and matching

- Missing Begin or End sentinel fails.
- Unprefixed context line fails.
- Protocol-looking file content is accepted when prefixed.
- Exact context succeeds.
- Trailing-whitespace tolerance succeeds and reports match quality.
- Unchanged context whitespace is preserved from source.
- Context not found fails with no mutation.
- Ambiguous repeated context fails.
- Duplicate anchor fails as `AMBIGUOUS_ANCHOR`.
- Missing anchor fails as `ANCHOR_NOT_FOUND`.
- `@@ before <anchor>` and `@@ after <anchor>` insertion-only hunks work.
- Plain insertion-only `@@` fails.
- Overlapping and out-of-order hunks fail.
- EOF assertion succeeds only on the final hunk at EOF.
- EOF assertion fails when the resulting span does not terminate at EOF.
- Terminal-newline state is preserved or explicitly changed.

### Validation and paths

- Updating a missing file fails.
- Deleting a missing file fails.
- Adding an existing file fails.
- Moving to an existing destination fails.
- Duplicate source actions fail.
- Destination collisions fail.
- Move chains and swaps fail.
- `../outside.txt`, absolute paths, and paths outside the workspace fail.
- Every symlink/reparse path component fails, including contained symlinks.
- Directory, FIFO, socket, device, and other special files fail.
- Multiple hard links fail.
- Nested `Add File` creates missing parent directories.
- Nested `Move to` creates missing destination parent directories.
- Shared missing parent directories for multiple Add/Move destinations are
  created once.
- Existing parent path components that are regular files fail with
  `PARENT_PATH_NOT_DIRECTORY`.
- Stale planned-directory absence after approval fails with `STALE_PLAN`.
- Case/normalization aliases fail.
- Cross-device moves fail.
- Protected paths such as `.git/**` are denied.

### Preservation

- LF file remains LF.
- CRLF file remains CRLF.
- Mixed-EOL file fails.
- UTF-8 BOM is preserved on update and move.
- Add emits UTF-8 without BOM.
- Executable mode bit is preserved on update and move.
- Add mode uses base `0666` filtered by configured workspace umask.
- Unsupported security-relevant metadata fails when the adapter cannot preserve it.

### Authorization and runtime behavior

- Default registered tool requires approval.
- Trusted policy can allow without prompt.
- Denied approval returns recoverable rejection.
- Truncated approval diff cannot be approved.
- Stale plan after approval fails and requires a new call.
- Expected hunk/path validation rejection maps to runtime `REJECTED` and the loop
  can continue.
- Duplicate tool call with same `call_id` and argument digest replays recorded
  result without re-execution.
- Duplicate `call_id` with different arguments fails.

### Commit, rollback, recovery, and deadlines

- Valid update A plus invalid update B leaves both unchanged.
- Source modified after planning fails with `STALE_PLAN`.
- Commit uses deterministic schedule while reporting input order.
- Commit creates planned parent directories shallowest-first before writing Add
  and Move destination contents.
- Commit failure with successful rollback reports `COMMIT_FAILED_ROLLED_BACK`.
- Rollback removes created parent directories deepest-first only when still empty
  and unchanged.
- Rollback retains and reports created directories that contain external work.
- Rollback failure reports per-path outcomes.
- Indeterminate cleanup timeout reports `INDETERMINATE_COMMIT_STATE` and stops the
  runtime loop.
- Incomplete journal on startup blocks mutation until recovery.
- Recovery rolls back only when identity/hash preconditions prove it safe.
- Cancellation after derived directory creation either proves cleanup or reports
  retained, failed, or uncertain directory outcomes.
- Concurrent `apply_patch` calls are serialized per workspace.
- Planning, approval, staging, and commit/rollback deadlines are enforced.

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Format | `uv run ruff format --check .` | Required for implementation changes |
| Lint | `uv run ruff check .` | Required for implementation changes |
| Type check | `uv run ty check src tests` | Required for implementation changes |
| Tests | `uv run pytest` | Required for implementation changes |
| Documentation | Review this specification and its internal references for accuracy and consistency. | Required |
| Migration or compatibility | Not applicable unless this specification explicitly introduces a migration. | Not applicable by default |
| Manual acceptance | Obtain documented human acceptance before implementation planning when the status is Draft. | Required for drafts |

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Future implementation should start with focused parser, matcher, path validation,
planner, authorization, result-contract, and runtime-status tests before adding a
real filesystem committer. Filesystem integration tests should follow once the
application contracts are stable.

## Execution Boundaries

- Always prefer context-based, minimal, reviewable patches over shell text
  rewrites.
- Always validate and authorize the full immutable plan before committing.
- Always reject unsupported filesystem, path, metadata, or matching cases before
  mutation.
- Always serialize `apply_patch` per workspace.
- Always bind approval to exact resulting bytes and plan digest.
- Always include derived parent-directory creations in planning, approval,
  journaling, result reporting, rollback, and recovery.
- Always durably record recovery intent before a derived parent directory becomes
  visible.
- Always treat filesystem commit as adapter-owned behavior.
- Never allow Add or Move to overwrite existing files.
- Never expose separate model-facing filesystem mutation tools that overlap with
  `apply_patch` in v1.
- Never create, remove, or retain directories as an unreported side effect.
- Never choose the first ambiguous hunk or anchor.
- Never use fuzzy, semantic, or indentation-normalized matching in v1.
- Never mutate through symlinks, reparse points, special files, or multiple hard
  links in v1.
- Never claim cross-file atomicity.
- Never return while background mutation can continue.
- Never report no mutation while plan-created directories are retained, failed to
  remove, or uncertain.
- Never collapse partial, rollback-failed, or indeterminate outcomes into generic
  `IO_ERROR`.

## Success Criteria

- The spec defines `apply_patch` as the single preferred model-facing filesystem
  mutation primitive for coding-agent workflows, while allowing operation-specific
  internal implementation components.
- The public model-facing interface is the canonical `{ "input": string }` schema.
- The grammar covers Add, Update, Delete, Move, anchors, insertion-only placement,
  EOF assertions, terminal-newline state, multi-file patches, and multiple hunks.
- The hunk model preserves line order and the matching algorithm is deterministic.
- The path model rejects symlinks, aliases, special files, non-directory parents,
  missing source parents, multiple hard links, protected paths, cross-device
  moves, and unsupported filesystems before mutation.
- The directory model automatically creates missing Add/Move destination parents
  as derived planned effects with approval visibility, journal evidence,
  rollback, recovery, and result reporting.
- The lifecycle model distinguishes side-effect-free planning, reversible
  preparation, the explicit file commit point, and startup recovery ownership.
- The authorization model binds approval to an immutable exact-byte plan.
- The runtime model includes async cancellation-aware handlers, recoverable
  `REJECTED` outcomes, duplicate-delivery protection, and fatal indeterminate
  mutation outcomes.
- The filesystem model includes mutation leases, snapshotting, strong POSIX
  capability probes, durable staging, explicit commit point, rollback journal,
  startup recovery, stale-plan detection, EOL/BOM/mode preservation, and bounded
  deadlines.
- The result contract includes stable statuses, error codes, mutation guarantees,
  retryability, and per-path evidence for post-commit failures.
- Future acceptance tests are explicit enough to drive implementation.

## Open Questions

None for v1. New behavior such as Windows support, fuzzy matching, non-UTF-8
encodings, symlink mutation, standalone empty-directory operations, richer
metadata preservation, executable-mode syntax, cross-device moves, or public
two-step preview/commit tokens requires a new spec revision.

## Scope

### In Scope

- The bounded, journaled workspace patch-mutation tool contract.

### Out of Scope

The detailed exclusions already recorded below remain authoritative.

## Acceptance and Planning Gate

This accepted specification is ready to guide implementation planning. Material
changes require an updated specification and renewed maintainer acceptance.

## Conventions and Constraints

Follow the project architecture, typing, logging, secret-safety, and validation conventions recorded in `.clinerules/`.

## Assumptions

- The existing detailed requirements remain valid unless explicitly superseded by an accepted revision.

## Desired Behavior

The detailed behavioral contract in this specification defines the required observable outcomes and failure behavior.

## Project Structure

- Specification: This file under `docs/specs/`.
- Source and test ownership: The detailed architecture section in this specification remains authoritative.
- Documentation ownership: `docs/specs/` and the relevant documentation indexes.
