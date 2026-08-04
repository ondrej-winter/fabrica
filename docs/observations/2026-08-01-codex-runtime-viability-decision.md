# Codex runtime viability decision: 2026-08-01

This note records the current viability decision for the subscription-backed
Python agent runtime evidence gate. It is based on repository documentation,
synthetic/offline implementation evidence, and the dated source-comparison notes
in `docs/observations/README.md`. It does not include new live backend
validation beyond the redacted collection note listed below.

## Decision label

`conditional_go`

## Observed facts

- Existing default tests and quality gates remain designed to run offline without
  reading real Codex credentials or calling the live Codex backend.
- Existing manual live validation paths are explicit and opt-in:
  `make test-live-codex`, `make test-live-runtime`,
  `make run-live-cli PROMPT="..."`, and
  `FABRICA_RUN_LIVE_CODEX_TESTS=1 uv run pytest -m live_codex`.
- The observation schema and repeated-session procedure require at least two
  successful live runs across separate local sessions before `go` or
  `conditional_go` can be recommended.
- The current source comparison is dated 2026-08-01 and records local
  `codex-cli 0.146.0` plus project source/spec observations for the private
  Codex backend shape.
- Public OpenAI Responses API documentation could not be consulted during the
  source-comparison pass because the documentation endpoint returned HTTP `403`
  with an edge challenge.
- The redacted collection note records two successful live validation runs across
  separately labeled local sessions.
- `2026-08-01-redacted-live-evidence-collection.md` records explicitly requested
  `session-1` and `session-2` live transport, runtime, and CLI successes with
  bounded expected output `pong`.
- No reactive auth, quota/rate-limit, backend-shape, or transport failure was
  observed during those successful validation runs.
- Exact per-session, per-call, or billing-attribution telemetry is not expected
  to be available for the subscription-backed path.

## Evidence gaps

- Exact reactive usage/quota telemetry or a safe quota-signal observation is not
  recorded beyond successful responses without quota/rate-limit failures.
- Billing attribution remains unresolved and is expected to stay ambiguous unless
  a safe external account observation is available.
- Public Responses API comparison remains source-limited until official docs can
  be consulted or another authoritative source is recorded.
- Private backend request and response behavior remains volatile and could change
  independently of this project.

## Interpretation

The current implementation and documentation now contain enough redacted live
evidence to support a bounded `conditional_go` recommendation for deeper runtime
work. Repeated live transport, runtime, and CLI validation succeeded across two
separately labeled local sessions, with no observed auth, quota/rate-limit,
backend-shape, or transport failures.

This decision does not imply that the direct Codex backend path is broken. It
only means the project still cannot claim stable private-backend compatibility,
public API equivalence, or precise subscription billing attribution.

## Follow-up recommendation

Proceed only with bounded follow-up runtime planning or implementation while
preserving the documented caveats:

1. Keep live validation opt-in and outside default tests/CI.
2. Continue recording only bounded observations in dated notes.
3. Treat billing attribution as unavailable or ambiguous unless a safe external
   account observation is available.
4. Revisit the decision label if reactive auth, quota/rate-limit, backend-shape,
   or transport failures appear.
5. Prefer narrow follow-up slices such as runtime ergonomics, transport
   hardening, or streaming/tool-loop planning rather than broad capability
   expansion.

Because repeated live evidence succeeded while public documentation remains
blocked and billing attribution remains ambiguous, the decision is
`conditional_go`, not `go`. If authentication, backend-shape, quota/rate-limit,
transport, billing-attribution contradiction, or safety failures later block the
direct path, update the decision to `no_go` and route follow-up work to transport
hardening or a documentation-only pause.

## Unresolved questions preserved

- Which private Codex backend headers are strictly required rather than
  incidental to the observed CLI behavior?
- Which reactive usage/quota signals appear as safe status codes, headers, or
  error messages without exposing account details or private backend payloads?
- Can official public Responses API documentation be consulted successfully for a
  stronger compatibility comparison?
- Can any safe external account observation distinguish subscription-backed usage
  from public OpenAI API billing, or should billing attribution remain explicitly
  ambiguous?
- Which normalized failure categories appear during repeated live validation, if
  any?
