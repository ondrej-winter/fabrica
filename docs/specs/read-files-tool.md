# Spec: Read Files Tool

## Objective

Define the model-facing and host-facing specification for a read-only
`read_files` filesystem inspection tool.

The tool is for autonomous coding agents that need one preferred primitive for
reading known workspace files, reading inclusive line ranges, paging through
large files, batching independent reads, and inspecting supported images when the
active model supports image input.

The design goal is a safe, bounded, provider-neutral read primitive that gives
the model exactly the requested source context with stable line references and
explicit metadata about any content it did not receive.

## Current context

- Project: `fabrica`, a Python 3.13 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime.md`.
- Filesystem mutation tool design is owned by `docs/specs/apply-patch-tool.md`.
- This spec defines the desired `read_files` tool contract only. It does not
  implement the tool.
- `read_files` is the read-side counterpart to `apply_patch`: the model reads
  bounded source context, reasons from stable line numbers, then applies
  contextual patches or asks for narrower ranges.

## Assumptions

- The primary caller is a model-driven coding agent operating inside a configured
  workspace root.
- The default implementation target will be Python and should follow Fabrica's
  feature-slice and hexagonal architecture conventions when implementation work
  begins.
- Canonical model-facing paths are workspace-relative, not absolute.
- The host can provide a canonical workspace root, model image-capability
  information, cancellation signals, timeout configuration, and retry policy.
- Version 1 supports UTF-8 and UTF-8 BOM text. UTF-16 LE/BE may be added when it
  can be detected reliably.
- Documentation-only changes should be reviewed for clarity and consistency;
  implementation changes will require tests and the project quality gate.

## Desired behavior

`read_files` must allow a model to:

- read one or more text files;
- read specific inclusive line ranges;
- page through large files;
- inspect supported image files when the active model supports image input;
- batch independent reads in a single tool call.

The tool should be preferred over shell commands such as `cat`, `sed`, `head`,
`tail`, `type`, and `Get-Content` when the intent is simply to inspect file
contents.

Primary design goals:

1. Cheap retrieval of source context.
2. Batch reads.
3. Stable line references for subsequent edits.
4. Bounded context-window consumption.
5. Explicit truncation and pagination.
6. Workspace containment.
7. Read-only semantics.
8. Multimodal file inspection where useful.

## Tool interface

Tool name:

```text
read_files
```

Do not create separate `read_file` or `read_file_range` tools. A batch of one is
already equivalent to `read_file`, and one stable interface is easier for the
model.

Canonical model-facing JSON schema:

```json
{
  "type": "object",
  "properties": {
    "files": {
      "type": "array",
      "minItems": 1,
      "maxItems": 20,
      "items": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "minLength": 1
          },
          "start_line": {
            "type": ["integer", "null"],
            "minimum": 1
          },
          "end_line": {
            "type": ["integer", "null"],
            "minimum": 1
          }
        },
        "required": ["path"],
        "additionalProperties": false
      }
    }
  },
  "required": ["files"],
  "additionalProperties": false
}
```

Example:

```json
{
  "files": [
    {
      "path": "src/service.py"
    },
    {
      "path": "src/config.py",
      "start_line": 40,
      "end_line": 100
    }
  ]
}
```

The model-facing protocol must stay canonical. A provider compatibility layer may
normalize common mistakes before validation, such as legacy `file_path` or
`paths` shapes, but malformed structures must not become part of the domain API
or advertised contract.

## Model-facing description

Recommended concise description:

```text
Read one or more files from the workspace.

Each file entry requires a workspace-relative path and may include
inclusive one-based start_line/end_line bounds.

Read multiple independent files together in one call.

Text results include line numbers and pagination metadata. Large reads are
bounded; use next_start_line or a narrower range to continue reading.

Supported image files are returned as image input when the current model
supports images.

Prefer read_files over shell commands when you only need file contents.
```

The complete rules belong in the schema and runtime, not in a multi-page tool
prompt.

## Path semantics and workspace security

Canonical paths should be workspace-relative:

```text
src/foo.py
tests/test_foo.py
README.md
```

Resolution model:

```text
resolved_path = workspace_root / requested_path
canonical_path = filesystem_resolve(resolved_path)
```

The implementation must verify that the final canonical path remains inside the
configured workspace root.

Reject by default:

- absolute paths;
- empty paths;
- parent-directory traversal such as `../outside.txt`;
- symlink escapes;
- paths that resolve outside the workspace.

An embedding application may explicitly enable external reads with a host-owned
permission such as `allow_external_reads = true`, but this must not be controlled
by the model.

Symlinks may be followed only when the final canonical target remains inside the
permitted workspace. Containment must be checked against the final
filesystem-resolved path, not only the lexical path.

Unicode filename tolerance may be supported carefully:

1. attempt exact path resolution;
2. only if it fails, optionally attempt Unicode-normalized matching;
3. accept only a unique candidate;
4. report the actual resolved path.

The implementation must never heuristically choose among multiple similar
filenames.

## Range semantics

Line ranges are 1-based and inclusive.

Example:

```json
{
  "path": "src/foo.py",
  "start_line": 10,
  "end_line": 20
}
```

This means exactly lines 10 through 20 inclusive.

Defaults:

- if both bounds are absent, `start_line = 1` and `end_line = unbounded`;
- if only `start_line` is supplied, read from that line until EOF or output cap;
- if only `end_line` is supplied, read from line 1 through `end_line`.

Reject:

- `start_line < 1`;
- `end_line < 1`;
- `start_line > end_line`;
- non-integer line numbers in the canonical API.

Example range error:

```json
{
  "code": "INVALID_RANGE",
  "path": "src/foo.py",
  "message": "start_line must be <= end_line",
  "start_line": 100,
  "end_line": 50
}
```

An adapter may tolerate stringified integer values such as `"3"` before canonical
validation, but strings must not be advertised as valid line numbers.

## Text output

Text output should contain line numbers by default:

```text
 98 | def execute():
 99 |     result = run()
100 |     return result
```

The model must not need to request line numbering explicitly. Line numbers provide
stable references for discussion, follow-up range requests, edits, and compiler
or test error interpretation.

## Output limits

Recommended initial defaults:

```text
MAX_READ_LINES        = 2,000
MAX_LINE_CHARS        = 2,000
MAX_READ_OUTPUT_CHARS = 48,000
```

These limits protect three different resources:

- per-file window size;
- huge individual lines such as minified JavaScript, generated JSON, source maps,
  and embedded blobs;
- total model context consumed by one file request.

A truncated line should render as:

```text
123 | <first 2000 chars> … [line truncated]
```

The result must include structured truncation metadata. Truncation must never be
silent.

## Structured result contract

Top-level result:

```json
{
  "results": [
    {
      "path": "src/foo.py",
      "success": true,
      "type": "text",
      "content": "1 | ...\n2 | ...",
      "start_line": 1,
      "end_line": 120,
      "complete": false,
      "next_start_line": 121,
      "total_lines": 873,
      "total_lines_exact": true,
      "truncated_lines": []
    }
  ]
}
```

For long individual lines, include their line numbers:

```json
{
  "truncated_lines": [47]
}
```

If output is capped, `complete` must be `false` and `next_start_line` must point
to the line the model should request next when continuing pagination.

If the total line count is unknown or approximate:

```json
{
  "total_lines": 50000,
  "total_lines_exact": false
}
```

The result may display this to users as `50,000+ lines`, but the protocol must
preserve exactness as structured metadata.

## Pagination

The normal workflow is:

```text
read_files(path)
        ↓
result.complete == false
        ↓
read_files(path, start_line=result.next_start_line)
```

Example continuation request:

```json
{
  "files": [
    {
      "path": "src/large.py",
      "start_line": 847
    }
  ]
}
```

The implementation must not automatically return the entire file across multiple
internal pages. That defeats bounded context consumption.

## Large text files and streaming

Text files should be streamed rather than loaded completely into memory.

Recommended hard safety limit:

```text
MAX_TEXT_FILE_BYTES = 100 MB
```

Files larger than this must fail with:

```json
{
  "code": "FILE_TOO_LARGE",
  "path": "data/huge.log",
  "size_bytes": 328348123,
  "max_size_bytes": 100000000
}
```

A text reader should:

1. open a streaming reader;
2. skip lines before `start_line`;
3. capture requested lines;
4. stop capturing after the requested `end_line`, max line count, or max output
   characters;
5. stop scanning once sufficient pagination metadata is known;
6. close the stream immediately.

The implementation must not read a 90 MB file into memory simply to return 200
lines.

## Total-line calculation

The model benefits from total-line metadata, but counting every remaining line in
a huge file can make a small read unexpectedly expensive.

Recommended metadata scan ceiling:

```text
MAX_METADATA_SCAN_LINES = 50,000
```

If EOF is reached:

```json
{
  "total_lines": 17420,
  "total_lines_exact": true
}
```

If EOF is not reached before the metadata scan ceiling:

```json
{
  "total_lines": 50000,
  "total_lines_exact": false
}
```

## Batch behavior

Multiple reads should execute concurrently because they are independent read-only
operations.

Recommended bounds:

```text
MAX_FILES_PER_CALL = 20
MAX_PARALLEL_READS = 8
```

Batch results must preserve request ordering.

Partial failures must not fail the entire batch. If A succeeds, B fails, and C
succeeds, the result must contain success for A, failure for B, and success for C
in the original request order.

Example:

```json
{
  "results": [
    {
      "path": "src/a.py",
      "success": true,
      "type": "text",
      "content": "..."
    },
    {
      "path": "src/missing.py",
      "success": false,
      "error": {
        "code": "NOT_FOUND",
        "message": "File does not exist"
      }
    },
    {
      "path": "src/c.py",
      "success": true,
      "type": "text",
      "content": "..."
    }
  ]
}
```

## File classification

`read_files` reads files, not directories. Directory discovery belongs to
`search_codebase` or a future explicit workspace/list operation.

If the resolved path is a directory, fail with:

```json
{
  "code": "NOT_A_FILE",
  "path": "src"
}
```

Ordinary binary files must be rejected, including archives, executables, shared
libraries, PDFs, SQLite databases, and compiled objects.

Binary rejection example:

```json
{
  "code": "UNSUPPORTED_BINARY_FILE",
  "path": "artifact.bin"
}
```

The implementation must not dump arbitrary binary data or base64 into model
context.

## Image support

`read_files` may support images as a special multimodal case.

Recommended v1 formats:

- PNG;
- JPEG;
- GIF;
- WebP.

If the active model supports image input, an image result should be:

```json
{
  "path": "screenshots/error.png",
  "success": true,
  "type": "image",
  "media_type": "image/png",
  "data": "<binary content block>"
}
```

The runtime should send bytes to the provider using its native image-content
representation rather than exposing base64 text to the model. Base64, if needed,
must remain an implementation detail.

Recommended maximum:

```text
MAX_IMAGE_BYTES = 10 MB
```

If exceeded:

```json
{
  "code": "IMAGE_TOO_LARGE",
  "path": "screenshot.png",
  "size_bytes": 18400000,
  "max_size_bytes": 10000000
}
```

If an image is requested but the current model does not support images:

```json
{
  "code": "IMAGE_INPUT_UNSUPPORTED",
  "path": "diagram.png"
}
```

The implementation must not reinterpret unsupported images as text.

Image detection must not rely exclusively on filename extension. Preferred
sequence:

```text
inspect magic bytes
→ identify supported image format
→ verify extension if present
```

For example, `foo.png` containing a ZIP archive must not be treated as an image
merely because the extension is `.png`.

## Text encoding

Version 1 should support:

- UTF-8;
- UTF-8 BOM.

UTF-16 LE/BE may be supported when detected reliably.

The reader must not silently replace extensive invalid byte sequences and pretend
the content was read correctly. If decoding fails:

```json
{
  "code": "UNSUPPORTED_ENCODING",
  "path": "legacy.dat"
}
```

## Cancellation, timeouts, and retries

Every file operation should accept the agent-run cancellation signal.

Cancellation must:

- stop streaming;
- close file handles;
- cancel remaining queued reads;
- return promptly.

Recommended defaults:

```text
PER_FILE_TIMEOUT = 10 seconds
TOOL_TIMEOUT     = 20 seconds
```

These should be configurable by the host.

Because reads are side-effect free, `read_files` is retryable. One automatic retry
is reasonable:

```text
maxRetries = 1
```

Only transient failures should be retried, such as temporary I/O errors,
network-mounted filesystem interruptions, or resource-temporarily-unavailable
errors.

Do not retry deterministic failures:

- `NOT_FOUND`;
- `NOT_A_FILE`;
- `PATH_OUTSIDE_WORKSPACE`;
- `INVALID_RANGE`;
- `UNSUPPORTED_BINARY_FILE`.

## Error codes

Define stable error codes:

- `INVALID_INPUT`;
- `INVALID_PATH`;
- `PATH_OUTSIDE_WORKSPACE`;
- `NOT_FOUND`;
- `NOT_A_FILE`;
- `INVALID_RANGE`;
- `PERMISSION_DENIED`;
- `FILE_TOO_LARGE`;
- `UNSUPPORTED_BINARY_FILE`;
- `UNSUPPORTED_ENCODING`;
- `IMAGE_TOO_LARGE`;
- `IMAGE_INPUT_UNSUPPORTED`;
- `READ_TIMEOUT`;
- `READ_CANCELLED`;
- `IO_ERROR`.

The human-readable message is secondary. The agent should be able to reason
primarily from `code`.

## Recommended agent workflow

Typical investigation:

```text
search_codebase
      ↓
read_files relevant files
      ↓
reason
      ↓
apply_patch
      ↓
run_commands tests
```

If paths are already known:

```text
read_files
      ↓
apply_patch
```

If several files are independently relevant, read them in one tool call:

```json
{
  "files": [
    { "path": "src/domain.py" },
    { "path": "src/api.py" },
    { "path": "tests/test_api.py" }
  ]
}
```

Do not make three sequential tool calls when the reads are independent.

## Relationship to neighboring tools

### `search_codebase`

Use `read_files` when the model knows which file it wants to inspect. Use
`search_codebase` when the model knows what it is looking for but not where it
lives.

Bad workflow:

```text
read every Python file looking for UserService
```

Good workflow:

```text
search_codebase("class UserService")
→ read_files(found paths)
```

### `run_commands`

Reading ordinary source through shell commands such as `cat foo.py` should be
discouraged. `read_files` provides line numbers, controlled output, batching,
range semantics, structured truncation, image support, security controls, and
predictable provider context.

The shell remains appropriate for generated output, git diff/status, build and
test output, specialized extraction, and very large logs requiring tools such as
`grep` or `awk`.

## Architecture and project structure

Recommended component boundaries:

```text
ReadFilesTool
      ↓
InputValidator
      ↓
WorkspacePathResolver
      ↓
FileClassifier
      ├── TextFileReader
      └── ImageFileReader
      ↓
OutputLimiter
      ↓
ResultFormatter
```

Core interfaces:

```text
read_files(requests, context)
    -> ReadFilesResult

read_text_file(request, context)
    -> TextFileResult

read_image_file(request, context)
    -> ImageFileResult
```

The reader must know nothing about LLM provider-specific JSON schemas. Provider
adaptation happens one layer above or below it as appropriate.

Likely future implementation ownership:

- Spec: `docs/specs/read-files-tool.md`.
- Runtime tool contracts and DTOs: under
  `src/fabrica/features/agent_runtime/application/` if exposed as a model-callable
  runtime tool.
- Filesystem reading, path resolution, streaming, MIME detection, and provider
  image conversion: adapter or infrastructure code, not domain or application
  core.
- Unit tests: mirrored under `tests/unit/` for validator, path resolver,
  classifier, limiter, formatter, and text/image reader behavior.
- Integration tests: under `tests/integration/` for real filesystem behavior,
  symlink containment, streaming, cancellation, and timeout checks.

Implementation must preserve hexagonal boundaries: domain and application code
must not perform filesystem I/O directly, and provider-specific multimodal
content structures must not leak into stable application ports or DTOs.

## Differences from current Cline behavior

Keep these Cline-compatible concepts:

- one tool for single or batch reads;
- inclusive one-based ranges;
- parallel independent reads;
- default line numbers;
- pagination;
- bounded per-file output;
- per-line truncation;
- streamed large-file reads;
- image support;
- cancellation;
- read operation is retryable;
- partial success across a batch.

Change these behaviors for this implementation:

- do not advertise absolute paths;
- do not expose a huge tolerant union schema;
- do not make malformed range-array entries part of the protocol;
- do not rely only on image extension;
- do not encode pagination only as prose;
- do not expose base64 image data as model-visible text;
- do not allow unconstrained parallel read fan-out.

Add these requirements beyond current Cline behavior:

- strict workspace containment;
- symlink escape protection;
- canonical workspace-relative paths;
- structured pagination metadata;
- stable error codes;
- explicit `total_lines_exact`;
- bounded batch size;
- bounded read concurrency;
- MIME and magic-byte validation;
- selective retry policy.

## Testing strategy

Required future acceptance tests include the following scenarios.

### Basic reads

- Read a small UTF-8 text file.
- Read multiple files.
- Read an empty file.
- Read a file with no terminal newline.
- Read a CRLF file.
- Read Unicode source.

### Ranges

- `start_line` only.
- `end_line` only.
- Both bounds.
- Exact one-line range.
- Range ending at EOF.
- Range extending beyond EOF.
- Start beyond EOF.
- `start_line > end_line` rejected.
- Zero or negative line numbers rejected.

### Limits

- More than 2,000 lines.
- More than 48,000 output characters.
- Individual line over 2,000 characters.
- Multiple oversized lines.
- Pagination produces the correct `next_start_line`.

### Batch behavior

- All files succeed.
- One file fails and others succeed.
- Request ordering is preserved in the result.
- Concurrency cap is enforced.

### Paths

Reject:

- `../foo`;
- absolute paths;
- symlink escaping workspace;
- directory path.

Allow:

- normal nested workspace paths;
- workspace-contained symlink.

### Images

- PNG.
- JPEG.
- GIF.
- WebP.
- Unsupported model.
- File over image limit.
- Fake image extension with invalid magic bytes.

### Large files

- Text under 100 MB streams correctly.
- Text over 100 MB is rejected.
- Initial 100 lines do not require loading the entire file.

### Cancellation

- Cancel during large stream.
- File descriptor is closed.
- Remaining queued reads are cancelled.

### Timeouts and retries

- Blocked read times out.
- Transient timeout may retry once.
- Deterministic error does not retry.

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Future implementation should start with focused validator, path resolver,
classification, text-reader, limiter, and result-contract tests before adding a
model-callable runtime adapter.

## Boundaries

- Always use one canonical `read_files` interface for single and batch reads.
- Always keep filesystem reads bounded, line-numbered, and explicit about
  truncation.
- Always resolve paths relative to a configured workspace root and verify final
  canonical containment.
- Always keep image provider adaptation outside the core reader contract.
- Always return independent per-file results in request order.
- Ask before enabling model-controlled external reads, broad compatibility input
  shapes in the public schema, non-UTF-8 encodings beyond reliable BOM detection,
  or unbounded concurrency.
- Never read directories through `read_files`.
- Never expose arbitrary binary or base64 data as model-visible text.
- Never silently truncate output.
- Never automatically page through an entire large file.
- Never allow paths to escape the configured workspace through absolute paths,
  parent traversal, or symlinks.

## Success criteria

- The spec defines `read_files` as the single preferred filesystem read primitive
  for coding-agent workflows.
- The public tool interface is the canonical `{ "files": [...] }` schema with
  workspace-relative paths and optional inclusive one-based line bounds.
- The path model includes workspace containment, absolute-path rejection,
  traversal rejection, symlink escape protection, and optional host-controlled
  external-read permission.
- The text output model includes default line numbers, UTF-8-oriented decoding,
  streaming, file-size limits, per-line limits, per-file output limits,
  structured truncation metadata, pagination, and total-line exactness metadata.
- The batch model includes partial success, request-order preservation, bounded
  batch size, and bounded concurrency.
- The image model includes supported formats, model capability checks, image size
  limits, native multimodal delivery, and magic-byte validation.
- The runtime model includes cancellation, timeouts, selective retry, and stable
  error codes.
- The architecture separates validation, path resolution, classification,
  text/image reading, output limiting, formatting, and provider adaptation.
- Future acceptance tests are explicit enough to drive implementation.

## Open questions

- Should Version 1 support UTF-16 LE/BE text files, or should it reject them until
  explicit implementation and tests are added?
- Which host component should own `allow_external_reads`, if any workflow ever
  needs external reads?
- Should Unicode-normalized filename fallback be enabled by default or only behind
  a compatibility flag?
- What provider abstraction should carry native image content without exposing
  base64 as model-visible text?
- Should total-line counting be exact for small files even when the requested
  range is narrow, or should the metadata scan ceiling always govern cost?
- Should the read-files implementation live inside the `agent_runtime` slice, a
  dedicated feature slice, or a shared infrastructure package once multiple
  workflows need it?
