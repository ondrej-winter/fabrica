# Read Files Tool Implementation Plan

**Status:** Ready for implementation — implementation not started.

**Readiness:** Ready. The runtime, POSIX secure-open, and blocking-I/O execution
decisions are accepted in
[`ADR 0004`](../adr/0004-use-bounded-multimodal-read-tool-runtime-contracts.md).
Implementation must preserve its bounded, provider-neutral, capability-gated, and
helper-process guarantees.

**Created:** August 28, 2026.

**Canonical specification:** [`../specs/read-files-tool.md`](../specs/read-files-tool.md), accepted August 27, 2026.

## Objective

Implement the canonical, read-only `read_files` model tool as the
`workspace_reading` vertical slice. The tool must read known workspace files in
batches, support inclusive one-based text ranges and pagination, safely inspect
supported images, and report bounded, structured per-file outcomes.

## Scope

### In scope

- One canonical `{ "files": [...] }` registered-tool schema with one to twenty
  workspace-relative requests.
- UTF-8 and UTF-8-BOM text reading with stable line numbers, ranges, streaming,
  output limits, pagination, and bounded total-line metadata.
- Workspace containment, parent-traversal rejection, and symlink-escape
  protection for the filesystem object actually read.
- PNG, JPEG, GIF, and WebP inspection using magic-byte validation, model image
  capability checks, and provider-neutral image content.
- Partial batch success, bounded parallelism, cancellation, timeouts, and one
  transient-failure retry.
- Runtime registration, composition-root wiring, unit tests, integration tests,
  and configured quality-gate validation.

### Out of scope

- Filesystem mutation, directory listing, source search, or command execution.
- Non-UTF-8 text decoding, including UTF-16 support.
- Model-visible raw binary data or base64 image text.
- Unicode-normalized filename fallback unless a separately approved host
  compatibility setting is added.
- Unbounded batch size, concurrency, metadata scanning, or automatic full-file
  paging.

## Architecture and sequencing

```text
read_files registered-tool adapter
        ↓
workspace_reading ReadFiles application use case
        ↓
application-owned workspace-reading ports and DTOs
        ↓
POSIX filesystem adapter
  ├── secure path resolution and open-time containment
  ├── file classification and magic-byte inspection
  ├── streamed text/image reads
  └── supervised helper-process single-request outcomes
        ↓
workspace_reading application execution coordinator
  └── bounded scheduling, cancellation, deadline, and retry handling
        ↓
bootstrap composition injects workspace root, policy, limits, and capabilities
```

Implement foundational contracts first, then one complete secure text-reading
vertical path, followed by images and runtime/composition integration. The
application core must not perform filesystem I/O; provider-native multimodal
types must not enter `workspace_reading` ports or DTOs.

The current `agent_runtime` registered-tool protocol must be extended before
`read_files` exposure. P0 introduces bounded immutable recursive JSON arguments
and ordered provider-neutral content parts for generic tools; provider adapters
alone translate those values to native request and multipart return types.

## Progress Tracking

Update this dashboard and the matching detailed checkbox after every completed
task, verification step, scope change, blocker, or newly discovered work. A
parent item is complete only after all of its child checks are complete or
explicitly marked not applicable with a reason.

- [x] **T1** Define workspace-reading DTOs, limits, result variants, and stable errors.
  - [x] **T1.A1** DTOs enforce valid ranges, paths, limits, pagination, and safe metadata.
  - [x] **T1.V1** Focused DTO/error tests pass.
- [x] **T2** Define application ports, read context, and use-case orchestration boundary.
  - [x] **T2.A1** Application code depends only on DTOs and ports; host policy is explicit.
  - [x] **T2.V1** Port export/type-contract tests pass.
- [x] **T3** Implement pure range validation, output limiting, and text formatting.
  - [x] **T3.A1** Formatting and pagination are explicit and never silently truncate output.
  - [x] **T3.V1** Parametrized unit tests cover ranges, caps, truncation, and line rendering.
- [x] **C1** Contract checkpoint: T1–T3 complete before filesystem implementation.
- [x] **P0** Implement accepted agent-runtime nested-argument and multipart-result contracts.
  - [x] **P0.A1** Generic runtime contracts represent canonical bounded immutable nested JSON arguments and ordered provider-neutral text/image content parts.
  - [x] **P0.V1** Agent-runtime and PydanticAI regression tests cover bounds, canonical argument digests, nested mapping, and multipart returns before `read_files` runtime exposure begins.
- [x] **T4** Implement capability-gated secure POSIX path resolution and file classification.
  - [x] **T4.A1** Open-time containment rejects traversal and escaping symlinks.
  - [x] **T4.V1** Real-filesystem containment and classification integration tests pass.
- [x] **T5** Implement streamed UTF-8 text reads and bounded total-line metadata.
  - [x] **T5.A1** Text reads respect file, line, output, and metadata scan limits.
  - [x] **T5.V1** Text streaming, encoding, range, and pagination tests pass.
- [x] **C2** Secure text-read checkpoint: T4–T5 complete before runtime exposure.
- [x] **T6** Implement supervised helper-process batch execution, cancellation, deadlines, and retry.
  - [x] **T6.A1** Batch results retain request order and isolate individual failures.
  - [x] **T6.V1** Scheduler, cancellation, timeout, and retry tests pass.
  - [x] **T6.V2** Real helper-process cancellation and timeout cleanup integration tests pass.
- [x] **T7** Implement verified provider-neutral image reading.
  - [x] **T7.A1** Only supported, verified images are returned as `ImageContent`.
  - [x] **T7.V1** Image format, capability, magic-byte, and size tests pass.
- [x] **T8** Add the canonical `read_files` registered-tool adapter.
  - [x] **T8.A1** The adapter exposes only the specified tool schema and maps outcomes safely.
  - [x] **T8.V1** Adapter schema, validation, and outcome-mapping tests pass.
- [x] **T9** Add composition-root factory and offline tool-loop integration.
  - [x] **T9.A1** Construction is side-effect free and filesystem/provider details remain outside runtime core.
  - [x] **T9.V1** Bootstrap API and tool-loop integration tests pass.
- [x] **C3** Runtime checkpoint: T6–T9 complete and the full vertical path is offline-testable.
- [x] **T10** Update applicable public documentation and execute the full quality gate.
  - [x] **T10.A1** Documentation reflects implemented behavior without changing the accepted spec silently.
  - [x] **T10.V1** Format, lint, type check, tests, and import-boundary checks pass.

## Detailed Tasks

### T1. Define workspace-reading DTOs, limits, result variants, and stable errors

**Dependencies:** None.

**Likely files:**

- `src/fabrica/features/workspace_reading/__init__.py`
- `src/fabrica/features/workspace_reading/application/__init__.py`
- `src/fabrica/features/workspace_reading/application/dtos/read_files.py`
- `src/fabrica/features/workspace_reading/application/dtos/__init__.py`
- `tests/unit/features/workspace_reading/application/test_read_files_dtos.py`

**Implementation work:**

- Define immutable request, batch-command, limits, error, text-result,
  image-result, and batch-result DTOs.
- Define provider-neutral `ImageContent` with verified bytes, path, and media
  type.
- Define all Version 1 error codes: `INVALID_INPUT`, `INVALID_PATH`,
  `PATH_OUTSIDE_WORKSPACE`, `NOT_FOUND`, `NOT_A_FILE`, `INVALID_RANGE`,
  `PERMISSION_DENIED`, `FILE_TOO_LARGE`, `UNSUPPORTED_BINARY_FILE`,
  `UNSUPPORTED_ENCODING`, `IMAGE_TOO_LARGE`, `IMAGE_INPUT_UNSUPPORTED`,
  `READ_TIMEOUT`, `READ_CANCELLED`, and `IO_ERROR`.
- Encode accepted defaults: 20 files/call, 8 parallel reads, 2,000 returned
  lines, 2,000 characters/line, 48,000 output characters/file, 100 MB text,
  10 MB image, 50,000 metadata scan lines, 10-second per-file deadline,
  20-second tool deadline, and one retry.

**Acceptance criteria:**

- [x] **T1.A1** Invalid ranges, blank paths, invalid limits, unsafe error
  metadata, and inconsistent pagination are rejected at DTO construction.
- [x] **T1.A2** The result model represents exact and bounded/inexact line
  totals without provider-specific or filesystem-specific types.

**Verification:**

- [x] **T1.V1** Add focused pytest coverage for each DTO invariant and error
  code.
- [x] **T1.V2** Run `uv run ruff check` and `uv run ty check` for the affected
  source and tests.

### T2. Define application ports, read context, and use-case orchestration boundary

**Dependencies:** T1.

**Likely files:**

- `src/fabrica/features/workspace_reading/application/ports/workspace_reading.py`
- `src/fabrica/features/workspace_reading/application/ports/__init__.py`
- `src/fabrica/features/workspace_reading/application/use_cases/read_files.py`
- `src/fabrica/features/workspace_reading/application/use_cases/__init__.py`
- `tests/unit/features/workspace_reading/application/test_ports.py`

**Implementation work:**

- Define a narrow outbound reader port for one normalized request and a
  host-supplied context containing workspace authorization, image capability,
  cancellation/deadline information, and configured limits.
- Define the `ReadFiles` use case for normalized batch commands and explicitly
  delegate one-request reads to an application-owned outbound port. Do not choose
  scheduling, retry, cancellation, or deadline mechanics in this task; T6 owns
  that execution coordination after its design is resolved.
- Keep external-read authorization as an already-decided host capability rather
  than an argument the model can control.

**Acceptance criteria:**

- [x] **T2.A1** The application layer contains no `open()`, path-resolution,
  MIME, provider SDK, or runtime-specific implementation dependencies.
- [x] **T2.A2** All dependencies required for real filesystem reads are explicit
  application-owned ports, and batch execution ownership is explicitly deferred
  to T6.

**Verification:**

- [x] **T2.V1** Add port/export tests and type-check application boundaries.

### T3. Implement pure range validation, output limiting, and text formatting

**Dependencies:** T1, T2.

**Likely files:**

- `src/fabrica/features/workspace_reading/application/validation.py`
- `src/fabrica/features/workspace_reading/application/text_formatting.py`
- `src/fabrica/features/workspace_reading/application/output_limiting.py`
- `tests/unit/features/workspace_reading/application/test_validation.py`
- `tests/unit/features/workspace_reading/application/test_text_formatting.py`
- `tests/unit/features/workspace_reading/application/test_output_limiting.py`

**Implementation work:**

- Normalize omitted bounds to the specified defaults and reject zero, negative,
  and inverted bounds.
- Render every text line as `<one-based line> | <content>`.
- Add visible per-line truncation and structured `truncated_lines` metadata.
- Stop at requested end line, line limit, or output-character limit and derive
  actual final line, `complete`, and `next_start_line` correctly.

**Acceptance criteria:**

- [ ] **T3.A1** A per-line truncation does not make a fully-read file incomplete.
- [ ] **T3.A2** An output cap returns the actual final line, `complete=false`,
  and the next unread line; it never silently continues internally.

**Verification:**

- [ ] **T3.V1** Add parametrized tests for omitted/one-sided/two-sided ranges,
  EOF behavior, line and output caps, and empty content.

### C1. Contract checkpoint

**Dependencies:** T1, T2, T3.

- [ ] **C1** Confirm all text/result semantics have unit coverage before adding
  filesystem behavior. Record any contract deviation in this plan and obtain
  renewed acceptance for a material spec change.

### P0. Implement accepted agent-runtime nested-argument and multipart-result contracts

**Dependencies:** C1.

**Decision:** Implement the runtime contract selected in
[`ADR 0004`](../adr/0004-use-bounded-multimodal-read-tool-runtime-contracts.md):
generic tool arguments are bounded, immutable recursive JSON values; generic tool
outcomes carry bounded ordered provider-neutral text and image content parts.

**Likely files:**

- `src/fabrica/features/agent_runtime/application/dtos/runtime.py`
- `src/fabrica/features/agent_runtime/application/dtos/tools.py`
- `src/fabrica/features/agent_runtime/application/dtos/__init__.py`
- `src/fabrica/features/agent_runtime/application/ports/registered_tool.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/registered_tool/adapter.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/pydantic_ai_model/tool_aware_agent_model.py`
- `tests/unit/features/agent_runtime/application/test_runtime_dtos.py`
- `tests/unit/features/agent_runtime/application/test_tool_dtos.py`
- `tests/unit/features/agent_runtime/adapters/outbound/registered_tool/test_adapter.py`
- `tests/unit/features/agent_runtime/adapters/outbound/pydantic_ai_model/test_tool_aware_adapter.py`
- `tests/integration/features/agent_runtime/test_tool_loop_composition.py`

**Implementation work:**

- Replace the scalar-only tool-argument contract with a recursive JSON value
  contract that accepts only `null`, booleans, finite numbers, strings, immutable
  sequences, and immutable mappings with string keys.
- Define explicit global bounds for nesting depth, mapping entries, sequence
  entries, and string length; validate values before they reach registered-tool
  handlers and preserve deterministic canonical JSON/digests for duplicate-call
  detection.
- Replace text-only success content with bounded ordered provider-neutral content
  parts. Retain text result/error serialization for statuses and diagnostics, but
  never serialize image bytes into JSON or `result_text`.
- Update registered-tool handler signatures and result mapping to preserve content
  parts, then update PydanticAI argument parsing and `ToolReturnPart` rendering
  at the provider boundary only.

**Acceptance criteria:**

- [ ] **P0.A1** Canonically equivalent nested arguments have the same digest, and
  out-of-bound, non-finite, mutable, or non-JSON values fail before handler
  execution.
- [ ] **P0.A2** A generic runtime result can preserve ordered bounded text and
  verified image content without provider-native DTOs or JSON/base64 image bytes.

**Verification:**

- [ ] **P0.V1** Unit tests cover recursive-value validation, immutability,
  canonicalization, bounds, duplicate-call behavior, and registered-tool mapping.
- [ ] **P0.V2** PydanticAI adapter tests cover nested argument mapping, text-only
  results, ordered text/image returns, and provider-native conversion isolation.
- [ ] **P0.V3** Offline tool-loop integration tests prove structured arguments and
  multipart results pass through the runtime without a live provider.

### T4. Implement capability-gated secure POSIX path resolution and file classification

**Dependencies:** C1.

**Likely files:**

- `src/fabrica/features/workspace_reading/adapters/__init__.py`
- `src/fabrica/features/workspace_reading/adapters/outbound/__init__.py`
- `src/fabrica/features/workspace_reading/adapters/outbound/posix_filesystem/path_resolution.py`
- `src/fabrica/features/workspace_reading/adapters/outbound/posix_filesystem/classification.py`
- `src/fabrica/features/workspace_reading/adapters/outbound/posix_filesystem/capabilities.py`
- `src/fabrica/features/workspace_reading/adapters/outbound/posix_filesystem/__init__.py`
- `scripts/read_files_posix_capability_probe.py`
- `tests/unit/features/workspace_reading/adapters/outbound/posix_filesystem/test_path_resolution.py`
- `tests/unit/features/workspace_reading/adapters/outbound/posix_filesystem/test_classification.py`
- `tests/integration/features/workspace_reading/test_posix_path_resolution.py`

**Implementation work:**

- Reject blank, absolute, and parent-traversal paths.
- Resolve paths relative to the configured workspace and verify containment on
  the exact filesystem object opened for reading.
- On macOS and Linux only, use the capability-gated platform-specific descriptor
  and identity design selected in ADR 0004 to prove containment for the exact
  opened object, including replacement races. Do not use lexical
  `Path.resolve()`-then-`open()` as a substitute for open-time containment.
- Allow symlinks only when the final canonical target is internal and the secure
  descriptor/identity checks prove that target; fail closed on unsupported
  platforms or filesystems rather than weaken this guarantee.
- Classify directories, text, supported images, unsupported binary files,
  UTF-16, invalid UTF-8, permission failures, and missing paths using stable
  result errors.

**Acceptance criteria:**

- [ ] **T4.A1** Escaping symlinks, symlink replacement races, and paths outside
  the workspace are denied unless a host-authorized external-read capability is
  present.
- [ ] **T4.A2** Unsupported POSIX platform or filesystem capabilities return a
  stable fail-closed result instead of falling back to a weaker open sequence.
- [ ] **T4.A3** Image classification uses verified magic bytes rather than only
  filename extensions, and arbitrary binary data is never exposed.

**Verification:**

- [ ] **T4.V1** Integration tests cover nested files, absolute paths, traversal,
  directory requests, allowed internal symlinks, escaping symlinks, and a
  validation-to-open replacement attempt.
- [ ] **T4.V2** Unit tests cover binary, UTF-16, UTF-8-BOM, invalid UTF-8, and
  fake-image classifications.
- [ ] **T4.V3** The macOS/Linux capability probe and deterministic secure-open
  test seam prove the required descriptor/identity primitives or verify a
  fail-closed unsupported result.

### T5. Implement streamed UTF-8 text reads and bounded total-line metadata

**Dependencies:** T4.

**Likely files:**

- `src/fabrica/features/workspace_reading/adapters/outbound/posix_filesystem/text_reader.py`
- `src/fabrica/features/workspace_reading/adapters/outbound/posix_filesystem/adapter.py`
- `tests/unit/features/workspace_reading/adapters/outbound/posix_filesystem/test_text_reader.py`
- `tests/integration/features/workspace_reading/test_posix_text_reader.py`

**Implementation work:**

- Reject text files over 100 MB before reading full content.
- Stream text, skip preceding lines, capture only the requested/allowed window,
  and close handles immediately after enough information is known.
- Calculate total lines only until EOF or the 50,000-line scan ceiling; return an
  inexact lower-bound total when the ceiling is reached.
- Preserve line numbering for UTF-8 BOM, CRLF, Unicode, empty, and
  no-terminal-newline files.

**Acceptance criteria:**

- [ ] **T5.A1** Narrow reads do not load an eligible large file into memory.
- [ ] **T5.A2** Exact total-line metadata is returned only when EOF is reached
  within the scan ceiling.

**Verification:**

- [ ] **T5.V1** Integration tests cover basic text shapes, ranges past EOF,
  start past EOF, output/line caps, large-line truncation, 100 MB boundary, and
  50,000-line metadata boundary.

### C2. Secure text-read checkpoint

**Dependencies:** T4, T5.

- [ ] **C2** Confirm all secure text-read acceptance scenarios pass before
  exposing the tool to the runtime.

### T6. Implement supervised helper-process batch execution, cancellation, deadlines, and retry

**Dependencies:** C2.

**Decision:** Use the supervised helper-process execution model selected in
[`ADR 0004`](../adr/0004-use-bounded-multimodal-read-tool-runtime-contracts.md).
The parent process owns scheduling, cancellation, deadline budgeting, helper
termination, and bounded join; a helper owns one isolated filesystem read attempt.

**Likely files:**

- `src/fabrica/features/workspace_reading/application/use_cases/read_files.py`
- `src/fabrica/features/workspace_reading/application/read_execution.py`
- `src/fabrica/features/workspace_reading/adapters/outbound/posix_filesystem/helper_process.py`
- `tests/unit/features/workspace_reading/application/test_read_files.py`
- `tests/integration/features/workspace_reading/test_read_cancellation_and_timeouts.py`

**Implementation work:**

- Limit batches to 20 requests and active reads to 8.
- Preallocate/index outcomes so results always remain in request order even if
  reads complete in a different order.
- Preserve successful results when sibling requests fail.
- Send only bounded, serializable request/context data to one supervised helper
  process per read attempt; receive only bounded, serializable one-request
  outcomes. The helper must not schedule sibling work.
- Stop active helpers, prevent queued work from starting after cancellation, then
  terminate and join affected helpers before returning the tool result.
- Enforce per-file and total deadlines supplied by composition. Each retry uses
  only the remaining per-file and tool deadline budget.
- Retry only classified transient I/O errors once; never retry deterministic
  input, containment, type, encoding, or missing-file errors.
- Own all batch scheduling, retry classification, cancellation propagation, and
  deadline budgeting in this task. The POSIX adapter returns one-request
  outcomes; it must not independently schedule sibling work.

**Acceptance criteria:**

- [x] **T6.A1** A mixed batch returns a corresponding ordered success/error
  result for every request.
- [x] **T6.A2** Cancellation and timeout cleanup complete before the tool returns.
- [x] **T6.A3** A blocked helper cannot outlive the documented bounded termination
  and join period, and a timeout or cancellation never starts queued work.

**Verification:**

- [x] **T6.V1** Fake-port tests prove concurrency caps, ordering, partial
  success, retry classification, and queued-work suppression.
- [x] **T6.V2** Integration tests verify large-stream cancellation and blocked
  read timeout cleanup, including helper termination and join.

### T7. Implement verified provider-neutral image reading

**Dependencies:** T4, T6.

**Likely files:**

- `src/fabrica/features/workspace_reading/adapters/outbound/posix_filesystem/image_reader.py`
- `tests/unit/features/workspace_reading/adapters/outbound/posix_filesystem/test_image_reader.py`
- `tests/integration/features/workspace_reading/test_posix_image_reader.py`

**Implementation work:**

- Support only PNG, JPEG, GIF, and WebP after magic-byte verification.
- Enforce the 10 MB image limit and host-provided model image-input capability.
- Return verified provider-neutral `ImageContent`; keep any base64/native-provider
  encoding behind a provider adapter.

**Acceptance criteria:**

- [x] **T7.A1** Unsupported, oversized, fake-extension, and image-input-disabled
  cases return stable errors without falling back to text.
- [x] **T7.A2** No core DTO or port refers to a provider-native multimodal type.

**Verification:**

- [x] **T7.V1** Add unit/integration coverage for PNG, JPEG, GIF, WebP, invalid
  magic bytes, capability denial, and image size denial.

### T8. Add the canonical `read_files` registered-tool adapter

**Dependencies:** P0, T6, T7.

**Likely files:**

- `src/fabrica/features/workspace_reading/adapters/inbound/__init__.py`
- `src/fabrica/features/workspace_reading/adapters/inbound/registered_tool/adapter.py`
- `src/fabrica/features/workspace_reading/adapters/inbound/registered_tool/__init__.py`
- `tests/unit/features/workspace_reading/adapters/inbound/registered_tool/test_adapter.py`

**Implementation work:**

- Define `read_files` and the exact accepted schema: a required one-to-twenty
  `files` array, each with required `path` and optional nullable inclusive
  integer bounds; reject additional properties.
- Use the concise description approved by the specification.
- Map runtime arguments and cancellation into the application use case, serialize
  bounded text/error outcomes, and map ordinary no-mutation read failures to
  recoverable runtime results.
- Return ordered provider-neutral text and verified image content parts using the
  P0 runtime contract; the provider adapter alone performs native multipart
  conversion and image bytes never enter `result_text`.

**Acceptance criteria:**

- [x] **T8.A1** The model sees only one read tool, never `read_file` or
  `read_file_range` variants.
- [x] **T8.A2** Invalid runtime arguments are rejected before use-case execution,
  and the adapter does not access the filesystem directly.

**Verification:**

- [x] **T8.V1** Test schema/description fidelity, argument mapping, text and
  mixed outcomes, invalid arguments, cancellation/error mapping, and output
  bounds.

**Implementation note (August 28, 2026):** The generic runtime multipart bounds
now allow 40 ordered content parts and 48,000 characters per text part. This is
the minimum needed to preserve the accepted 20-file batch and 48,000-character
per-file read-output bounds when image results require both structured metadata
and verified binary image content.

### T9. Add composition-root factory and offline tool-loop integration

**Dependencies:** T8.

**Likely files:**

- `src/fabrica/bootstrap/composition/workspace_reading.py`
- `src/fabrica/bootstrap/composition/__init__.py`
- `src/fabrica/bootstrap/__init__.py`
- Agent-runtime DTO, registered-tool executor, and PydanticAI provider-adapter
  files changed by P0.
- `tests/integration/features/workspace_reading/test_read_files_tool_composition.py`
- Agent-runtime unit and integration tests identified by the P0 decision.
- `tests/unit/test_bootstrap_api.py`

**Implementation work:**

- Create an explicit bootstrap factory analogous to the workspace-editing tool
  factory, receiving workspace root, already-authorized policy, limits, timeout
  configuration, helper-process termination/join configuration, and model image
  capability.
- Assemble the application use case, secure POSIX adapter, and helper-process
  supervisor without reading files, starting helpers, or contacting a provider
  during construction.
- Register the resulting async tool in the existing tool-loop composition and
  confirm a fake model can request it and receive an outcome on its next turn.

**Acceptance criteria:**

- [x] **T9.A1** `agent_runtime` receives an explicit registered tool, not
  filesystem details or provider-specific image logic.
- [x] **T9.A2** Construction is side-effect free.

**Verification:**

- [x] **T9.V1** Bootstrap export tests and offline tool-loop integration tests
  pass.

### C3. Runtime checkpoint

**Dependencies:** T6, T7, T8, T9.

- [x] **C3** Confirm the secure, bounded, offline-testable vertical path works
  from model-facing schema through application contracts to filesystem adapter.

### T10. Update applicable documentation and execute the quality gate

**Dependencies:** C3.

**Likely files:**

- `README.md`, only if the public tool/runtime inventory documents the new
  composition capability.
- `docs/specs/read-files-tool.md`, only for a material implementation-discovered
  contract change that is reviewed and re-confirmed.
- This plan file, with task status and deviations updated during implementation.

**Implementation work:**

- Document only actual implementation behavior, settings, and limitations.
- Do not modify the accepted specification merely to match an implementation
  shortcut; record a deviation and seek re-confirmation instead.
- Update all plan checkboxes and add concise status notes for blockers,
  deviations, or newly discovered work.

**Acceptance criteria:**

- [x] **T10.A1** Public documentation and implementation behavior agree, and no
  unsupported configuration surface is documented.

**Verification:**

- [x] **T10.V1** Run `uv run ruff format .`.
- [x] **T10.V2** Run `uv run ruff check .`.
- [x] **T10.V3** Run `uv run ty check src tests`.
- [x] **T10.V4** Run `uv run pytest`.
- [x] **T10.V5** Run `uv run lint-imports`.

## Risks and controls

| Risk | Control |
| --- | --- |
| Symlink time-of-check/time-of-use escape | Verify containment for the exact filesystem object opened; fail closed if the POSIX platform cannot provide the required guarantee. |
| Large-file reads consume unbounded memory or time | Stream content, enforce file/output/line limits, and cap metadata scans at 50,000 lines. |
| Concurrent completion changes model-visible result order | Associate each task with its input index and format outcomes in original order. |
| Cancellation leaks file handles or starts queued reads | Use cancellation-aware scheduling and context-managed streams; test cleanup and queue suppression. |
| Provider adapter leaks base64 or provider types into the core | Keep `ImageContent` provider-neutral and adapt native multimodal parts only at the provider boundary. |
| Runtime loses structured arguments or image content during adaptation | Complete P0 before implementing the registered-tool adapter; preserve bounded immutable JSON values and ordered provider-neutral content parts without scalar/text compatibility shims. |
| A resolve-then-open implementation permits a replacement race | Use the ADR 0004 macOS/Linux descriptor/identity design and fail closed when its capabilities are unavailable. |
| A blocking local read outlives cancellation or timeout | Use an ADR 0004 supervised helper process, then terminate and join it before returning; test active and queued work separately. |
| Permissive compatibility inputs expand the contract | Keep the public schema canonical; any normalization belongs to an explicit host/provider compatibility layer. |

## Assumptions and accepted decisions

- The accepted specification dated August 27, 2026 is authoritative. Material
  changes require specification update and re-confirmation.
- Fabrica remains a Python 3.13 project using `uv`, `ruff`, `ty`, and `pytest`.
- The existing `workspace_editing` registered-tool and bootstrap patterns are
  implementation references only; no private cross-slice coupling is permitted.
- External-read authorization is host-owned and supplied explicitly at
  composition/invocation time.

The following decisions are accepted in
[`ADR 0004`](../adr/0004-use-bounded-multimodal-read-tool-runtime-contracts.md):

- **D1 — Runtime arguments:** Replace scalar-only registered-tool arguments with
  a bounded immutable recursive JSON value contract. The runtime validates depth,
  container, string, and finite-number limits and uses deterministic canonical
  JSON for duplicate-call digests.
- **D2 — Runtime results:** Extend generic registered-tool outcomes with bounded,
  ordered provider-neutral content parts. Text and verified images remain ordered;
  provider adapters alone create native multipart returns, and image bytes are
  never JSON serialized or included in `result_text`.
- **D3 — Secure POSIX open:** Support macOS and Linux only when a tested,
  platform-specific descriptor/identity design proves that the opened object is
  inside the workspace. Internal symlinks are allowed only when that proof holds;
  unsupported platforms or filesystems fail closed.
- **D4 — Blocking read execution:** Execute each filesystem read attempt in a
  supervised helper process. The parent enforces deadlines, cancellation,
  termination, bounded join, retry budgeting, and queued-work suppression.

## Plan readiness checklist

- [x] **R1** Record D1 through D4 in ADR 0004 and update P0/T4/T6/T8/T9 with the
  chosen designs, affected files, and focused regression checks.
- [x] **R2** Dependencies and checkpoints are ordered from runtime contracts to
  workspace contracts, secure filesystem behavior, and runtime exposure.
- [x] **R3** Each implementation task is small enough for focused review; tasks
  spanning multiple files are grouped by one cohesive responsibility.
- [x] **R4** Scope boundaries, assumptions, risks, and non-goals are documented.
- [x] **R5** The plan describes how progress, scope changes, and discovered work
  must be recorded during implementation.
