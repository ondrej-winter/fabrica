# Spec: Search Codebase Tool

## Objective

Define the model-facing and host-facing specification for a read-only
`search_codebase` textual discovery tool.

The tool is for autonomous coding agents that need one preferred primitive for
regular-expression search across workspace file contents before reading full
files. It must provide deterministic, bounded, structured search results with
stable file, line, and column references.

The design goal is a safe, provider-neutral search primitive analogous to
`ripgrep`, but with a stable agent-facing contract that does not expose backend
implementation quirks.

## Current context

- Project: `fabrica`, a Python 3.13 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime.md`.
- Filesystem reading is owned by `docs/specs/read-files-tool.md`.
- Filesystem mutation is owned by `docs/specs/apply-patch-tool.md`.
- This spec defines the desired `search_codebase` tool contract only. It does not
  implement the tool.
- `search_codebase` is the discovery counterpart to `read_files`: the model
  searches for relevant locations, reads the files that matter, reasons from
  source context, then applies patches or runs verification.

## Assumptions

- The primary caller is a model-driven coding agent operating inside a configured
  workspace root.
- Canonical model-facing paths are workspace-relative, not absolute.
- The host can provide a canonical workspace root, cancellation signals, timeout
  configuration, retry policy, and optional host-configured ignore patterns.
- Version 1 searches textual file contents only. It is not semantic search,
  vector retrieval, AST symbol search, filename search, Git history search, or
  commit-message search.
- Regexes are line-oriented and cannot span newline boundaries in Version 1.
- Documentation-only changes should be reviewed for clarity and consistency;
  implementation changes will require tests and the project quality gate.

## Desired behavior

`search_codebase` must allow a model to:

- search source-code contents using regular expressions;
- execute several independent searches in one tool call;
- narrow a search to a workspace subtree or individual workspace file;
- optionally restrict candidate files with a glob;
- choose case-sensitive or case-insensitive matching;
- receive stable file, line, and column locations;
- receive bounded structured surrounding context;
- discover relevant files before calling `read_files`.

The intended agent loop is:

```text
search_codebase
      ↓
read_files
      ↓
reason
      ↓
apply_patch
      ↓
run_commands
```

The tool should be preferred over shell commands such as `grep -R`, `rg`,
`findstr`, and `Select-String` when the intent is ordinary source discovery.
Shell commands remain appropriate for genuinely shell-specific behavior.

Primary design goals:

1. Deterministic textual discovery.
2. Batch searches.
3. Stable line and column references.
4. Bounded context-window consumption.
5. Explicit result and output-limit metadata.
6. Workspace containment.
7. Backend-neutral semantics.
8. Cancellation, timeout, and selective retry support.

## Tool interface

Tool name:

```text
search_codebase
```

Keep this name. It communicates intent better than generic names such as `grep`,
`search`, or `find`.

Canonical model-facing JSON schema:

```json
{
  "type": "object",
  "properties": {
    "queries": {
      "type": "array",
      "minItems": 1,
      "maxItems": 8,
      "items": {
        "type": "object",
        "properties": {
          "pattern": {
            "type": "string",
            "minLength": 1,
            "maxLength": 4000
          },
          "path": {
            "type": "string",
            "minLength": 1
          },
          "glob": {
            "type": ["string", "null"]
          },
          "case_sensitive": {
            "type": "boolean"
          }
        },
        "required": ["pattern"],
        "additionalProperties": false
      }
    }
  },
  "required": ["queries"],
  "additionalProperties": false
}
```

Defaults:

```text
path           = "."
glob           = null
case_sensitive = false
```

Example:

```json
{
  "queries": [
    {
      "pattern": "class\\s+UserService",
      "path": "src",
      "glob": "**/*.py",
      "case_sensitive": true
    },
    {
      "pattern": "UserService\\(",
      "path": "."
    }
  ]
}
```

For Cline compatibility, a runtime adapter may accept non-canonical inputs such
as `{ "queries": ["class\\s+UserService"] }`, a single string, or an array of
strings, then normalize them to the canonical query object form. These shapes
should not be advertised in the canonical schema.

## Model-facing description

Recommended concise description:

```text
Search file contents across the workspace using regular expressions.

Run multiple independent searches together in one call. Each query may
optionally restrict the search to a workspace-relative path or file glob.

Results contain workspace-relative file paths, one-based line/column
locations, and surrounding context.

Searches are case-insensitive by default. Use case_sensitive when exact
case matters.

Use this tool to locate definitions, references, imports, configuration,
tests, error strings, and other code patterns. After locating relevant
files, use read_files for broader context.

Search output is bounded. If a query reaches the result/output limit,
narrow its regex, path, or glob rather than repeatedly requesting broad
results.
```

The complete rules belong in the schema and runtime, not in a multi-page tool
prompt.

## Query semantics

Each query searches file contents.

It does not search:

- filenames;
- directory names;
- Git history;
- commit messages;
- symbols through an AST;
- semantic embeddings.

For example:

```json
{
  "pattern": "UserService"
}
```

means: find textual occurrences of `UserService` in searchable workspace files.

No matches is not an error. A successful query with no results must return an
empty `matches` array and `more_results_possible = false`.

## Regex semantics and engine

`pattern` is a regular expression. Useful examples include:

```text
UserService
class\s+UserService
from\s+.*\s+import\s+UserService
def\s+test_.*user
TODO|FIXME
```

Regexes are line-oriented. A match must not span newline boundaries in Version 1.
Therefore `foo.*bar` matches only when `foo` and `bar` occur on the same logical
line.

Backend regex semantics must be deterministic. Recommended implementation:

```text
Bundle or require ripgrep and treat Rust regex semantics as the canonical search language.
```

Do not silently switch among Rust regex, JavaScript `RegExp`, Python `re`, PCRE2,
or another engine depending on environment. If ripgrep cannot be provided, use a
regex implementation compatible with the chosen canonical grammar. Otherwise fail
with `SEARCH_BACKEND_UNAVAILABLE` rather than silently changing regex languages.

Do not implement agent-supplied regex search using an unrestricted backtracking
engine. Prefer Rust regex or RE2-style linear-time matching for ReDoS resistance.

Invalid regexes must fail with `INVALID_REGEX`. Do not fall back to literal
search, because that silently changes the model's request.

Empty patterns must fail with `EMPTY_PATTERN`. Do not interpret an empty regex as
matching every line in the repository.

Zero-width regexes may be supported, but they must still observe normal line,
result, output, timeout, and cancellation limits.

## Case sensitivity

The default is case-insensitive search:

```text
case_sensitive = false
```

This preserves Cline's current default behavior. A query may opt into exact-case
matching:

```json
{
  "pattern": "HTTPClient",
  "case_sensitive": true
}
```

Do not use implicit smart-case behavior in Version 1. Explicit behavior is easier
for an agent to reason about.

## Search scope and workspace security

Default scope:

```text
path = "."
```

meaning the workspace root.

`path` may identify either:

- a directory, searched recursively beneath it; or
- an individual file, searched only as that file.

Canonical paths must be workspace-relative. Reject:

- absolute paths;
- empty paths;
- Windows absolute paths such as `C:\outside`;
- parent-directory traversal such as `../outside`;
- paths that resolve outside the workspace;
- symlink escapes.

Resolution model:

```text
resolved_path = workspace_root / requested_path
canonical_path = filesystem_resolve(resolved_path)
```

The implementation must verify that the final canonical path remains inside the
configured workspace root before searching. The same workspace boundary should be
shared by `read_files`, `search_codebase`, and `apply_patch`. Prefer one
`WorkspacePathResolver` rather than three subtly different implementations.

Default symlink behavior:

- do not recursively follow symlinked directories;
- an explicitly referenced symlinked file may be searched only if its canonical
  target remains inside the workspace.

## File glob

`glob` optionally limits candidate files within `path`.

Examples:

```text
**/*.py
**/*.ts
**/*.{ts,tsx}
tests/**
*.toml
```

Example:

```json
{
  "pattern": "timeout",
  "path": "src",
  "glob": "**/*.py"
}
```

This means: search case-insensitively for `timeout` in Python files below `src`.

Invalid globs must fail the affected query with `INVALID_GLOB` and must not fail
unrelated queries in the same batch.

## Ignore and hidden-file behavior

Default behavior should:

- respect `.gitignore`;
- respect `.ignore`;
- respect host-configured ignore patterns;
- exclude `.git`;
- exclude common generated, dependency, build, and cache directories.

Recommended built-in hard excludes:

```text
.git
node_modules
dist
build
.next
coverage
__pycache__
.venv
venv
.cache
.turbo
.output
target
out
bin
obj
```

Search hidden files by default, provided they are not ignored. This includes
files such as:

```text
.github/workflows/*
.pre-commit-config.yaml
.editorconfig
docker/.env.example
```

Use ripgrep-equivalent `--hidden` behavior while still respecting ignore rules
and always excluding `.git/`.

If `path` explicitly identifies a single ignored file, the explicit file path
should override ordinary ignore filtering. Workspace-security restrictions still
apply. A directory scope does not disable ignore rules.

## File classification and size limits

Binary files must be skipped during directory searches. Do not search executables,
archives, databases, images, object files, PDFs, or other binary files as text.

If an explicitly targeted file is binary, fail the query with
`UNSUPPORTED_BINARY_FILE` rather than silently claiming no matches.

Recommended candidate-file size limit:

```text
MAX_SEARCH_FILE_BYTES = 10 MB
```

Use ripgrep's equivalent maximum-file-size control when possible. Generated 200 MB
bundles should not dominate source search even if they escaped ignore rules.

If an explicitly targeted file is oversized, fail the query with `FILE_TOO_LARGE`.

Version 1 should support normal UTF-8 source, CRLF source, and Unicode source.
Unsupported or invalid encodings may be treated as unsuitable text files according
to the file-classification policy.

## Match unit and ordering

A result represents one matching line, not every regex occurrence.

For this line:

```text
foo = foo(foo)
```

and pattern:

```text
foo
```

return one match for that line. The result's `column` identifies the first match
on that line.

Allow multiple matching lines from the same file. Do not copy Cline's current
ripgrep `--max-count=1` behavior, because that limits matching lines per file and
hides relevant references.

Results should be deterministic:

```text
path ascending
then line ascending
then column ascending
```

Backend filesystem traversal order must not leak into the contract.

## Line, column, and context semantics

Return:

```text
line   = 1-based line number
column = 1-based character offset
```

`column` should mean Unicode character offset within the logical line, not raw
UTF-8 byte offset and not terminal display width. Backend byte offsets must be
converted before returning them.

Default context:

```text
CONTEXT_LINES = 2
```

A result should include structured context:

```json
{
  "path": "src/service.py",
  "line": 87,
  "column": 7,
  "text": "class UserService:",
  "text_truncated": false,
  "before": [
    {
      "line": 85,
      "text": ""
    },
    {
      "line": 86,
      "text": "@injectable"
    }
  ],
  "after": [
    {
      "line": 88,
      "text": "    def __init__(self, repo):"
    },
    {
      "line": 89,
      "text": "        self.repo = repo"
    }
  ]
}
```

Do not bake context into opaque prose. Keep line numbers and text structured.

Adjacent matches may produce overlapping contexts in Version 1. Do not introduce
block-merging semantics prematurely. A future renderer may merge adjacent blocks
for display without changing the logical result contract.

## Long-line protection

Reuse the same long-line protection as `read_files` where practical.

Recommended default:

```text
MAX_LINE_CHARS = 2,000
```

If a matching line exceeds the cap:

```json
{
  "text": "<first 2000 chars> …",
  "text_truncated": true
}
```

Context lines should use the same cap and include equivalent truncation metadata
if the result contract grows per-context-line truncation flags.

## Output limits

Recommended initial defaults:

```text
MAX_RESULTS_PER_QUERY     = 100
MAX_OUTPUT_PER_QUERY      = 48,000 chars
MAX_QUERIES_PER_CALL      = 8
MAX_OUTPUT_PER_TOOL_CALL  = 96,000 chars
```

A result means one matching line, not one regex submatch.

When the result limit is reached:

```json
{
  "limit_reached": true,
  "more_results_possible": true
}
```

Do not imply that exactly 100 total matches exist.

Do not middle-cut serialized results. Add complete result objects until the
output budget is reached, then return:

```json
{
  "output_truncated": true,
  "more_results_possible": true
}
```

No result object should be cut in half.

If the aggregate batch budget is exhausted, preserve already completed query
results and mark subsequent ones:

```json
{
  "success": true,
  "matches": [],
  "output_omitted": true,
  "reason": "BATCH_OUTPUT_LIMIT"
}
```

Do not implement cursors or pagination in Version 1. When a query reaches a
result or output limit, the preferred recovery is to narrow the regex, `path`, or
`glob`.

## Structured result contract

Top-level result:

```json
{
  "results": [
    {
      "query": {
        "pattern": "class\\s+UserService",
        "path": "src",
        "glob": "**/*.py",
        "case_sensitive": true
      },
      "success": true,
      "matches": [
        {
          "path": "src/domain/users.py",
          "line": 41,
          "column": 1,
          "text": "class UserService:",
          "text_truncated": false,
          "before": [
            {
              "line": 39,
              "text": ""
            },
            {
              "line": 40,
              "text": "@injectable"
            }
          ],
          "after": [
            {
              "line": 42,
              "text": "    def __init__(self, repository):"
            },
            {
              "line": 43,
              "text": "        self.repository = repository"
            }
          ]
        }
      ],
      "matches_returned": 1,
      "limit_reached": false,
      "output_truncated": false,
      "more_results_possible": false
    }
  ]
}
```

Failure example:

```json
{
  "results": [
    {
      "query": {
        "pattern": "[unfinished",
        "path": ".",
        "glob": null,
        "case_sensitive": false
      },
      "success": false,
      "error": {
        "code": "INVALID_REGEX",
        "message": "Unclosed character class"
      }
    }
  ]
}
```

The human-readable message is secondary. The agent should be able to reason
primarily from stable codes and structured metadata.

## Batch behavior and partial failures

Queries are independent and should execute concurrently.

Recommended bounds:

```text
MAX_QUERIES_PER_CALL = 8
MAX_PARALLEL_SEARCHES = 4
```

Do not unconditionally run an arbitrary-sized array with unlimited parallelism.

Batch results must preserve input query order, regardless of completion order.

One invalid query must not invalidate unrelated queries. Example outcomes in one
call:

```text
query A → matches
query B → invalid regex
query C → no matches
```

must return all three independently in request order.

## Cancellation, timeouts, and retries

Every running search must observe the agent-run cancellation signal.

Cancellation must:

- terminate the search subprocess;
- stop context hydration;
- stop queued queries;
- close file handles;
- return promptly.

Recommended defaults:

```text
PER_QUERY_TIMEOUT = 30 seconds
TOOL_TIMEOUT      = 60 seconds
maxRetries        = 1
```

Do not add a hidden short ripgrep deadline followed by fallback search, because
that can change semantics depending on repository performance. Use one backend
and one deadline.

Because search is read-only, one automatic retry is safe for transient errors
such as temporary process launch failure, transient filesystem failure, or
resource temporarily unavailable.

Never retry deterministic failures:

- `INVALID_REGEX`;
- `INVALID_PATH`;
- `PATH_OUTSIDE_WORKSPACE`;
- `EMPTY_PATTERN`;
- `INVALID_GLOB`.

## Error codes

Define stable error codes:

- `INVALID_INPUT`;
- `EMPTY_PATTERN`;
- `INVALID_REGEX`;
- `INVALID_PATH`;
- `PATH_NOT_FOUND`;
- `PATH_OUTSIDE_WORKSPACE`;
- `NOT_A_FILE_OR_DIRECTORY`;
- `INVALID_GLOB`;
- `SEARCH_BACKEND_UNAVAILABLE`;
- `PERMISSION_DENIED`;
- `SEARCH_TIMEOUT`;
- `SEARCH_CANCELLED`;
- `IO_ERROR`;
- `BATCH_OUTPUT_LIMIT`;
- `UNSUPPORTED_BINARY_FILE`;
- `FILE_TOO_LARGE`.

No-match results must not use `NOT_FOUND`. `PATH_NOT_FOUND` is only for a missing
requested search path.

## Ripgrep execution guidance

Recommended conceptual invocation:

```bash
rg \
  --json \
  --hidden \
  --no-follow \
  --ignore-case \
  --max-filesize 10M \
  <optional glob> \
  <pattern> \
  <scope>
```

Use the case-sensitive equivalent when `case_sensitive = true`.

Do not use:

```text
--max-count=1
```

Instead stream results and stop the process once `MAX_RESULTS_PER_QUERY` matching
lines have been collected. This produces a global result cap rather than a
per-file cap.

Do not buffer all ripgrep stdout. Parse stdout incrementally:

```text
spawn rg
   ↓
read JSON event
   ↓
convert match
   ↓
collect result
   ↓
result limit reached?
   ├── no  → continue
   └── yes → terminate rg
```

This gives bounded memory use, early termination, lower latency, and better
cancellation behavior.

## Backend and context separation

Do not make ripgrep's output format leak throughout the application.

Recommended component boundaries:

```text
SearchCodebaseTool
        ↓
InputValidator
        ↓
WorkspacePathResolver
        ↓
SearchPlanner
        ↓
SearchBackend
        ↓
ContextHydrator
        ↓
ResultLimiter
        ↓
ResultFormatter
```

Core interfaces:

```text
search_codebase(request, context)
    -> SearchCodebaseResult

search(query, workspace, signal)
    -> AsyncIterator[SearchLocation]

hydrate_context(location, context)
    -> SearchMatch
```

Backend-neutral intermediate type:

```text
SearchLocation
    path
    line
    column
    matched_text
```

Hydrated result type:

```text
SearchMatch
    path
    line
    column
    text
    text_truncated
    before[]
    after[]
```

The backend should primarily find match locations. A common `ContextHydrator`
should obtain surrounding lines so context semantics remain identical across
backends.

## Indexing

Do not require an index for Version 1. Start with direct ripgrep search.

Add a persistent or cached index only if profiling demonstrates a real need. An
index creates additional correctness questions around staleness, ignore-rule
parity, watcher behavior, cache invalidation, and workspace changes during
search.

## Relationship to neighboring tools

### `read_files`

Use `search_codebase` to identify where relevant code is. Use `read_files` to
understand surrounding implementation.

Example:

```text
search_codebase("class UserService")
→ src/users/service.py:41
→ read_files({ "path": "src/users/service.py", "start_line": 1, "end_line": 180 })
```

Search context should help locate code, not replace proper file reading.

### `run_commands`

Discourage shell search commands for ordinary source discovery. `search_codebase`
provides workspace isolation, consistent regex semantics, structured matches,
bounded output, batching, context, cancellation, and portable behavior.

### Semantic search

Do not overload this tool with embeddings. If semantic retrieval is added later,
expose it separately, for example as `semantic_search`, because regex search and
semantic search have fundamentally different completeness and ranking semantics.

## Agent examples

Find definition and references together:

```json
{
  "queries": [
    {
      "pattern": "class\\s+UserService"
    },
    {
      "pattern": "UserService\\("
    }
  ]
}
```

Python-only:

```json
{
  "queries": [
    {
      "pattern": "register_user",
      "path": "src",
      "glob": "**/*.py"
    }
  ]
}
```

Exact case:

```json
{
  "queries": [
    {
      "pattern": "HTTPClient",
      "case_sensitive": true
    }
  ]
}
```

Test discovery:

```json
{
  "queries": [
    {
      "pattern": "test_.*timeout",
      "path": "tests"
    }
  ]
}
```

## Differences from current Cline behavior

Keep these Cline-compatible concepts:

- `search_codebase` name;
- regex as the fundamental abstraction;
- multiple searches per call;
- parallel independent searches;
- case-insensitive default;
- 100-result default;
- 2 context lines;
- ignore common generated and dependency paths;
- cancellation;
- 30-second search deadline;
- one retry for a read-only operation;
- about 48,000 characters of output budget per query;
- encourage narrow patterns.

Change these behaviors for this implementation:

- no `--max-count=1` per-file limitation;
- no backend-dependent match semantics;
- no JavaScript-RegExp fallback with different grammar;
- no hidden 5-second ripgrep deadline followed by fallback;
- no whole-stdout buffering;
- no extension or depth behavior that differs by backend;
- no opaque prose-only result format;
- no middle truncation through match objects;
- no unlimited query-array size.

Add these requirements beyond current Cline behavior:

- workspace-relative scope;
- optional path restriction;
- optional file glob;
- optional exact case sensitivity;
- deterministic ordering;
- stable structured result;
- stable error codes;
- one matching-line result regardless of repeated submatches;
- multiple matching lines per file;
- long-line protection;
- explicit output-limit metadata;
- aggregate batch-output limit;
- symlink containment;
- explicit file-size policy;
- streaming ripgrep parser;
- common `ContextHydrator`.

## Testing strategy

Required future acceptance tests include the following scenarios.

### Basic search

- Literal-looking regex finds expected line.
- Regex character classes.
- Alternation.
- Escaped punctuation.
- Multiple queries.
- No matches.
- Multiple matches in one file.
- Multiple files.

### Case behavior

- Default case-insensitive search.
- Explicit case-sensitive search.
- Uppercase and lowercase distinctions.

### Regex behavior

- Invalid regex rejected.
- Empty regex rejected.
- Zero-width regex behaves safely.
- Regex cannot span lines.
- Unicode matching.

### Scope and paths

- Workspace root search.
- Nested directory search.
- Explicit file search.
- Glob restriction.
- Path not found.
- Invalid glob.
- Path outside workspace rejected.
- Symlink escape rejected.

### Ignore behavior

- `.gitignore` respected.
- Hidden tracked config searched.
- `.git` excluded.
- `node_modules` excluded.
- Explicit ignored file can be searched.

### Results

- Line is one-based.
- Column is one-based.
- Unicode prefix produces correct column.
- One result per matching line.
- Multiple matching lines in the same file.
- Deterministic path and line order.

### Context

- Two lines before.
- Two lines after.
- Beginning-of-file match.
- End-of-file match.
- Overlapping contexts.
- Long context line truncated safely.

### Limits

- 100-result cap.
- 48,000-character query-output cap.
- Aggregate batch-output cap.
- No partial JSON or partial result objects.
- `more_results_possible` correctly set.

### Files

- Binary skipped during directory search.
- Explicitly targeted binary reports error.
- Oversized file skipped or rejected appropriately.
- Normal UTF-8 source.
- CRLF source.
- Unicode source.

### Concurrency

- Multiple queries run concurrently.
- Concurrency limit respected.
- Results returned in input-query order.

### Cancellation

- Running ripgrep is terminated.
- Queued searches cancelled.
- Context hydration stops.

### Timeout and retry

- Query killed at deadline.
- Transient failure retried once.
- Invalid regex not retried.

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Future implementation should start with focused validator, path resolver, search
planner, backend parser, context hydrator, limiter, and result-contract tests
before adding a model-callable runtime adapter.

## Boundaries

- Always treat `search_codebase` as textual regex search, not semantic search.
- Always keep the canonical public schema as `{ "queries": [query objects] }`.
- Always keep backend selection unobservable in search semantics.
- Always reject empty patterns and invalid regexes explicitly.
- Always resolve paths relative to a configured workspace root and verify final
  canonical containment.
- Always return independent per-query results in request order.
- Always keep results structured, bounded, and explicit about truncation or output
  omission.
- Always hydrate context through common logic rather than ripgrep-specific context
  event parsing.
- Ask before introducing an indexed search layer, semantic search, model-visible
  non-canonical input shapes, pagination, or a different canonical regex engine.
- Never silently change regex languages because a backend is unavailable.
- Never use Cline's `--max-count=1` per-file behavior.
- Never buffer unbounded backend output before parsing.
- Never allow search paths to escape the configured workspace through absolute
  paths, parent traversal, or symlinks.

## Success criteria

- The spec defines `search_codebase` as the single preferred textual discovery
  primitive for coding-agent workflows.
- The public tool interface is the canonical `{ "queries": [...] }` schema with
  query objects containing `pattern`, optional `path`, optional `glob`, and
  optional `case_sensitive`.
- The path model includes workspace-relative paths, path/file scopes, glob
  filtering, ignore semantics, hidden-file search, symlink containment, and
  explicit ignored-file behavior.
- The regex model is deterministic, line-oriented, case-insensitive by default,
  ReDoS-resistant, and explicit about invalid or empty patterns.
- The result model includes one matching-line result per line, one-based
  line/column locations, Unicode-aware columns, deterministic ordering,
  structured context, long-line protection, and stable error codes.
- The limit model includes per-query result caps, per-query output caps, aggregate
  batch caps, no partial result objects, and no pagination in Version 1.
- The runtime model includes bounded concurrency, partial failures, cancellation,
  timeouts, selective retry, binary/oversized-file handling, and streaming backend
  parsing.
- The architecture separates validation, path resolution, planning, backend
  search, context hydration, result limiting, formatting, and provider adaptation.
- Future acceptance tests are explicit enough to drive implementation.

## Open questions

- Should Version 1 require bundled ripgrep, discover a host ripgrep binary, or
  allow either as long as the same canonical regex semantics are guaranteed?
- What exact glob grammar should be canonical if host platforms differ?
- Should context-line truncation include per-context-line `text_truncated` flags
  in the initial result contract, or is truncating context text sufficient until a
  caller needs structured context truncation metadata?
- Should ignored explicit files be searchable only when they are named exactly, or
  also when a `path` names a glob-like single-file candidate through host
  expansion? Version 1 should avoid shell expansion and prefer exact explicit
  file paths.
- Should the implementation live inside the `agent_runtime` slice, a dedicated
  search feature slice, or a shared infrastructure package once multiple runtime
  tools need the same workspace resolver and filesystem classification logic?
