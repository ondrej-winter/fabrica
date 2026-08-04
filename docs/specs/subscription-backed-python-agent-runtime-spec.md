# Spec: Subscription-Backed Python Agent Runtime

## Objective

Define the first implementation target for a local Python agent runtime experiment that can use an existing
ChatGPT/Codex subscription without introducing separate OpenAI API billing. The immediate goal is not a complete agent
runtime; it is a narrow transport spike that validates whether direct, subscription-backed Codex backend access is viable
enough to justify deeper runtime and PydanticAI integration work.

The primary user is an agent power user who already has local Codex CLI authentication and wants to run local Python
agent workflows while keeping volatile subscription-backed backend details isolated behind replaceable hexagonal
boundaries.

## Current context

- Source idea: subscription-backed Codex transport for local Python agent runtime experiments.
- Project: `fabrica`, a Python 3.13 application scaffold for local agent runtime experiments.
- Local Codex CLI observed during spec refinement: `codex-cli 0.146.0`, installed from Homebrew cask `codex`.
- Source reference used for research: `openai/codex` tag `rust-v0.146.0`.
- Architecture: `src/` layout with hexagonal architecture organized by vertical feature slices.
- Tooling: `uv` for environment and command execution, `ruff` for formatting/linting, `ty` for type checking, and
  `pytest` for tests.
- Existing package roots:
  - `src/fabrica/features/` for business capabilities and use cases.
  - `src/fabrica/shared_kernel/` for pure domain concepts genuinely shared by multiple slices.
  - `src/fabrica/bootstrap/` for composition root, dependency wiring, and startup helpers.
  - `tests/unit/` and `tests/integration/` for mirrored test ownership.
- No concrete feature slice exists yet; the first implementation should introduce only the slice structure required for
  the selected spike.

## Assumptions

- `~/.codex/auth.json` contains enough credential and account information to authenticate direct Codex backend requests.
- On the observed local install, `~/.codex/auth.json` uses `auth_mode = chatgpt`, has no stored public OpenAI API key, and
  contains `tokens.access_token`, `tokens.account_id`, `tokens.id_token`, and `tokens.refresh_token` values. Token values
  must remain redacted and in memory only.
- The local auth file can be read safely without modifying, copying, printing, or persisting credential values elsewhere.
- The ChatGPT Codex backend request path is Responses-shaped. Codex `0.146.0` uses ChatGPT backend base URL
  `https://chatgpt.com/backend-api/`, a `codex/responses` API path, bearer auth from the ChatGPT access token, and the
  `ChatGPT-Account-ID` header. The local `codex doctor --json` report confirms ChatGPT auth mode, backend reachability,
  locally configured model, and `wire API = responses` over a redacted Responses WebSocket endpoint.
- Direct Codex backend use is covered by the user's existing ChatGPT/Codex subscription and does not create separately
  billed public OpenAI API usage. This is still not fully proven; the implementation must collect repeated-session evidence
  and documented billing/quota observations before declaring viability.
- Authentication failures can be handled safely by reloading credentials and instructing the user to run `codex login`.
- Full Agent Skills support is useful, but it does not need to be validated until after transport viability is known.
- Default local tests and quality gates must not call the live backend or require real subscription credentials.

## Desired behavior

### MVP transport spike

The first deliverable after this spec is accepted should be a narrow local transport spike that proves the riskiest
assumption: subscription-backed direct Codex access.

The spike should:

- Load Codex credentials from `~/.codex/auth.json` in read-only mode.
- Extract only the minimum token and account values required for a single backend request.
- Keep credential values in memory only.
- Send one direct, non-streaming request to the current Codex backend.
- Return a normalized result that distinguishes successful responses, authentication failures, rate-limit or quota
  failures, backend shape mismatches, and transport errors.
- Capture observed request requirements, response shapes, error shapes, and rate-limit or quota signals with all
  credentials and sensitive values redacted.
- Keep the Codex backend isolated as a volatile outbound adapter from the start.
- Expose a Python API first, so the spike output can be reused by later runtime and PydanticAI integration work without
  committing to a CLI surface prematurely.

Viability should be judged strictly. Subscription-backed direct Codex access is viable only if the spike demonstrates:

- successful redacted live requests without relying on a public OpenAI API key;
- repeated requests across sessions after local Codex authentication has been established;
- distinguishable authentication, rate-limit, quota, backend-shape, and transport failures;
- observable Codex subscription usage or quota signals, including `/api/codex/usage`, Codex rate-limit headers or events,
  and billing/quota observations that do not indicate public OpenAI API billing;
- enough Responses-shape compatibility to justify follow-up PydanticAI integration work.

### Follow-up Agent Skills spike

Agent Skills support should be treated as a second spike after transport viability is known.

The skills spike may explore:

- Loading complete `SKILL.md` files into model context when they fit comfortably.
- Loading selected skill references without introducing retrieval-augmented generation by default.
- Defining a local approval and sandbox policy before executing arbitrary skill scripts.

### Explicitly out of scope for the MVP

- Streaming responses.
- Tool calls and tool-result loops.
- Full PydanticAI agent orchestration.
- Custom PydanticAI `Model` implementation.
- OAuth refresh or mutation of Codex credentials.
- Full Agent Skills resource/script runtime.
- Production sandboxing.
- A `codex exec` wrapper as the main integration path.
- RAG or vector search for skills.
- Multi-provider polish before Codex transport viability is known.

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency. Future implementation changes should use the
project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Live backend validation, when intentionally performed, must be manual or explicitly opt-in. It must not be part of the
default local or CI test suite.

## Project structure

- Spec: `docs/specs/subscription-backed-python-agent-runtime-spec.md`.
- Source idea: subscription-backed Codex transport for local Python agent runtime experiments.
- Future transport spike source: under `src/fabrica/features/codex_transport/`.
- Future application ports and DTOs: under the owning slice's `application/ports/` and `application/dtos/` packages.
- Future Codex credential and backend implementation details: under the owning slice's `adapters/outbound/` package.
- Future composition or optional CLI wiring: under `src/fabrica/bootstrap/` or a driving adapter owned by
  `codex_transport`, after the Python API proof is useful.
- Future unit tests: under `tests/unit/features/<feature_name>/` mirroring domain, application, and adapter ownership.
- Future opt-in live integration tests: under `tests/integration/features/<feature_name>/`, skipped by default unless an
  explicit environment flag or marker is provided.

## Conventions

- Keep dependencies pointing inward toward domain and application code.
- Keep Codex auth-file details, backend headers, request payloads, response payloads, and SDK/client specifics out of the
  domain and application core.
- Define application-owned ports for credential loading and model transport before depending on concrete adapters.
- Use application DTOs for normalized commands and results when crossing application boundaries.
- Keep all environment, filesystem, credential, and network I/O inside adapters or composition-root code.
- Use explicit type annotations on public ports, DTOs, services, and adapter APIs.
- Use layer-appropriate exceptions and preserve context with exception chaining.
- Use module-level loggers for production code and never log secrets, tokens, cookies, raw auth headers, raw credential
  files, or full request/response bodies containing sensitive data.
- Prefer stable, low-cardinality operational context such as status codes, duration, retry count, backend component, and
  redacted account identifiers.

## Testing strategy

- Unit-test credential parsing with temporary files and synthetic auth payloads only.
- Unit-test missing, malformed, and expired credential scenarios without real secrets.
- Unit-test redaction helpers to ensure token-like fields and sensitive headers are never exposed in logs, errors, or
  captured observations.
- Unit-test application orchestration against fake credential stores and fake transport ports.
- Unit-test the Codex outbound adapter with fake HTTP/client behavior rather than live backend calls.
- Add contract-style tests if multiple transport adapters or credential stores are introduced.
- Keep live backend checks opt-in and isolated from the default `uv run pytest` suite.
- Add regression tests for any observed backend shape, auth, or rate-limit behavior that becomes part of the normalized
  result contract.

## Research findings

- Codex CLI `0.146.0` is installed locally and reports ChatGPT auth mode in `codex doctor --json`.
- The Homebrew cask points to `https://github.com/openai/codex/releases/download/rust-v0.146.0/codex-package-aarch64-apple-darwin.tar.gz`.
- Tagged source `openai/codex` `rust-v0.146.0` shows ChatGPT backend requests using
  `https://chatgpt.com/backend-api/`, `codex/responses`, bearer authorization, `ChatGPT-Account-ID`, `Content-Type:
  application/json`, and for some ChatGPT backend calls `OAI-Product-Sku: codex`.
- Tagged source shows Codex rate-limit and usage signals through `/api/codex/usage`,
  `/api/codex/rate-limit-reset-credits`, `x-codex-*` rate-limit headers, `codex.rate_limits` events, and
  `x-codex-rate-limit-reached-type`.
- Live probing against `codex/responses` reached a JSON backend response. The backend rejected `gpt-5-codex` for ChatGPT
  auth, so direct probes should use a ChatGPT-account-compatible Codex model such as the local model reported by
  `codex doctor --json`. The backend also requires `input` to be a list, not a bare prompt string, requires
  `store: false`, and requires `stream: true`.
- Local auth-file field names were inspected with secret values redacted. Observed top-level keys were `OPENAI_API_KEY`,
  `auth_mode`, `last_refresh`, and `tokens`; observed nested token keys were `access_token`, `account_id`, `id_token`,
  and `refresh_token`.
- Public OpenAI Responses API documentation could not be fetched during this pass because `platform.openai.com` returned
  HTTP 403. Treat public Responses API comparison as source-limited until official docs are consulted successfully.
- Agent Skills script execution should remain out of the transport MVP. A conservative later policy should require explicit
  user approval before running skill-provided scripts, run scripts under the narrowest practical sandbox, avoid network
  access unless explicitly needed and approved, and treat bundled skill scripts as untrusted executable code until reviewed.

## Boundaries

- Always isolate the unofficial Codex backend behind an outbound adapter.
- Always treat local Codex credentials as secrets.
- Always redact credentials and sensitive account details from logs, exceptions, diagnostics, fixtures, and docs.
- Always keep default automated tests deterministic and independent of live subscription credentials.
- Ask before adding runtime dependencies, making live backend calls, changing public command interfaces, introducing OAuth
  refresh, implementing streaming, integrating PydanticAI internals, or executing Agent Skill scripts.
- Ask before making architectural decisions that create shared infrastructure outside a feature slice.
- Never modify, rewrite, copy, upload, or persist `~/.codex/auth.json` contents.
- Never log raw tokens, auth headers, cookies, credential files, private backend payloads, or personal data.
- Never make direct Codex backend usage a hidden side effect of import-time code, default tests, or quality gates.
- Never couple the application core to private Codex CLI internals, ChatGPT backend headers, OpenAI transport schemas, or
  PydanticAI implementation details.

## Success criteria

- The spec clearly distinguishes the transport MVP from later Agent Skills work.
- The spec identifies assumptions that must be validated before deeper runtime implementation.
- The spec defines what is in scope and out of scope for the first spike.
- The spec preserves hexagonal vertical-slice boundaries for future implementation.
- The spec defines secret-safe handling expectations for local Codex credentials.
- The spec records default validation commands and clarifies that live backend calls are opt-in only.
- The spec provides enough project-structure guidance to start an implementation plan without guessing where code and
  tests belong.

## Open questions

- Which observed request headers are strictly required for a direct Python transport versus incidental to Codex CLI
  behavior? Initial candidates are bearer `Authorization`, `ChatGPT-Account-ID`, `Content-Type: application/json`, and
  possibly `OAI-Product-Sku: codex`.
- What is the smallest non-streaming Responses-shaped payload that the ChatGPT Codex backend accepts for a useful Python
  API proof?
- Can public OpenAI Responses API documentation be consulted successfully and compared against the tagged Codex
  Responses-shaped payloads and events?
- What concrete billing evidence can be captured safely, without exposing account details, to prove that successful calls
  are subscription-backed rather than public API-billed?
- What exact normalized result contract should represent Codex-specific usage limits, public-API-style quota failures,
  auth failures, backend-shape mismatches, and transport errors?
