# Spec: Apply Patch Tool

## Objective

Define the model-facing and host-facing specification for an `apply_patch`
filesystem mutation tool.

The tool is for autonomous coding agents that need a single preferred primitive
for creating, modifying, deleting, and moving text files in a workspace. It must
favor contextual, reviewable patches over line-number edits, shell text
rewrites, or whole-file replacement.

The design goal is a reusable patch engine that can support CLI execution, IDE
diff preview, approval workflows, autonomous mode, and tests without changing the
patch grammar shown to the model.

## Current context

- Project: `fabrica`, a Python 3.13 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime.md`.
- Developer workflow and local tool safety concerns are owned by related specs
  such as `docs/specs/git-workflow-tools.md`.
- This spec defines the desired `apply_patch` tool contract only. It does not
  implement the tool.
- The requested design keeps selected Cline patch semantics while tightening
  matching, workspace containment, target protection, and commit guarantees.

## Assumptions

- The primary caller is a model-driven coding agent operating inside a configured
  workspace root.
- The default implementation target will be Python and should follow Fabrica's
  feature-slice and hexagonal architecture conventions when implementation work
  begins.
- Version 1 supports UTF-8 text files and rejects binary or unsupported-encoding
  files.
- The host can provide a canonical workspace root and can expose separate preview
  and commit phases.
- Documentation-only changes should be reviewed for clarity and consistency;
  implementation changes will require tests and the project quality gate.

## Desired behavior

`apply_patch` must allow a model to:

- create text files;
- modify existing text files with context-based hunks;
- delete files;
- move or rename files, optionally while modifying their contents;
- change multiple files in one tool call.

The tool must be designed around contextual patches rather than line numbers or
whole-file replacement. It must prefer minimal mutations, deterministic failure,
workspace containment, reviewable change computation, and compatibility with
GPT/Codex-style coding models.

The implementation must separate:

- parsing;
- validation;
- hunk matching;
- change computation;
- preview;
- filesystem commit.

## Tool interface

Tool name:

```text
apply_patch
```

Canonical model-facing JSON schema:

```json
{
  "type": "object",
  "properties": {
    "input": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": ["input"],
  "additionalProperties": false
}
```

The public tool schema should remain `{ "input": string }`. An implementation may
internally tolerate a raw string input for provider compatibility.

Recommended default timeout:

```text
30 seconds
```

The operation must not be automatically retried. Filesystem edits are stateful,
and automatic retry after an indeterminate failure could duplicate or incorrectly
reapply an operation.

## Model-facing description

The tool description should teach the model the patch syntax directly rather than
asking it to invoke a shell command:

```text
Apply context-based patches to files in the workspace.

Pass the patch directly in `input`.

Supported operations:
- *** Add File: <path>
- *** Update File: <path>
- *** Delete File: <path>
- *** Move to: <new-path> after an Update File header

Use context lines together with - deleted lines and + inserted lines.
Use @@ or @@ <anchor> to separate or disambiguate hunks.
Do not use line numbers.

The entire patch is validated before changes are committed.
If any hunk cannot be matched safely, the patch fails and no intended
changes are applied.

Prefer small, focused patches over large whole-file replacements.
```

The model should be encouraged to use raw patch bodies, not shell wrappers such
as `apply_patch <<"EOF"`.

## Patch protocol

Canonical patch form:

```text
*** Begin Patch
<action>
<action>
...
*** End Patch
```

A patch contains one or more file actions.

### Add file

Syntax:

```diff
*** Add File: src/example.py
+def example():
+    return 42
```

Every content line in an `Add File` block must begin with `+`. The leading `+` is
syntax and is not written to the resulting file. `Add File` means create a new
file only; it must never overwrite an existing file.

### Delete file

Syntax:

```diff
*** Delete File: src/obsolete.py
```

The target must exist. Deletion does not require file contents in the patch.

### Update file

Syntax:

```diff
*** Update File: src/example.py
@@
 def example():
-    return 41
+    return 42
```

Update hunks contain context lines, deleted lines, and inserted lines. Canonical
syntax should use one leading space for context lines. For model robustness, the
parser may also accept unprefixed lines as context, but newly generated patches
should use the canonical leading-space form.

### Section anchors

A hunk may begin with either:

```text
@@
```

or:

```text
@@ <anchor>
```

Example:

```diff
*** Update File: src/service.py
@@ class UserService:
     def load(self):
-        return old_loader()
+        return new_loader()
```

`@@ <anchor>` is not a line number. It narrows the subsequent search to a region
after a matching source line.

If an explicit anchor is supplied and cannot be found, the hunk must fail. The
implementation must not silently fall back to searching the whole remaining file.

### End-of-file assertion

Syntax:

```text
*** End of File
```

The marker may appear after a hunk:

```diff
*** Update File: config.txt
@@
 old-last-line
+new-last-line
*** End of File
```

Semantics: the matched hunk must terminate at EOF. If it does not, the patch must
fail with an EOF assertion error. EOF is a real assertion, not merely a search
preference.

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
header.

Move semantics are:

```text
read source
→ apply update hunks
→ write resulting contents to destination
→ remove source
```

The destination must remain inside the workspace, must not already exist, must
not collide with another Add or Move destination in the same patch, and must not
be the target of another incompatible operation. No implicit overwrite is
permitted.

### One action per source path

A patch must not contain multiple top-level actions for the same source path.
Multiple hunks must appear inside a single `Update File` action.

Invalid:

```text
*** Update File: foo.py
...

*** Update File: foo.py
...
```

## Sentinel compatibility

Canonical emitted patches should contain both sentinels:

```text
*** Begin Patch
...
*** End Patch
```

For compatibility, the parser may accept a patch body without sentinels and
internally wrap it. If either Begin or End is present but the other is missing,
the parser must fail with `INCOMPLETE_SENTINELS`.

Legacy shell wrappers such as the following are not part of the canonical
protocol:

```text
%%bash
apply_patch <<"EOF"
...
EOF
```

A compatibility adapter may strip such wrappers if supporting older prompts, but
the model-facing protocol should prefer the raw patch body.

## Parsing model

The executor must parse the patch into an intermediate representation before any
filesystem mutation occurs.

Suggested representation:

```text
Patch
  actions: list[FileAction]

FileAction
  type: ADD | UPDATE | DELETE
  source_path: Path
  destination_path: Path | null
  new_file_content: str | null
  hunks: list[Hunk]

Hunk
  anchor: str | null
  old_context: list[str]
  deletions: list[str]
  insertions: list[str]
  eof_required: bool
```

Parsing must be side-effect free.

## Matching strategy

The default matcher must be conservative and deterministic.

### Pass 1: exact match

Match the complete old hunk context exactly.

### Pass 2: trailing-whitespace tolerance

If exact matching fails, the matcher may accept a candidate where:

```text
rstrip(source_line) == rstrip(patch_line)
```

The result must record `match_quality = trailing_whitespace`.

### Optional indentation tolerance

A compatibility mode may permit leading and trailing whitespace normalization. It
must not be enabled by default.

### No default approximate semantic matching

The default matcher must not apply a patch merely because a low-threshold fuzzy
or semantic similarity check passes.

If approximate matching is introduced later, it must be explicitly configurable,
require a high threshold, choose the unique best candidate, fail on ambiguity, and
report the similarity score. The recommended minimum threshold is `0.90`.

## Context ambiguity

A hunk should identify its destination sufficiently precisely. If multiple
candidate regions match equally and the patch does not provide enough information
to distinguish them, the matcher must fail with `AMBIGUOUS_HUNK`.

The agent can then reread the file, provide more context or an `@@ anchor`, and
retry. This is preferable to silently modifying the first similar block.

## File loading and snapshot phase

Before parsing context-dependent operations, the implementation must:

1. resolve every referenced path;
2. validate workspace containment;
3. read all `Update` and `Delete` source files;
4. check all `Add` destinations;
5. check all `Move` destinations;
6. capture source metadata.

A source snapshot should contain at least:

- path;
- content bytes;
- encoding;
- line-ending style;
- file mode or permissions;
- content hash.

All matching and change computation must use the snapshot.

## Preflight validation

The implementation must validate the entire patch before any write occurs.

The following conditions must fail preflight:

- `Add File` target already exists;
- `Update File` source is missing;
- `Delete File` source is missing;
- `Move to` destination already exists;
- duplicate source operation;
- duplicate destination;
- destination/source collision;
- path escapes workspace;
- malformed patch;
- unmatched hunk;
- ambiguous hunk;
- invalid EOF assertion;
- binary file;
- unsupported encoding.

If preflight fails, intended filesystem mutations must be zero.

## Workspace security

All paths must be resolved relative to a configured workspace root.

Defaults:

- absolute paths are rejected;
- `../` traversal is rejected;
- symlink escape is rejected.

Validation should use canonical filesystem paths, not merely lexical path
normalization. For example, if `workspace/link -> /etc`, then this patch must be
rejected:

```text
*** Update File: link/passwd
```

An autonomous coding tool must not inherit behavior that allows absolute paths as
long as they are syntactically valid.

## Existing-file protection

`Add File` means create new file, not create-or-overwrite. If the target exists,
preflight must fail with `ADD_TARGET_EXISTS`.

The same rule applies to `Move to`: if the destination exists, preflight must fail
with `MOVE_TARGET_EXISTS`.

These checks must query the filesystem during preflight. They must not depend
solely on an in-memory map of files loaded for other operations.

## Line endings

Matching may internally normalize line endings. Writing must preserve the
original file's convention, including LF and CRLF. Newly added files default to LF
unless workspace configuration specifies otherwise.

The implementation must avoid unrelated whole-file EOL churn. Updating a CRLF
file must not rewrite it as LF.

## Encoding and binary files

Version 1 should support UTF-8 text files. UTF-8 BOM preservation is optional but
should be explicit if supported.

The implementation must reject files that appear binary, including NUL-containing
data. It must not silently decode arbitrary binary data as UTF-8 and rewrite it.

## File metadata

For updates, permissions must be preserved. For moves, source permissions should
be preserved. For adds, normal workspace or default creation permissions apply.

Where practical, moves should preserve executable bits and other basic mode
metadata.

## Change computation

After matching all hunks, the implementation must compute an in-memory change set
before writing.

Suggested representation:

```text
ChangeSet
  ADD:
    path
    new_content

  UPDATE:
    path
    old_content
    new_content

  DELETE:
    path
    old_content

  MOVE:
    old_path
    new_path
    old_content
    new_content
```

The change set should be reusable by CLI execution, IDE diff preview, approval
UI, auditing, and tests.

## Concurrent modification protection

Immediately before commit, every snapshotted source must still have the same
content hash. If a source changed after preflight, the implementation must fail
with `STALE_SOURCE` and ask the agent to reread and retry.

Add and Move destinations must also remain absent immediately before commit.

## Commit semantics

Semantic validation must be all-or-nothing. The implementation should also make
filesystem commit as transactional as practical.

Recommended commit approach:

1. create temporary files in destination directories;
2. write complete new contents;
3. flush and close;
4. preserve required permissions;
5. verify all staging succeeded;
6. rename staged files into place;
7. perform deletions;
8. clean temporary files.

If commit fails midway, the implementation should attempt rollback using the
preflight snapshot. True cross-file atomicity is generally unavailable on ordinary
filesystems, so the documented guarantee is:

```text
fully atomic preflight + best-effort transactional commit
```

## Result contract

The tool should return structured results rather than only human-readable prose.

Success example:

```json
{
  "success": true,
  "changes": [
    {
      "operation": "update",
      "path": "src/example.py",
      "hunks": 2,
      "match_quality": "exact"
    },
    {
      "operation": "add",
      "path": "tests/test_example.py"
    }
  ],
  "warnings": []
}
```

Failure example:

```json
{
  "success": false,
  "error": {
    "code": "HUNK_CONTEXT_NOT_FOUND",
    "path": "src/example.py",
    "hunk": 2,
    "message": "Hunk context does not match current file content.",
    "context": "..."
  }
}
```

Useful error codes include:

- `INVALID_PATCH`;
- `INCOMPLETE_SENTINELS`;
- `UNKNOWN_ACTION`;
- `DUPLICATE_ACTION`;
- `SOURCE_NOT_FOUND`;
- `ADD_TARGET_EXISTS`;
- `MOVE_TARGET_EXISTS`;
- `PATH_OUTSIDE_WORKSPACE`;
- `BINARY_FILE`;
- `HUNK_CONTEXT_NOT_FOUND`;
- `AMBIGUOUS_HUNK`;
- `EOF_ASSERTION_FAILED`;
- `STALE_SOURCE`;
- `IO_ERROR`;
- `TIMEOUT`.

## Recommended agent workflow

System prompts should encourage this workflow:

```text
read_files / search_codebase
        ↓
understand current source
        ↓
apply_patch
        ↓
read changed area if necessary
        ↓
run_commands: formatter / tests / type checker
        ↓
fix with another apply_patch if needed
```

System prompts should not encourage `sed`, `perl -pi`, Python one-liners that
modify files, `cat > file`, or shell heredocs when `apply_patch` can represent
the same mutation.

## Architecture and project structure

Implementation should consist of five independent components:

```text
PatchParser
    ↓
PatchValidator
    ↓
HunkMatcher
    ↓
ChangePlanner
    ↓
FilesystemCommitter
```

Host-facing orchestration API:

```text
parse_patch(text)
    -> Patch

compute_patch_changes(patch, workspace)
    -> ChangeSet

apply_patch_changes(change_set, workspace)
    -> ApplyResult
```

The LLM tool itself should be a thin adapter:

```text
apply_patch(input)
    = parse
    + compute/preflight
    + commit
    + structured result
```

The patch grammar is the model protocol; filesystem mutation is an
implementation detail.

Likely future implementation ownership:

- Spec: `docs/specs/apply-patch-tool.md`.
- Runtime tool contracts and DTOs: under
  `src/fabrica/features/agent_runtime/application/` if exposed as a model-callable
  runtime tool.
- Patch engine source: under an owning feature slice or a clearly documented
  shared infrastructure package if multiple slices need the same engine.
- Filesystem adapter and commit implementation: adapter or infrastructure code,
  not domain or application core.
- Unit tests: mirrored under `tests/unit/` for parser, validator, matcher, change
  planner, and committer boundaries.
- Integration tests: under `tests/integration/` for real filesystem behavior,
  symlink containment, metadata preservation, and concurrency checks.

Implementation must preserve hexagonal boundaries: domain and application code
must not perform filesystem I/O directly, and adapter-specific filesystem details
must not leak into stable application ports or DTOs.

## Differences from current Cline behavior

Keep these Cline-compatible concepts:

- Begin/End patch grammar;
- Add, Update, and Delete actions;
- `Move to` after an Update header;
- context-based hunks;
- `@@` anchors;
- `*** End of File` marker;
- multiple files per call;
- multiple hunks per update;
- precompute before write;
- fail if any hunk is skipped;
- no automatic tool retry;
- previewable change-set architecture.

Change these behaviors for this implementation:

- reject absolute paths outside the workspace;
- do not use low-threshold fuzzy matching;
- do not silently ignore unresolved `@@` anchors;
- do not treat EOF as a fallback preference;
- do not let Add overwrite existing files;
- do not let Move overwrite existing files;
- do not rewrite CRLF files as LF;
- do not allow unresolved destination collisions.

Add these requirements beyond current Cline behavior:

- ambiguity detection;
- destination preflight;
- symlink-safe workspace containment;
- concurrent-modification detection;
- EOL preservation;
- file-mode preservation;
- structured result and error codes;
- staged transactional commit.

## Testing strategy

Required future acceptance tests include the following scenarios.

### Basic operations

- Add a new file.
- Update one line.
- Delete one file.
- Move a file.
- Move and modify simultaneously.
- Apply a multi-file patch.
- Apply multiple hunks in one file.

### Validation

- Updating a missing file fails.
- Deleting a missing file fails.
- Adding an existing file fails.
- Moving to an existing destination fails.
- Duplicate source actions fail.
- Destination collisions within the same patch fail.

### Hunk matching

- Exact context succeeds.
- Trailing-whitespace tolerance succeeds and reports match quality.
- Context not found fails the entire patch.
- Ambiguous repeated context fails.
- `@@ anchor` resolves repeated blocks.
- Missing explicit anchor fails.
- EOF assertion succeeds when the hunk terminates at EOF.
- EOF assertion fails when the hunk does not terminate at EOF.

### Atomicity

A patch containing a valid update A and invalid update B must leave both A and B
unchanged.

### Security

Reject:

- `../outside.txt`;
- `../../etc/passwd`;
- absolute paths;
- symlink escape.

### Preservation

- CRLF file remains CRLF.
- UTF-8 BOM is preserved if supported.
- Executable permission remains executable after update and move.

### Concurrency

Modifying a source between preflight and commit must fail with `STALE_SOURCE` and
must not commit any intended patch changes.

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Future implementation should start with focused parser, validator, matcher, and
filesystem tests before adding a model-callable runtime adapter.

## Boundaries

- Always prefer context-based, minimal, reviewable patches over shell text
  rewrites.
- Always validate the full patch before committing any intended filesystem
  mutations.
- Always keep workspace containment, existing-target checks, and stale-source
  checks in preflight or immediately-before-commit validation.
- Always reject ambiguous hunks rather than choosing the first matching block.
- Always treat the filesystem commit as an adapter concern, not domain logic.
- Ask before enabling fuzzy matching, indentation normalization by default,
  non-UTF-8 encodings, absolute path support, or overwrite semantics.
- Ask before exposing the tool as a mutating model-callable capability in a
  runtime composition.
- Never mutate files while parsing or matching.
- Never allow Add or Move to overwrite existing files.
- Never silently apply a patch when an explicit anchor or EOF assertion fails.
- Never use approximate semantic matching by default.
- Never allow paths to escape the configured workspace through absolute paths,
  parent traversal, or symlinks.

## Success criteria

- The spec defines `apply_patch` as the single preferred filesystem mutation
  primitive for coding-agent workflows.
- The public tool interface is the canonical `{ "input": string }` schema with a
  30-second timeout and no automatic retries.
- The patch grammar covers Add, Update, Delete, Move, anchors, EOF assertions,
  sentinels, multi-file patches, and multiple hunks.
- The matching strategy is deterministic, conservative, and rejects ambiguity.
- The filesystem model includes snapshotting, preflight validation, workspace
  containment, existing-file protection, line-ending and metadata preservation,
  stale-source detection, and best-effort transactional commit.
- The result contract includes structured success and failure payloads with stable
  error codes.
- The architecture separates parser, validator, matcher, change planner,
  filesystem committer, and thin model-tool adapter responsibilities.
- Future acceptance tests are explicit enough to drive implementation.

## Open questions

- Should Version 1 support UTF-8 BOM preservation, or should BOM files be rejected
  until explicit support is implemented?
- Should indentation normalization exist as a compatibility mode, and if so, who
  is allowed to enable it?
- Should approximate matching be omitted entirely from Version 1 rather than
  implemented behind configuration?
- What workspace configuration should control default line endings for newly added
  files?
- What exact rollback guarantees are feasible across the target filesystems used
  by Fabrica users?
- Should the patch engine live inside the `agent_runtime` slice, a dedicated
  feature slice, or a shared infrastructure package once more than one workflow
  needs it?
