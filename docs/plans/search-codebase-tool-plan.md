# Implementation Plan: Search Codebase Tool

## Overview

Implement the accepted, read-only `search_codebase` tool as the new `workspace_searching` vertical slice. The slice will provide canonical, bounded, deterministic regex source discovery through a Fabrica-distributed, integrity-verified pinned ripgrep payload and will be exposed to models through the existing asynchronous registered-tool runtime.

## Scope

### In scope

- The accepted canonical `{ "queries": [...] }` interface, query/result DTOs, stable errors, validation, path containment, glob/ignore semantics, pinned-backend execution, context hydration, output limiting, cancellation, retries, and tool-loop composition.
- Unit, integration, backend-conformance, and composition coverage required by `docs/specs/tools-search-codebase-tool-spec.md`.
- Bootstrap exports and user-facing README documentation required for a new model-callable workspace tool.

### Out of scope

- Semantic, vector, AST, filename, Git-history, or commit-message search.
- Pagination/cursors, an index, host-installed ripgrep detection, or a fallback regex engine.
- Changing the accepted search contract, silently widening scopes, or refactoring workspace-reading/editing beyond containment infrastructure proven necessary by concrete reuse.

## Assumptions

- The target is the Python 3.13 `src/fabrica` package and POSIX-oriented workspace tooling patterns used by `workspace_reading`.
- `agent_runtime` registered tools continue to accept structured text content and provide cancellation plus phase deadlines through `ToolExecutionContext`.
- The implementation will preserve the specification's August 28, 2026 accepted decisions; discrepancies discovered during implementation require spec clarification, not silent changes.
- Version 1 uses a checksum-verified package-data ripgrep executable in Bubblewrap on Linux `x86_64`, and a locally provisioned digest-verified Fabrica OCI search image in Apple Container on macOS Apple Silicon running macOS 26 or later. Intel macOS and every other OS/architecture combination fail closed without host-binary discovery, fallback, or tool-call-time image pulls.

## Architecture Decisions

- Create `src/fabrica/features/workspace_searching/` as the owning vertical slice. Keep backend invocation in an outbound adapter, core orchestration in application use cases, and model schema normalization/serialization in an inbound registered-tool adapter.
- Use one backend-neutral `SearchLocation` intermediate contract and a common context hydrator; do not couple context semantics to ripgrep JSON context events.
- Establish a platform-specific subprocess-containment boundary that pins ripgrep traversal inside the workspace for the complete search lifetime; a preflight `resolve()` or file-only descriptor check is insufficient. Linux uses Bubblewrap and macOS uses Apple Container as recorded in ADR 0006. Fail closed when the selected runtime or payload is unavailable, and extract shared containment infrastructure only after concrete read/search reuse demonstrates a stable boundary.
- Treat only Fabrica-distributed, integrity-verified ripgrep payloads as Version 1 execution backends: a Linux package-data executable or a macOS OCI image. No host discovery, Python-regex fallback, or tool-call-time image pull is permitted.
- Validate only basic glob shape in application code. Pass globs literally to pinned ripgrep as the grammar authority and map its recognized deterministic syntax failure to `INVALID_GLOB`.
- Serialize the canonical top-level `{ "results": [...] }` object as exactly one `ToolTextContent` part and enforce its 48,000-character aggregate output budget before adapter serialization.

## Progress Tracking

This dashboard mirrors every detailed task, acceptance criterion, verification item, and checkpoint below. Update both copies after every completed task or material scope/sequencing change. Unresolved or unapproved questions remain unchecked and block dependent work.

### Phase 1: Contract and safe search planning

- [x] `T1` — Establish search application contracts, DTOs, limits, validation, and result serialization.
  - [x] `T1-AC1` — Canonical query objects, immutable results, one-based Unicode column semantics, defaults, stable error codes, and all per-query/batch limits are represented and validated.
  - [x] `T1-AC2` — Invalid input and empty patterns produce independent per-query failures without invalidating other batch entries; backend-classified invalid regexes and invalid globs have stable result representations reserved for T3.
  - [x] `T1-V1` — Focused DTO/validator tests pass.
  - [x] `T1-V2` — `uv run ruff check src/fabrica/features/workspace_searching tests/unit/features/workspace_searching` passes.
- [x] `T2` — Define and implement workspace-contained scope resolution plus a fail-closed subprocess-containment boundary.
  - [x] `T2-AC1` — Literal workspace-relative file/directory paths reject absolute paths, traversal, non-filesystem targets, missing paths, and symlink escapes.
  - [x] `T2-AC2` — The selected launch boundary prevents ripgrep from traversing outside the configured workspace for the subprocess lifetime, including after pathname/symlink races; unsupported hosts fail closed before spawning a backend.
  - [x] `T2-V1` — Focused scope and containment-design tests cover the accepted path matrix, launch preconditions, and race/escape regressions.
  - [x] `T2-V2` — POSIX integration tests prove an attempted post-validation escape cannot be searched and unsupported containment capabilities fail closed.
- [x] `CP1` — Application contracts and the concrete subprocess-containment design are reviewed against the accepted spec and ADR 0006 before backend wiring.

### Phase 2: Pinned backend, context, limits, and scheduling

- [ ] `T3` — Package and validate the pinned ripgrep backend; implement incremental JSON-event parsing into backend-neutral locations.
  - [ ] `T3-AC1` — Only the Fabrica-distributed, integrity-verified platform payload may execute; unavailable, malformed, permission, transient I/O, and deterministic regex/glob failures map to stable outcomes.
  - [ ] `T3-AC2` — The adapter passes globs literally to ripgrep as the only grammar authority, applies ignore/hidden/hard-exclude and exact explicit-ignored-file behavior through backend arguments, searches line-oriented Rust-regex semantics, stops at the global matching-line cap without `--max-count=1`, parses incrementally, and terminates subprocesses on cancellation/limit/timeout.
  - [ ] `T3-V1` — Backend argument, glob-diagnostic mapping, parser, process-cleanup, pinned-version, payload-integrity, Linux executable-permission, macOS image-digest, runtime-availability, and platform-selection conformance tests pass.
  - [ ] `T3-V2` — Focused integration tests verify actual contained fixture searches with the platform payload, including ignore/hidden/explicit-file glob behavior.
  - [ ] `T3-V3` — Clean-environment tests install the built wheel and source distribution for Linux verification. Separate macOS Apple Silicon conformance provisions the Fabrica OCI archive, verifies the image digest, and runs a representative contained search through Apple Container.
  - **Implementation status (August 29, 2026):** The Linux-oriented pinned-ripgrep outbound adapter, incremental stdout supervision, result-cap termination, cancellation/timeout cleanup, source hydration, stable failure mapping, and deterministic unit coverage are implemented. The fixed command also disables host ripgrep configuration and parent-ignore discovery. ADR 0006 supersedes the blocked macOS `sandbox-exec` launch profile with Apple Container. T3 remains open until the macOS runtime probe, local OCI-image provisioning and digest verification, fixed read-only container command, workspace scope rewriting, containment regressions, and cross-platform conformance are implemented.
- [x] `T4` — Implement backend-neutral context hydration, Unicode-safe location conversion, deterministic ordering, and complete-object output limiting.
  - [x] `T4-AC1` — Every match returns two bounded before/after lines, matching/context truncation metadata, CRLF/UTF-8 handling, one match per line, and Unicode character columns.
  - [x] `T4-AC2` — Results sort by path/line/column and observe 100-match, 48,000-character/query, and 48,000-character/batch budgets without partial objects; omitted batch entries are explicit.
  - [x] `T4-V1` — Context, long-line, ordering, Unicode, and output-limiter unit tests pass.
  - [x] `T4-V2` — Result JSON contract tests cover success, failure, truncation, and omission fixtures.
- [ ] `T5` — Orchestrate bounded concurrent queries with ordered partial results, deadlines, cancellation, and selective retry.
  - [x] `T5-AC1` — Up to eight input queries execute with at most four active searches and return in input order regardless of completion order.
  - [x] `T5-AC2` — Per-query/tool deadlines cancel active work and queued searches; only adapter-classified transient errors retry once, never deterministic validation failures.
  - [x] `T5-V1` — Scheduler tests cover concurrency, request ordering, mixed failures, cancellation, timeout, and retry classification.
  - [ ] `T5-V2` — Integration tests prove subprocess termination and context-hydration interruption.
- [ ] `CP2` — Search core is acceptance-tested without model-runtime dependencies.

### Phase 3: Model-facing tool and product composition

- [x] `T6` — Add the `search_codebase` registered-tool adapter and bootstrap factory.
  - [x] `T6-AC1` — The public `ToolDefinition` advertises only the canonical schema and concise accepted description; adapter-only compatibility normalization, if retained, never reaches the core.
  - [x] `T6-AC2` — Adapter maps runtime cancellation/deadlines to search context, serializes stable ordered structured JSON, declares no mutation, and converts malformed top-level arguments to recoverable rejection.
  - [x] `T6-V1` — Registered-tool adapter unit tests cover schema, canonical/compatibility inputs, context mapping, and serialized outcomes.
  - [x] `T6-V2` — Offline tool-loop composition test invokes the explicitly composed tool after construction without workspace inspection at construction time.
- [ ] `T7` — Complete public exports, documentation, and final validation.
  - [x] `T7-AC1` — Bootstrap composition and public exports expose the explicit search-tool factory without changing unrelated tool registration.
  - [x] `T7-AC2` — README explains host composition and intended search-to-read workflow; specs documentation index remains accurate.
  - [ ] `T7-AC3` — Build configuration includes the Linux executable/checksum metadata and the macOS OCI archive/digest metadata; Linux clean-install and macOS Apple Container conformance are manually run on their respective supported platforms.
  - [x] `T7-V1` — `uv run ruff format .` and `uv run ruff check .` pass.
  - [x] `T7-V2` — `uv run ty check src tests` and `uv run pytest` pass.
  - [x] `T7-V3` — Import-linter/project checks configured by the repository pass, and the final diff contains only intentional implementation, test, packaging, and docs changes.
  - [ ] `T7-V4` — `uv build` succeeds, Linux wheel/source-distribution checks pass on Linux `x86_64`, and macOS Apple Container image/runtime conformance passes on macOS Apple Silicon.

### Completion

- [ ] `CP-FINAL-1` — All required acceptance criteria above are met.
- [ ] `CP-FINAL-2` — Focused checks and the full quality gate pass with no unapproved failures.
- [ ] `CP-FINAL-3` — Open questions are resolved or explicitly approved for deferral; the change is ready for review.

## Task List

### Phase 1: Contract and safe search planning

#### Task 1: Establish search application contracts and pure validation

**Task completion:**

- [x] `T1` — All required acceptance and verification items are resolved.

**Description:** Define immutable search DTOs, error taxonomy, defaults/limits, application ports, canonical query validation, structural-only glob validation, and pure output-size accounting before any process execution. Ripgrep remains the sole glob grammar authority; this task must not implement or classify glob syntax beyond structural input constraints.

**Acceptance criteria:**

- [x] `T1-AC1` — Canonical query objects, immutable results, one-based Unicode column semantics, defaults, stable error codes, and all per-query/batch limits are represented and validated.
- [x] `T1-AC2` — Invalid input and empty patterns produce independent per-query failures without invalidating other batch entries; backend-classified invalid regexes and invalid globs have stable result representations reserved for T3.

**Verification:**

- [x] `T1-V1` — Focused DTO/validator tests pass.
- [x] `T1-V2` — `uv run ruff check src/fabrica/features/workspace_searching tests/unit/features/workspace_searching` passes.

**Dependencies:** None.

**Files likely touched:**

- `src/fabrica/features/workspace_searching/application/dtos/search_codebase.py`
- `src/fabrica/features/workspace_searching/application/ports/workspace_searching.py`
- `src/fabrica/features/workspace_searching/application/validation.py`
- `src/fabrica/features/workspace_searching/application/output_limiting.py`
- `tests/unit/features/workspace_searching/application/test_search_codebase_dtos.py`
- `tests/unit/features/workspace_searching/application/test_validation.py`

**Estimated scope:** M — isolated pure contracts with a large acceptance matrix.

#### Task 2: Define and implement contained search scopes and subprocess launch boundary

**Task completion:**

- [x] `T2` — All required acceptance and verification items are resolved.

**Description:** Implement search-specific workspace path resolution and a concrete, lifecycle-long containment mechanism for the ripgrep subprocess. A preflight canonical-path check, a file-only descriptor opener, or `rg --no-follow` alone is not sufficient because directory contents can change after validation. Select a supported POSIX mechanism that prevents all backend traversal outside the pinned workspace, document its ownership and failure mode, and fail closed before launch when the guarantee cannot be provided. Reuse or extract containment infrastructure only after the read/search use cases demonstrate a stable shared boundary; do not migrate `workspace_editing` merely for symmetry.

**Acceptance criteria:**

- [x] `T2-AC1` — Literal workspace-relative file/directory paths reject absolute paths, traversal, non-filesystem targets, missing paths, and symlink escapes.
- [x] `T2-AC2` — The launch boundary prevents backend traversal outside the configured workspace for the complete subprocess lifetime, including pathname replacement and symlink-race attempts; unsupported hosts return `SEARCH_BACKEND_UNAVAILABLE` without spawning ripgrep.

**Verification:**

- [x] `T2-V1` — Focused path/containment tests cover the accepted scope matrix, launch preconditions, and escape/race regressions.
- [x] `T2-V2` — POSIX integration tests prove an attempted post-validation escape cannot be searched and that unsupported containment capabilities fail closed.

**Dependencies:** T1; accepted containment mechanism recorded in OQ1.

**Files likely touched:**

- `docs/adr/<next-number>-pin-search-subprocess-workspace-containment.md`
- `src/fabrica/features/workspace_searching/application/search_planning.py`
- `src/fabrica/features/workspace_searching/adapters/outbound/posix_filesystem/path_resolution.py`
- `src/fabrica/features/workspace_searching/adapters/outbound/posix_filesystem/search_sandbox.py`
- Potentially a narrowly extracted shared read/search containment module and corresponding reading imports.
- `tests/unit/features/workspace_searching/.../test_path_resolution.py`
- `tests/integration/features/workspace_searching/test_posix_search_scope.py`

**Estimated scope:** L — security-sensitive launch guarantee and possible concrete read/search reuse extraction.

### Checkpoint: Core boundary and planner review

- [ ] `CP1` — Application contracts and secure search planning are reviewed against the accepted spec before backend wiring.

### Phase 2: Pinned backend, context, limits, and scheduling

#### Task 3: Add the pinned ripgrep adapter and streaming parser

**Task completion:**

- [ ] `T3` — All required acceptance and verification items are resolved.

**Description:** Establish reproducible distribution/startup validation paths for the accepted ripgrep payloads, then implement an outbound adapter that launches only the Linux executable in Bubblewrap or the macOS OCI image in Apple Container. It must pass globs literally as ripgrep's sole grammar authority, stream JSON events, yield locations, and perform prompt process cleanup.

**Acceptance criteria:**

- [ ] `T3-AC1` — Only the Fabrica-distributed, integrity-verified platform payload may execute; unavailable, malformed, permission, transient I/O, and deterministic regex/glob failures map to stable outcomes.
- [ ] `T3-AC2` — The adapter passes globs literally to ripgrep as the only grammar authority, applies ignore/hidden/hard-exclude and exact explicit-ignored-file behavior through backend arguments, searches line-oriented Rust-regex semantics, stops at the global matching-line cap without `--max-count=1`, parses incrementally, and terminates subprocesses on cancellation/limit/timeout.

**Verification:**

- [ ] `T3-V1` — Backend argument, glob-diagnostic mapping, parser, process cleanup, pinned-version, Linux checksum/executable-permission, macOS image-digest/runtime-availability, and platform-selection conformance tests pass.
- [ ] `T3-V2` — Focused integration tests verify actual contained fixture searches with each platform payload, including ignore/hidden/explicit-file glob behavior.
- [ ] `T3-V3` — Linux clean-environment tests install both built distributions, verify the executable/checksum metadata, and run a representative search. macOS Apple Silicon tests provision the Fabrica OCI archive, verify its selected digest, and run a representative contained Apple Container search.

**Implementation status (August 29, 2026):**

- Implemented `PinnedRipgrepWorkspaceSearchBackend` with verified-command construction, incremental JSON-lines collection, bounded matching-line termination, cancellation/timeout cleanup, source loading, context hydration, and stable error mapping.
- Added deterministic adapter tests for successful hydration, invalid regex/glob diagnostics, transient I/O, cancellation, timeout, malformed output, source containment, output caps, and macOS/Linux cleanup paths.
- Added `--no-config` and `--no-ignore-parent` to fixed ripgrep arguments so host configuration and ancestor ignore discovery cannot alter search behavior.
- Full local quality evidence passed on August 29, 2026: formatting, linting, `ty`, import-linter, `pytest` (1,276 passed, 2 skipped, 93.03% coverage), and `uv build`.
- Do not check T3 complete: ADR 0006 superseded the blocked macOS `sandbox-exec` design. Implement and verify Apple Container runtime detection, explicitly provisioned local OCI-image availability, digest verification, a fixed read-only workspace mount, `/workspace` scope rewriting, cancellation/timeout cleanup, and real contained fixture searches before closing T3.

**Dependencies:** T1 and T2.

**Files likely touched:**

- `pyproject.toml` and `uv.lock` for mandatory wheel/source-distribution package-data configuration and test tooling.
- `src/fabrica/features/workspace_searching/adapters/outbound/pinned_ripgrep/manifest.py`
- `src/fabrica/features/workspace_searching/adapters/outbound/pinned_ripgrep/adapter.py`
- `src/fabrica/features/workspace_searching/adapters/outbound/ripgrep_binaries/**`
- `src/fabrica/features/workspace_searching/adapters/outbound/ripgrep_binaries/sha256.json`
- `src/fabrica/features/workspace_searching/adapters/outbound/apple_container/**`
- `src/fabrica/features/workspace_searching/adapters/outbound/search_images/**`
- `src/fabrica/features/workspace_searching/adapters/outbound/pinned_ripgrep/json_parser.py`
- `src/fabrica/features/workspace_searching/adapters/outbound/pinned_ripgrep/packaging.py`
- `tests/unit/features/workspace_searching/adapters/outbound/pinned_ripgrep/test_json_parser.py`
- `tests/integration/features/workspace_searching/test_pinned_ripgrep_adapter.py`
- `tests/integration/features/workspace_searching/test_search_distribution_artifacts.py`

**Estimated scope:** L — requires deliberate artifact distribution and subprocess lifecycle design.

#### Task 4: Hydrate context and enforce deterministic complete-object limits

**Task completion:**

- [x] `T4` — All required acceptance and verification items are resolved.

**Description:** Convert streamed locations into the canonical model-facing matches through shared context hydration, Unicode-safe column normalization, line truncation, deterministic sorting, and per-query/aggregate serialization-budget enforcement.

**Acceptance criteria:**

- [x] `T4-AC1` — Every match returns two bounded before/after lines, matching/context truncation metadata, CRLF/UTF-8 handling, one match per line, and Unicode character columns.
- [x] `T4-AC2` — Results sort by path/line/column and observe 100-match, 48,000-character/query, and 48,000-character/batch budgets without partial objects; omitted batch entries are explicit.

**Verification:**

- [x] `T4-V1` — Context, long-line, ordering, Unicode, and output-limiter unit tests pass.
- [x] `T4-V2` — Result JSON contract tests cover success, failure, truncation, and omission fixtures.

**Dependencies:** T1–T3.

**Files likely touched:**

- `src/fabrica/features/workspace_searching/application/context_hydration.py`
- `src/fabrica/features/workspace_searching/application/result_limiting.py`
- `src/fabrica/features/workspace_searching/application/result_formatting.py`
- `tests/unit/features/workspace_searching/application/test_context_hydration.py`
- `tests/unit/features/workspace_searching/application/test_result_limiting.py`

**Estimated scope:** M — pure/controlled filesystem logic with precise byte-versus-character accounting.

#### Task 5: Orchestrate concurrent, cancellable query execution

**Task completion:**

- [ ] `T5` — All required acceptance and verification items are resolved.

**Description:** Implement the search use case using the established `workspace_reading` scheduler style: bounded active tasks, earliest host/configured deadline, ordered per-query outcomes, cancellation cleanup, and selective transient retry.

**Acceptance criteria:**

- [x] `T5-AC1` — Up to eight input queries execute with at most four active searches and return in input order regardless of completion order.
- [x] `T5-AC2` — Per-query/tool deadlines cancel active work and queued searches; only adapter-classified transient errors retry once, never deterministic validation failures.

**Verification:**

- [x] `T5-V1` — Scheduler tests cover concurrency, request ordering, mixed failures, cancellation, timeout, and retry classification.
- [ ] `T5-V2` — Integration tests prove subprocess termination and context-hydration interruption.

**Dependencies:** T1–T4.

**Files likely touched:**

- `src/fabrica/features/workspace_searching/application/use_cases/search_codebase.py`
- `src/fabrica/features/workspace_searching/application/ports/workspace_searching.py`
- `tests/unit/features/workspace_searching/application/test_search_codebase.py`
- `tests/integration/features/workspace_searching/test_search_cancellation_and_timeouts.py`

**Estimated scope:** M — concurrency behavior follows an established sibling pattern but has backend process cleanup requirements.

### Checkpoint: Search-core acceptance review

- [ ] `CP2` — Search core is acceptance-tested without model-runtime dependencies.

### Phase 3: Model-facing tool and product composition

#### Task 6: Expose search as a registered tool and compose it explicitly

**Task completion:**

- [x] `T6` — All required acceptance and verification items are resolved.

**Description:** Add the inbound tool adapter beside `workspace_reading`'s registered adapter and a bootstrap factory. Keep canonical schema/arguments core-facing and localize any Cline compatibility normalization in this adapter only.

**Acceptance criteria:**

- [x] `T6-AC1` — The public `ToolDefinition` advertises only the canonical schema and concise accepted description; adapter-only compatibility normalization, if retained, never reaches the core.
- [x] `T6-AC2` — Adapter maps runtime cancellation/deadlines to search context, serializes stable ordered structured JSON, declares no mutation, and converts malformed top-level arguments to recoverable rejection.

**Verification:**

- [x] `T6-V1` — Registered-tool adapter unit tests cover schema, canonical/compatibility inputs, context mapping, and serialized outcomes.
- [x] `T6-V2` — Offline tool-loop composition test invokes the explicitly composed tool after construction without workspace inspection at construction time.

**Dependencies:** T1–T5.

**Files likely touched:**

- `src/fabrica/features/workspace_searching/adapters/inbound/registered_tool/adapter.py`
- `src/fabrica/bootstrap/composition/workspace_searching.py`
- `src/fabrica/bootstrap/composition/__init__.py`
- `src/fabrica/bootstrap/__init__.py`
- `tests/unit/features/workspace_searching/adapters/inbound/registered_tool/test_adapter.py`
- `tests/integration/features/workspace_searching/test_search_codebase_tool_composition.py`

**Estimated scope:** M — established registered-tool and composition patterns minimize new runtime surface.

#### Task 7: Finalize exports, documentation, and quality evidence

**Task completion:**

- [ ] `T7` — All required acceptance and verification items are resolved.

**Description:** Complete package exports and project-facing documentation, add manually invoked package-data/build-artifact verification for each supported platform, run the full quality gate, inspect the final diff, and record any approved deviations or deferred decisions.

**Acceptance criteria:**

- [x] `T7-AC1` — Bootstrap composition and public exports expose the explicit search-tool factory without changing unrelated tool registration.
- [x] `T7-AC2` — README explains host composition and intended search-to-read workflow; specs documentation index remains accurate.
- [ ] `T7-AC3` — Build configuration includes the Linux executable/checksum metadata and macOS OCI archive/digest metadata; platform conformance is manually run on Linux `x86_64` and macOS Apple Silicon.

**Verification:**

- [x] `T7-V1` — `uv run ruff format .` and `uv run ruff check .` pass.
- [x] `T7-V2` — `uv run ty check src tests` and `uv run pytest` pass.
- [x] `T7-V3` — Import-linter/project checks configured by the repository pass, and the final diff contains only intentional implementation, test, packaging, and docs changes.
- [ ] `T7-V4` — `uv build` succeeds, Linux wheel/source-distribution checks pass on Linux `x86_64`, and Apple Container image/runtime conformance passes on macOS Apple Silicon.

**Dependencies:** T6.

**Files likely touched:**

- `README.md`
- `docs/README.md`
- `src/fabrica/features/workspace_searching/**/__init__.py`
- `tests/unit/test_bootstrap_api.py`
- `pyproject.toml` and `uv.lock` for Linux package-data plus macOS OCI-image packaging/build-test configuration.
- `tests/integration/features/workspace_searching/test_search_distribution_artifacts.py` for Linux distribution conformance.
- `tests/integration/features/workspace_searching/test_apple_container_search.py` for manually invoked macOS Apple Silicon runtime/image conformance.

**Estimated scope:** S — integration/documentation closeout after the core is complete.

### Checkpoint: Complete

- [ ] `CP-FINAL-1` — All acceptance criteria met.
- [ ] `CP-FINAL-2` — Focused and full validation passes or is explicitly approved as not applicable; no required check remains unknown.
- [ ] `CP-FINAL-3` — Ready for review.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Vendored ripgrep artifacts or the macOS OCI image are selected, modified, or omitted incorrectly. | High | Commit Linux SHA-256 and macOS OCI digest metadata, package both platform payloads intentionally, fail closed when unavailable or unverifiable, and run platform-specific conformance coverage. |
| A validated path is replaced before or during ripgrep traversal, allowing an escape from the workspace. | High | Select a lifecycle-long POSIX subprocess-containment mechanism before backend wiring, fail closed when unavailable, and prove post-validation pathname/symlink races cannot be searched. |
| Ripgrep byte offsets, Python Unicode indexing, CRLF handling, and truncation budgets diverge. | High | Centralize conversion/hydration and test Unicode prefixes, CRLF fixtures, and serialized output boundaries. |
| Killing a subprocess on result caps/cancellation can leak handles or leave child processes. | High | Make lifecycle ownership explicit; test cancellation, timeout, cap stop, and cleanup deterministically. |
| Ignore/glob parity varies if host shell or filesystem traversal leaks into semantics. | Medium | Pass literal arguments only, use tool-evaluated ripgrep grammar, and fixture-test ignore/hidden/explicit-file cases. |
| One-part runtime output limits conflict with batched structured search output. | Medium | Enforce the 48,000-character aggregate serialized-output cap before producing the sole `ToolTextContent` part and cover its boundary in adapter tests. |

## Resolved Decisions

- [x] **OQ1 — Search subprocess containment:** Linux uses Bubblewrap. macOS Apple Silicon on macOS 26 or later uses Apple Container with a read-only `/workspace` mount, as recorded in ADR 0006. Unsupported or unavailable containment fails closed.
- [x] **OQ2 — Pinned ripgrep packaging:** Ship the Linux executable as wheel/source-distribution package data with SHA-256 metadata. Provision the macOS digest-pinned OCI image explicitly from a Fabrica-distributed archive or equivalent operator workflow; Version 1 never discovers, falls back to, or pulls host/registry `rg` during a tool call.
- [x] **OQ3 — Glob validation implementation:** Validate basic shape locally, pass globs literally to pinned ripgrep, and map its recognized deterministic syntax error to `INVALID_GLOB`; no host-shell expansion or approximate independent parser.
- [x] **OQ4 — Runtime output representation:** Return one `ToolTextContent` part containing the complete canonical top-level `{ "results": [...] }` object and limit its aggregate serialized output to 48,000 characters.
- [x] **OQ5 — Packaging/CI targets:** Support macOS Apple Silicon on macOS 26 or later and Linux `x86_64` only. Linux validates the package-data executable; macOS validates Apple Container runtime plus OCI image conformance. Intel macOS is out of scope.
