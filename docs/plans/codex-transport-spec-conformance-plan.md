# Codex Transport Specification Conformance Plan

## Status

- **Readiness:** Ready.
- **Created:** September 4, 2026.
- **Source of truth:** `docs/specs/codex-transport-spec.md`.
- **Resolved implementation decisions:** A completion `401` or `403` loads
  credentials once and makes one backend request, then returns
  `authentication_failed` without refresh, auth-file reread, or replay. A
  successful SSE completion requires matching `event: response.completed` and
  JSON `"type":"response.completed"` identifiers plus non-whitespace final
  output in that terminal payload. The shared HTTP client owns stream/client
  closure and invokes an adapter-provided async body consumer; a completion POST
  is never retried after body consumption begins.
- **Plan maintenance:** During implementation, update both the Progress Tracking
  item and its matching detailed task checkbox after every completed task,
  validation result, scope change, blocker, or newly discovered work. Keep
  unverified work unchecked.

## Goal

Bring the existing Codex transport implementation into conformance with the
accepted Version 1 transport specification, focusing on strict internal SSE
completion handling and the conservative completion-POST retry policy.

## Audit Findings

The existing implementation already provides a read-only credential adapter,
application-owned ports and DTOs, redaction, normalized outcome categories,
deterministic offline tests, opt-in live validation, and a default completion
retry policy limited to HTTP 429.

The following gaps remain:

1. The current SSE mapper can return success from deltas or
   `response.output_text.done` without proving a recognized
   `response.completed` terminal event.
2. Malformed SSE JSON and unsupported stream payloads are silently skipped
   rather than failing closed as `backend_shape_mismatch`.
3. EOF after partial output, cancellation, read failure, and terminal backend
   errors are not all distinguished from a completed final result.
4. The shared HTTP response abstraction buffers response text, so the Codex
   completion adapter needs a narrow stream-aware execution path to distinguish
   response delivery failure from a completed response.
5. One unit test demonstrates that an injected completion retry policy can
   replay a `503` POST. This contradicts the specification: only HTTP 429 may
   be retried until replay safety is proven.
6. Required regression tests for malformed, partial, terminal-error, and
   unsupported event streams are missing.

## Confirmed Protocol and Execution Decisions

### Completion authentication failure

- Load Codex credentials once at the start of one completion operation.
- On an HTTP `401` or `403`, return `authentication_failed` after one backend
  request.
- Do not refresh credentials, reread `~/.codex/auth.json`, or replay the
  completion request. Direct the operator to run `codex login` through existing
  safe operational guidance.

### Successful SSE completion

- A successful completion requires one terminal SSE frame with both
  `event: response.completed` and a JSON payload whose `type` is
  `response.completed`.
- The terminal payload itself must yield final normalized output containing at
  least one non-whitespace character. Earlier deltas and
  `response.output_text.done` events may inform internal parsing but never prove
  success.
- Comments, blank lines, and empty heartbeat frames may be ignored before the
  terminal frame. Malformed framing, malformed JSON, mismatched terminal
  identifiers, missing terminal output, and unsupported required event shapes
  fail closed as `backend_shape_mismatch`.
- `[DONE]` never proves completion by itself. EOF before the accepted terminal
  frame is `transport_error`, including after valid partial output.

### Stream lifecycle and retry boundary

- The shared async HTTP client owns HTTPX client and response closure. It invokes
  an adapter-provided async body consumer rather than returning a raw HTTPX
  response or stream object.
- The Codex adapter owns internal SSE parsing and maps body read, cancellation,
  and delivery failures to `transport_error`; cancellation must propagate after
  lifecycle cleanup.
- Completion retry eligibility ends before body consumption. Only a complete
  HTTP `429` response received before body consumption may be retried. A
  completion POST is never replayed after body consumption starts or any body
  bytes are delivered.

## Scope

### In scope

- Strict adapter-internal parsing and validation of Codex SSE completion
  responses.
- Narrow streaming support in the reusable async HTTP adapter only if necessary
  to preserve stream-delivery semantics.
- Enforcement that completion POST retries may occur only for HTTP 429.
- Deterministic regression coverage for stream and retry failure cases.
- Documentation alignment where the implementation-status wording or operational
  instructions require correction.

### Out of scope

- OAuth refresh or modification of `~/.codex/auth.json`.
- Incremental streaming APIs outside the Codex outbound adapter.
- New CLI options, public configuration, dependencies, or provider APIs.
- Billing, pricing, quota-attribution, or subscription-billing claims.
- Full PydanticAI model implementation or agent orchestration work.
- Live backend calls as part of default tests or CI.

## Progress Tracking

- [x] **CTSC-1** Define and test strict SSE completion parsing.
- [x] **CTSC-2** Add the minimum stream-aware HTTP execution capability.
- [x] **CTSC-3** Integrate strict streaming completion handling in the Codex adapter.
- [x] **CTSC-4** Enforce the completion POST retry invariant.
- [x] **CTSC-5** Add credential-load and authentication no-replay regressions.
- [x] **CTSC-6** Align documentation and run full validation.
- [x] **CTSC-C1** Checkpoint: deterministic stream conformance tests pass.
- [x] **CTSC-C2** Checkpoint: full offline quality gate passes.
- [x] **CTSC-C3** Checkpoint: optional live validation is documented as manual and opt-in.

## Dependency Graph and Sequencing

```text
Strict SSE contract tests (CTSC-1)
  -> stream-aware HTTP capability, if required (CTSC-2)
    -> Codex adapter integration (CTSC-3)
      -> completion retry restriction (CTSC-4)
        -> credential/no-replay integration regression (CTSC-5)
          -> docs and full validation (CTSC-6)
```

The parser contract must be established before changing transport execution so
that shared HTTP work remains narrowly scoped. The completion retry restriction
must follow adapter integration because it applies specifically to the final
completion execution path, not the usage probe path.

## Detailed Tasks

### CTSC-1 — Define and test strict SSE completion parsing

- [x] **CTSC-1** Implement a stateful, adapter-internal SSE parser that accepts
  only known successful completion shapes and requires a recognized terminal
  `response.completed` event plus non-empty final normalized output.

**Likely files**

- `src/fabrica/features/codex_transport/adapters/outbound/codex_backend_http/response_mapping.py`
- Optionally a focused sibling parser module under the same adapter package if
  this keeps responsibilities clearer.
- `tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_response_mapper.py`

**Implementation requirements**

- Preserve the application boundary: no SSE event, stream object, private
  backend payload, or partial output may escape the outbound adapter.
- Treat malformed SSE framing, malformed `data:` JSON, and unsupported required
  event shapes as `backend_shape_mismatch`.
- Require matching `event: response.completed` and JSON
  `"type":"response.completed"` on the successful terminal frame.
- Extract final output only from that terminal payload and reject missing,
  empty, or whitespace-only output as `backend_shape_mismatch`.
- Ignore only comments, blank lines, and empty heartbeat frames before terminal
  completion; do not silently ignore malformed or unsupported required frames.
- Treat terminal backend error events as non-success outcomes without output.
- Treat EOF before a recognized successful terminal completion as
  `transport_error`, even if deltas or done-text were received.
- Do not accept `[DONE]` alone as proof of a completed response unless it is
  explicitly part of an accepted completed response shape.
- Retain only bounded, redacted observations; do not expose raw stream data.

**Acceptance criteria**

- [x] **CTSC-1-A** Valid accepted event streams with a terminal completed event
  and non-empty final output return `success`.
- [x] **CTSC-1-B** No non-success result contains `output_text`.
- [x] **CTSC-1-C** Invalid JSON, malformed framing, and unsupported required
  shapes return `backend_shape_mismatch`.
- [x] **CTSC-1-D** Partial EOF and terminal failure conditions return a
  non-success status without partial text.
- [x] **CTSC-1-E** Mismatched SSE/JSON terminal identifiers and whitespace-only
  terminal output return `backend_shape_mismatch` without partial text.

**Verification**

```bash
uv run pytest tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_response_mapper.py
```

### CTSC-2 — Add the minimum stream-aware HTTP execution capability

- [x] **CTSC-2** Add an additive, transport-neutral async HTTP capability only
  as necessary for the Codex adapter to consume completion streams fully and
  distinguish a completed stream from read, cancellation, and delivery failure.

**Likely files**

- `src/fabrica/adapters/outbound/httpx_client/contracts.py`
- `src/fabrica/adapters/outbound/httpx_client/async_client.py`
- `src/fabrica/adapters/outbound/httpx_client/async_executor.py`
- `tests/unit/adapters/outbound/httpx_client/test_async_client.py`
- `tests/unit/adapters/outbound/httpx_client/test_async_executor.py`

**Implementation requirements**

- Keep the existing non-streaming `AsyncHttpxRetryClient.request()` behavior
  compatible for current callers.
- Do not add Codex-specific names, headers, payloads, or status concepts to the
  shared HTTP package.
- Preserve request-local retry diagnostics and time budgets.
- Keep HTTPX client and response closure in the shared HTTP client and provide a
  transport-neutral async body-consumer callback to the owning adapter.
- Make stream read and delivery failures observable as safe, bounded error
  categories for the owning adapter to translate; clean up and re-raise
  cancellation rather than normalizing it as a successful delivery.
- Decide retry eligibility before invoking the body consumer. The shared client
  must not retry after consumption starts or any body bytes are delivered.

**Acceptance criteria**

- [x] **CTSC-2-A** Existing non-streaming HTTP client tests remain unchanged or
  pass with intentional compatible updates.
- [x] **CTSC-2-B** The owning adapter can distinguish completed body delivery
  from body-read or cancellation failure through the transport-neutral callback;
  Codex adapter integration remains CTSC-3 work.
- [x] **CTSC-2-C** The shared HTTP contract remains transport-neutral and does
  not expose private Codex details.
- [x] **CTSC-2-D** The shared HTTP client closes response and client resources on
  successful consumption, read failure, and cancellation, while cancellation is
  propagated.
- [x] **CTSC-2-E** Retry execution cannot replay a request after the body
  consumer has started.

**Verification**

```bash
uv run pytest tests/unit/adapters/outbound/httpx_client
```

### CTSC-3 — Integrate strict streaming completion handling in the Codex adapter

- [x] **CTSC-3** Route only Codex completion POSTs through the new stream-aware
  path, consume the stream inside `CodexBackendHttpAdapter`, and map the final
  outcome through the strict SSE parser.

**Likely files**

- `src/fabrica/features/codex_transport/adapters/outbound/codex_backend_http/adapter.py`
- `src/fabrica/features/codex_transport/adapters/outbound/codex_backend_http/response_mapping.py`
- `tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_adapter.py`
- `tests/integration/features/codex_transport/test_codex_backend_http_adapter.py`

**Implementation requirements**

- Continue using `stream: true` with the current adapter-owned request shape.
- Keep usage-endpoint GET behavior separate and non-streaming unless it already
  needs a shared behavior change for correctness.
- Translate an incomplete/cancelled/failed stream into `transport_error`.
- Translate a fully delivered but unsupported/malformed stream protocol into
  `backend_shape_mismatch`.
- Preserve redacted response observations and retry diagnostics.
- Add offline integration coverage with a true async streamed response rather
  than only a buffered JSON mock: valid completed stream, mid-stream read
  failure, and cancellation must prove result mapping and resource closure.

**Acceptance criteria**

- [x] **CTSC-3-A** The completion adapter returns final output only after valid
  internal stream completion.
- [x] **CTSC-3-B** No raw stream payload, credentials, headers, or partial text
  is exposed in a result or observation.
- [x] **CTSC-3-C** Usage probing continues to function through its existing
  endpoint-specific behavior.
- [x] **CTSC-3-D** A streamed-body failure or cancellation after a successful
  response status returns `transport_error`, excludes output, and does not leak
  raw stream data.

**Verification**

```bash
uv run pytest tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_adapter.py
uv run pytest tests/integration/features/codex_transport/test_codex_backend_http_adapter.py
```

### CTSC-4 — Enforce the completion POST retry invariant

- [x] **CTSC-4** Make the completion retry policy non-bypassable: only HTTP 429
  may be replayed; 5xx responses, HTTP client exceptions, and ambiguous or
  partial stream outcomes remain single-attempt.

**Likely files**

- `src/fabrica/features/codex_transport/adapters/outbound/codex_backend_http/adapter.py`
- `tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_adapter.py`

**Implementation requirements**

- Preserve bounded exponential backoff, jitter, `Retry-After`, and elapsed-time
  budget behavior for HTTP 429 retries.
- Do not allow a caller-provided completion retry policy to make 5xx or
  transport exceptions replayable.
- Permit a completion retry only for a complete HTTP `429` before stream body
  consumption begins; do not retry after any response body bytes are delivered.
- Replace the existing custom-policy `503` replay test with a custom-policy
  `429` retry test.

**Acceptance criteria**

- [x] **CTSC-4-A** A completion HTTP 429 retries within policy limits.
- [x] **CTSC-4-B** Completion 5xx returns after one attempt.
- [x] **CTSC-4-C** Completion transport/read exceptions return after one attempt.
- [x] **CTSC-4-D** Completion results include scalar-safe retry diagnostics:
  attempt count, retry count, final reason, final HTTP status or error type,
  elapsed seconds, and budget exhaustion.

**Verification**

```bash
uv run pytest tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_adapter.py
```

### CTSC-5 — Add credential-load and authentication no-replay regressions

- [x] **CTSC-5** Add deterministic orchestration tests proving that 401 and 403
  load credentials once and make one backend request, without refreshing,
  rereading, or replaying.

**Likely files**

- `tests/unit/features/codex_transport/application/test_complete_with_codex_transport.py`
- `tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_adapter.py`
- `tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_response_mapper.py`

**Test matrix**

| Scenario | Expected normalized result | Output |
| --- | --- | --- |
| Valid final stream | `success` | Complete final text |
| Delta/done text then EOF | `transport_error` | None |
| `[DONE]` without accepted completion | `transport_error` | None |
| Malformed SSE JSON/framing | `backend_shape_mismatch` | None |
| Unsupported required event | `backend_shape_mismatch` | None |
| Terminal backend error event | Non-success | None |
| Empty final output | `backend_shape_mismatch` | None |
| Completion 401/403 | `authentication_failed` | None |
| Completion 429 | Retry only as policy permits | No partial output |
| Completion 5xx/client/stream failure | One attempt | None |
| Mismatched SSE/JSON terminal identifiers | `backend_shape_mismatch` | None |
| Whitespace-only terminal output | `backend_shape_mismatch` | None |

**Acceptance criteria**

- [x] **CTSC-5-A** Tests use only synthetic values and fake HTTP behavior.
- [x] **CTSC-5-B** 401 and 403 each prove a single credential load and a single
  request attempt, with no refresh, auth-file reread, or replay.
- [x] **CTSC-5-C** Tests prove no partial output leaks into every listed
  non-success result category.

**Verification**

```bash
uv run pytest tests/unit/features/codex_transport/application/test_complete_with_codex_transport.py
uv run pytest tests/unit/features/codex_transport/adapters/outbound/codex_backend_http
```

### CTSC-6 — Align documentation and run full validation

- [x] **CTSC-6** Reconcile documentation with the final behavior and execute the
  complete offline quality gate.

**Likely files**

- `docs/specs/codex-transport-spec.md`
- `README.md`
- Any test files changed by CTSC-1 through CTSC-5.

**Implementation requirements**

- Update specification implementation-status wording only if the audit finding
  makes the current wording inaccurate.
- Preserve the current live-validation guidance: `codex login`, explicit opt-in
  execution, secret-safe output, and no billing-source conclusion.
- Do not add examples containing credentials, account identifiers, raw backend
  payloads, private paths, or headers.

**Acceptance criteria**

- [x] **CTSC-6-A** Documentation accurately describes strict final-result-only
  streaming behavior and opt-in operational validation.
- [x] **CTSC-6-B** The default test suite remains offline and credential-free.
- [x] **CTSC-6-C** All required validation commands pass without bypass flags.

**Verification**

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check src tests
uv run lint-imports
uv run pytest
```

## Checkpoints

### CTSC-C1 — Deterministic stream conformance tests

- [x] **CTSC-C1** Complete only after CTSC-1 through CTSC-5 focused tests pass
  and every non-success stream case is proven to exclude partial output.

### CTSC-C2 — Full offline quality gate

- [x] **CTSC-C2** Complete only after formatting, linting, type checking,
  import-linter, and the full default pytest suite pass.

### CTSC-C3 — Opt-in live validation documentation

- [x] **CTSC-C3** Confirm the manual validation procedure remains opt-in and is
  documented without recording sensitive values. If intentionally performed,
  run `codex login` followed by `make test-live-codex`, recording only command
  outcome, normalized status, and bounded redacted observations.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Shared HTTP work expands beyond Codex needs. | Use the transport-neutral async body-consumer callback, preserve shared lifecycle ownership, and limit the new capability to required lifecycle/error information. |
| Private backend event shapes drift. | Fail closed, add a synthetic regression fixture, update this specification, run the offline quality gate, then perform documented opt-in live validation before accepting the new shape. |
| Retry customization accidentally re-enables unsafe completion replay. | Normalize or constrain the completion policy at the Codex adapter boundary, prohibit retries after body consumption begins, and prove both invariants with explicit tests. |
| Stream fixtures expose sensitive information. | Use only synthetic payloads and assert credentials, account values, cookies, headers, URLs, and raw payloads do not appear in observations. |
| Live validation is confused with billing proof. | Preserve README/spec wording that live checks validate technical behavior only, not billing source or pricing attribution. |

## Assumptions

- The confirmed terminal completion rule is sufficient for the first strict
  parser: matching SSE/JSON `response.completed` identifiers and non-whitespace
  final output in the terminal payload.
- Existing application DTO statuses are sufficient; no new public result status
  is required for this conformance work.
- The current `httpx` dependency supports an async streaming path without adding
  dependencies.

## Open Questions

No blocking questions are known. The resolved `401`/`403`, terminal-success, and
stream-lifecycle rules above are authoritative for this implementation plan. During
CTSC-1, document any newly observed event type that cannot be safely classified
using the accepted Version 1 contract. Do not silently accept it; handle it under
the backend drift policy.

## Deferred Work

- Repeated cross-session live technical-viability evidence collection.
- Accepting newly observed backend request, event, error, or rate-limit shapes.
- OAuth refresh, public API compatibility work, incremental streaming APIs,
  custom PydanticAI models, and billing attribution.
