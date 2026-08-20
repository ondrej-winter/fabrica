# Spec: Codex Transport

> Status note: this spec preserves findings from the original transport spike.
> Later implementation and observation notes found that the private Codex backend
> request path requires `stream: true`; older non-streaming MVP assumptions should
> be treated as historical context, not the current adapter contract.
> Current implementation notes also treat exact per-call subscription billing
> attribution as unavailable unless the backend exposes a safe reactive signal;
> repeated-session success plus documented billing ambiguity can support a
> conditional viability decision.

## Objective

Define the Codex-specific support needed for Fabrica's local Python agent runtime
to use an existing ChatGPT/Codex subscription without introducing separate
OpenAI API billing.

The immediate goal is a narrow transport support path that validates direct,
subscription-backed Codex backend access and keeps volatile private-backend
details isolated behind replaceable hexagonal boundaries.

The broader runtime direction is owned by `docs/specs/agent-runtime.md`.
Provider-neutral usage and pricing evidence is owned by
`docs/specs/model-usage-and-cost-evidence.md`.

## Current context

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
- The local auth file can be read safely without modifying, copying, printing, or
  persisting credential values elsewhere.
- The ChatGPT Codex backend request path is Responses-shaped. Codex `0.146.0`
  uses ChatGPT backend base URL `https://chatgpt.com/backend-api/`, a
  `codex/responses` API path, bearer auth from the ChatGPT access token, and the
  `ChatGPT-Account-ID` header.
- `codex doctor --json` confirms ChatGPT auth mode, backend reachability, locally
  configured model, and `wire API = responses` over a redacted Responses
  WebSocket endpoint.
- Direct Codex backend use appears intended to be covered by the user's existing
  ChatGPT/Codex subscription rather than separately billed public OpenAI API
  usage. Implementation must collect repeated-session evidence and document the
  limits of available billing/quota attribution before declaring viability.
- Authentication failures can be handled safely by reloading credentials and
  instructing the user to run `codex login`.

## Desired behavior

Codex transport support should:

- load Codex credentials from `~/.codex/auth.json` in read-only mode;
- extract only the minimum token and account values required for backend
  requests;
- keep credential values in memory only;
- send direct streaming requests to the current Codex backend using the observed
  required shape;
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

Viability should be judged strictly. Subscription-backed direct Codex access is
viable only if the support path demonstrates:

- successful redacted live requests without relying on a public OpenAI API key;
- repeated requests across sessions after local Codex authentication has been
  established;
- distinguishable authentication, rate-limit, quota, backend-shape, and transport
  failures;
- observable Codex subscription usage or quota signals when the backend exposes
  them, including `/api/codex/usage`, Codex rate-limit headers or events, and
  redacted billing/quota observations;
- documented billing-attribution limits when exact per-session or per-call
  subscription telemetry is unavailable;
- enough Responses-shape compatibility to justify runtime integration work.

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

## Explicitly out of scope

- Treating `codex exec` as the main integration path.
- OAuth refresh or mutation of Codex credentials.
- Full PydanticAI agent orchestration beyond thin bridge experiments.
- Custom PydanticAI `Model` implementation beyond explicit runtime composition
  experiments.
- Full Agent Skills resource/script runtime.
- Production sandboxing.
- RAG or vector search for skills.
- Multi-provider polish before Codex transport viability is known.

## Project structure

- Spec: `docs/specs/codex-transport.md`.
- Runtime spec: `docs/specs/agent-runtime.md`.
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

## Conventions

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

## Testing strategy

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
- Add contract-style tests if multiple transport adapters or credential stores are
  introduced.
- Keep live backend checks opt-in and isolated from the default `uv run pytest`
  suite.
- Add regression tests for any observed backend shape, auth, or rate-limit
  behavior that becomes part of the normalized result contract.

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency.
Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Live backend validation, when intentionally performed, must be manual or
explicitly opt-in. It must not be part of the default local or CI test suite.

## Boundaries

- Always isolate the unofficial Codex backend behind an outbound adapter.
- Always treat local Codex credentials as secrets.
- Always redact credentials and sensitive account details from logs, exceptions,
  diagnostics, fixtures, and docs.
- Always keep default automated tests deterministic and independent of live
  subscription credentials.
- Ask before adding runtime dependencies, making live backend calls, changing
  public command interfaces, introducing OAuth refresh, integrating PydanticAI
  internals, or executing Agent Skill scripts.
- Ask before making architectural decisions that create shared infrastructure
  outside a feature slice.
- Never modify, rewrite, copy, upload, or persist `~/.codex/auth.json` contents.
- Never log raw tokens, auth headers, cookies, credential files, private backend
  payloads, or personal data.
- Never make direct Codex backend usage a hidden side effect of import-time code,
  default tests, or quality gates.
- Never couple the application core to private Codex CLI internals, ChatGPT
  backend headers, OpenAI transport schemas, or PydanticAI implementation details.

## Success criteria

- The spec defines the Codex-specific support needed by the Python agent runtime.
- The spec identifies assumptions that must be validated before deeper runtime
  integration.
- The spec defines what is in scope and out of scope for Codex support.
- The spec preserves hexagonal vertical-slice boundaries for implementation.
- The spec defines secret-safe handling expectations for local Codex credentials.
- The spec records default validation commands and clarifies that live backend
  calls are opt-in only.
- The spec provides enough project-structure guidance to start implementation
  without guessing where code and tests belong.

## Open questions

- Which observed request headers are strictly required for a direct Python
  transport versus incidental to Codex CLI behavior? Initial candidates are
  bearer `Authorization`, `ChatGPT-Account-ID`, `Content-Type: application/json`,
  and possibly `OAI-Product-Sku: codex`.
- What is the smallest streaming Responses-shaped payload that the ChatGPT Codex
  backend accepts for a useful Python API proof?
- Can public OpenAI Responses API documentation be consulted successfully and
  compared against the tagged Codex Responses-shaped payloads and events?
- What concrete billing evidence can be captured safely, without exposing account
  details, to prove that successful calls are subscription-backed rather than
  public API-billed?
- What exact normalized result contract should represent Codex-specific usage
  limits, public-API-style quota failures, auth failures, backend-shape
  mismatches, and transport errors?
