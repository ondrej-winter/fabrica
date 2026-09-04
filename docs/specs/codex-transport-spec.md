# Spec: Codex Transport

## Status

- State: Accepted and implemented — Version 1 technical contract.
- Implementation status: Substantially implemented; this accepted specification reconciles the existing Version 1 boundary.
- Accepted by: Maintainer
- Accepted on: September 4, 2026
- Revision: Accepted Version 1 technical-contract clarification on September 4, 2026.
- Supersedes: Not applicable.

This document is the canonical source of truth for the requirements it defines. Derived plans and implementation must preserve its objective, constraints, execution boundaries, and success criteria; material changes require an updated and re-confirmed specification.

> Status note: this spec preserves findings from the original transport spike.
> Later implementation and observation notes found that the private Codex backend
> request path requires `stream: true`; older non-streaming MVP assumptions should
> be treated as historical context, not the current adapter contract.
> This Version 1 specification accepts technical viability only. It does not
> establish, infer, or promise subscription billing attribution; provider-neutral
> usage and pricing evidence remains separately owned.

## Objective

Define the Codex-specific support needed for Fabrica's local Python agent runtime
to use direct ChatGPT/Codex-authenticated backend access without exposing private
backend details to the runtime core.

The immediate goal is a narrow transport support path that validates direct
technical access and final-result behavior while keeping volatile private-backend
details isolated behind replaceable hexagonal boundaries. Billing source and
per-call subscription attribution are not technical-viability criteria.

The broader runtime direction is owned by `docs/specs/agent-runtime-spec.md`.
Provider-neutral usage and pricing evidence is owned by
`docs/specs/model-usage-and-cost-evidence-spec.md`.

## Current Context

- Source idea: subscription-backed Codex transport for local Python agent runtime
  experiments.
- Local Codex CLI observed during spec refinement: `codex-cli 0.146.0`, installed
  from Homebrew cask `codex`.
- Source reference used for research: `openai/codex` tag `rust-v0.146.0`.
- Codex transport source lives under `src/fabrica/features/codex_transport/`.
- Runtime source lives under `src/fabrica/features/agent_runtime/` and should
  consume Codex through application-level transport contracts only.
- Current implementation includes a thin PydanticAI completion bridge and
  composition experiment, but the Codex transport slice remains the boundary for
  private backend details.
- Default automated tests must remain deterministic and offline.

## Assumptions

- `~/.codex/auth.json` contains enough credential and account information to
  authenticate direct Codex backend requests.
- On the observed local install, `~/.codex/auth.json` uses `auth_mode = chatgpt`,
  has no stored public OpenAI API key, and contains `tokens.access_token`,
  `tokens.account_id`, `tokens.id_token`, and `tokens.refresh_token` values.
  Token values must remain redacted and in memory only.
- The local auth file can be read safely without modifying, printing, or
  persisting credential values elsewhere. The minimum values required for one
  request may exist in process memory only; they must not be copied to another
  file, process, remote service, log, diagnostic, fixture, or persistent store.
- The ChatGPT Codex backend request path is Responses-shaped. Codex `0.146.0`
  uses ChatGPT backend base URL `https://chatgpt.com/backend-api/`, a
  `codex/responses` API path, bearer auth from the ChatGPT access token, and the
  `ChatGPT-Account-ID` header.
- `codex doctor --json` confirms ChatGPT auth mode, backend reachability, locally
  configured model, and `wire API = responses` over a redacted Responses
  WebSocket endpoint.
- Version 1 reloads the auth file once at the start of each operation. It does
  not refresh credentials or reread the file after a backend `401` or `403`.
- Direct Codex backend use appears intended to be covered by the user's existing
  ChatGPT/Codex subscription rather than separately billed public OpenAI API
  usage. Implementation must collect repeated-session evidence and document the
  limits of available billing/quota attribution before declaring viability.
- Authentication failures can be handled safely by reloading credentials and
  instructing the user to run `codex login`.

## Scope

### In Scope

- Subscription-backed Codex transport support behind a replaceable outbound adapter.

### Out of Scope

The detailed exclusions already recorded below remain authoritative.

## Desired Behavior

Codex transport support should:

- load Codex credentials from `~/.codex/auth.json` in read-only mode;
- extract only the minimum token and account values required for backend
  requests;
- keep credential values in memory only;
- send direct streaming requests to the current Codex backend using the observed
  required shape;
- execute Codex HTTP requests with `httpx.AsyncClient` through the reusable async
  retry client;
- return a normalized result that distinguishes successful responses,
  authentication failures, rate-limit or quota failures, backend shape
  mismatches, and transport errors;
- retry Codex HTTP transport calls only through adapter-owned policies with
  bounded backoff, jitter, `Retry-After`, and elapsed budgets;
- keep completion `POST` replay conservative by default: HTTP 429 may be retried,
  but transport exceptions, backend 5xx responses, and ambiguous partial stream
  outcomes must remain single-attempt until replay safety is proven;
- capture observed request requirements, response shapes, error shapes, and
  rate-limit or quota signals with all credentials and sensitive values redacted;
- record retry diagnostics as secret-safe scalar observations including attempt
  count, retry count, final retry reason, final HTTP status or HTTPX error type,
  elapsed seconds, and budget exhaustion status;
- keep the Codex backend isolated as a volatile outbound adapter from the start;
- expose an application API that the runtime can reuse without depending on
  private Codex backend schemas.

Streaming is an adapter implementation detail in Version 1. The adapter may use
the observed streaming wire protocol internally, but it must consume that
protocol before returning one final normalized result. It must not expose
incremental events or partial output through the application boundary. A stream
is successful only when the adapter can extract a non-empty final output from an
accepted completed response shape. Malformed stream framing, unrecognized
required event shapes, a terminal backend error, cancellation, EOF before a
completed result, or output that cannot be safely normalized must produce a
non-success result without partial output. These cases must be classified as
`backend_shape_mismatch` when the observed protocol shape is unsupported and as
`transport_error` when delivery or completion is indeterminate.

Technical viability should be judged strictly. Direct Codex transport is
technically viable only if the support path demonstrates:

- successful redacted live requests authenticated from the supported local Codex
  auth-file shape;
- repeated requests across sessions after local Codex authentication has been
  established;
- distinguishable authentication, rate-limit, quota, backend-shape, and transport
  failures;
- enough Responses-shape compatibility to justify runtime integration work.

Usage, quota, and rate-limit signals may be captured as safe operational
observations when the backend exposes them, but they do not prove a billing source
and are not acceptance evidence for this specification. Billing attribution and
pricing conclusions are deferred to `docs/specs/model-usage-and-cost-evidence-spec.md`.

## Observed request and usage signals

- Tagged source `openai/codex` `rust-v0.146.0` shows ChatGPT backend requests
  using `https://chatgpt.com/backend-api/`, `codex/responses`, bearer
  authorization, `ChatGPT-Account-ID`, `Content-Type: application/json`, and for
  some ChatGPT backend calls `OAI-Product-Sku: codex`.
- Live probing against `codex/responses` reached a JSON backend response.
- The backend rejected `gpt-5-codex` for ChatGPT auth, so direct probes should use
  a ChatGPT-account-compatible Codex model such as the local model reported by
  `codex doctor --json`.
- Adapter and composition defaults are volatile observed defaults and may be
  overridden for live validation; `codex doctor --json` remains the safest source
  for the locally configured ChatGPT-account-compatible model.
- The backend requires `input` to be a list, not a bare prompt string.
- The backend requires `store: false`.
- The backend requires `stream: true`.
- Tagged source shows Codex rate-limit and usage signals through
  `/api/codex/usage`, `/api/codex/rate-limit-reset-credits`, `x-codex-*`
  rate-limit headers, `codex.rate_limits` events, and
  `x-codex-rate-limit-reached-type`.
- Local auth-file field names were inspected with secret values redacted.
  Observed top-level keys were `OPENAI_API_KEY`, `auth_mode`, `last_refresh`, and
  `tokens`; observed nested token keys were `access_token`, `account_id`,
  `id_token`, and `refresh_token`.
- Public OpenAI Responses API documentation could not be fetched during the
  original research pass because `platform.openai.com` returned HTTP 403. Treat
  public Responses API comparison as source-limited until official docs are
  consulted successfully.

## Backend Drift Policy

The private backend is volatile. A changed required endpoint, header, request
field, stream event shape, completion shape, authentication behavior, or
rate-limit/error shape must be treated as an observed backend change rather than
silently normalized. The adapter must fail closed with
`backend_shape_mismatch` when it cannot safely recognize a required successful
or terminal response shape.

Before accepting a changed wire assumption, maintainers must:

1. capture a redacted, synthetic fixture or deterministic contract case that
   represents the new supported shape;
2. update adapter tests and this specification's observed signals or constraints;
3. run the default offline quality gate; and
4. perform and document an opt-in live validation if the changed behavior affects
   a live backend request or response.

## Explicitly out of scope

- Treating `codex exec` as the main integration path.
- OAuth refresh or mutation of Codex credentials.
- Incremental streaming events or partial output in application/runtime APIs.
- Billing-source, subscription-attribution, or per-call pricing conclusions.
- Full PydanticAI agent orchestration beyond thin bridge experiments.
- Custom PydanticAI `Model` implementation beyond explicit runtime composition
  experiments.
- Full Agent Skills resource/script runtime.
- Production sandboxing.
- RAG or vector search for skills.
- Multi-provider polish before Codex transport viability is known.

## Project Structure

- Spec: `docs/specs/codex-transport-spec.md`.
- Runtime spec: `docs/specs/agent-runtime-spec.md`.
- Transport source: `src/fabrica/features/codex_transport/`.
- Application ports and DTOs: under the owning slice's `application/ports/` and
  `application/dtos/` packages.
- Codex credential and backend implementation details: under the owning slice's
  `adapters/outbound/` package.
- Composition or optional CLI wiring: under `src/fabrica/bootstrap/` or a driving
  adapter owned by `codex_transport`, after the Python API proof is useful.
- Unit tests: under `tests/unit/features/codex_transport/`.
- Opt-in live integration tests: under `tests/integration/features/codex_transport/`,
  skipped by default unless an explicit environment flag or marker is provided.

## Conventions and Constraints

- Keep dependencies pointing inward toward domain and application code.
- Keep Codex auth-file details, backend headers, request payloads, response
  payloads, and SDK/client specifics out of the domain and application core.
- Define application-owned ports for credential loading and model transport before
  depending on concrete adapters.
- Use application DTOs for normalized commands and results when crossing
  application boundaries.
- Keep all environment, filesystem, credential, and network I/O inside adapters or
  composition-root code.
- Use explicit type annotations on public ports, DTOs, services, and adapter APIs.
- Use layer-appropriate exceptions and preserve context with exception chaining.
- Use module-level loggers for production code and never log secrets, tokens,
  cookies, raw auth headers, raw credential files, or full request/response bodies
  containing sensitive data.
- Prefer stable, low-cardinality operational context such as status codes,
  duration, retry count, backend component, and redacted account identifiers.

## Testing Strategy

- Unit-test credential parsing with temporary files and synthetic auth payloads
  only.
- Unit-test missing, malformed, and expired credential scenarios without real
  secrets.
- Unit-test redaction helpers to ensure token-like fields and sensitive headers
  are never exposed in logs, errors, or captured observations.
- Unit-test application orchestration against fake credential stores and fake
  transport ports.
- Unit-test the Codex outbound adapter with fake HTTP/client behavior rather than
  live backend calls.
- Unit-test successful final-result extraction and non-success normalization for
  accepted stream fixtures, malformed stream framing, terminal backend errors,
  truncated or partial streams, and unsupported required event shapes.
- Add contract-style tests if multiple transport adapters or credential stores are
  introduced.
- Keep live backend checks opt-in and isolated from the default `uv run pytest`
  suite.
- Add regression tests for any observed backend shape, auth, or rate-limit
  behavior that becomes part of the normalized result contract.
- Verify that a `401` or `403` returns `authentication_failed` without rereading
  the auth file, refreshing credentials, or replaying the request.

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Format | `uv run ruff format --check .` | Required for implementation changes |
| Lint | `uv run ruff check .` | Required for implementation changes |
| Type check | `uv run ty check src tests` | Required for implementation changes |
| Tests | `uv run pytest` | Required for implementation changes |
| Documentation | Review this specification and its internal references for accuracy and consistency. | Required |
| Migration or compatibility | Not applicable unless this specification explicitly introduces a migration. | Not applicable by default |
| Opt-in live validation | Run a redacted live completion after `codex login`; record only the command outcome, normalized status, and safe observations. | Required operational check; not a documentary acceptance gate |

Documentation-only changes should be reviewed for clarity and consistency.
Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Live backend validation, when intentionally performed, must be manual or
explicitly opt-in. It must not be part of the default local or CI test suite.
It validates authentication and final-result behavior only. It must not be used
to claim or infer a billing source.

## Execution Boundaries

- Always isolate the unofficial Codex backend behind an outbound adapter.
- Always treat local Codex credentials as secrets.
- Always redact credentials and sensitive account details from logs, exceptions,
  diagnostics, fixtures, and docs.
- Always keep default automated tests deterministic and independent of live
  subscription credentials.
- Always load credentials once at the start of an operation. On a backend `401`
  or `403`, return `authentication_failed`; do not refresh credentials, reread
  the auth file, or replay the request. Direct the operator to run `codex login`.
- Ask before adding runtime dependencies, making live backend calls, changing
  public command interfaces, introducing OAuth refresh, integrating PydanticAI
  internals, or executing Agent Skill scripts.
- Ask before making architectural decisions that create shared infrastructure
  outside a feature slice.
- Never modify, rewrite, upload, or persist `~/.codex/auth.json` contents or
  copy its values outside the minimum in-memory values needed for one request.
- Never log raw tokens, auth headers, cookies, credential files, private backend
  payloads, or personal data.
- Never make direct Codex backend usage a hidden side effect of import-time code,
  default tests, or quality gates.
- Never couple the application core to private Codex CLI internals, ChatGPT
  backend headers, OpenAI transport schemas, or PydanticAI implementation details.

## Success Criteria

- The spec defines the Codex-specific support needed by the Python agent runtime.
- The spec identifies assumptions that must be validated before deeper runtime
  integration.
- The spec defines what is in scope and out of scope for Codex support.
- The spec preserves hexagonal vertical-slice boundaries for implementation.
- The spec defines secret-safe handling expectations for local Codex credentials.
- The spec records default validation commands and clarifies that live backend
  calls are opt-in only.
- The spec defines final-result-only streaming behavior, partial-stream failure
  handling, and private-backend drift handling without exposing private wire
  schemas through the application boundary.
- The spec explicitly defers billing-source and subscription-attribution claims.
- The spec provides enough project-structure guidance to start implementation
  without guessing where code and tests belong.

## Resolved Decisions and Deferred Questions

| Question | Impact | Blocking? | Owner | Resolution |
| --- | --- | --- | --- | --- |
| Should Version 1 expose incremental streaming to the runtime? | Application API shape and runtime complexity. | No | Maintainer | Resolved: streaming stays adapter-internal; return one final normalized result only. |
| Can this spec conclude that calls are subscription-billed or not public-API-billed? | Product and billing claims. | No | Maintainer | Deferred: technical viability does not establish billing attribution. |
| What follows a backend `401` or `403` without OAuth refresh? | Authentication recovery behavior. | No | Maintainer | Resolved: return `authentication_failed`; do not reread, refresh, or replay; instruct the operator to run `codex login`. |
| Which observed headers and private stream details are strictly required? | Backend compatibility. | No | Maintainer | Ongoing operational observation governed by the backend drift policy. |

## Acceptance and Operational Validation

This accepted Version 1 specification is ready for implementation planning and
maintenance work. It accepts the documented technical contract, not the volatile
backend facts forever and not any billing-attribution conclusion.

Before an operator relies on the direct transport in a local environment, they
must authenticate through `codex login` and perform the documented opt-in live
validation. Record only secret-safe evidence: the command outcome, normalized
status, and bounded observations. A failed or changed live validation must be
handled under the backend drift policy before its wire assumptions are accepted.
