# Spec: Provider-Agnostic Usage and Cost Evidence

## Objective

Add a provider-agnostic usage and cost evidence model for Fabrica model calls so
agent workflows can report useful usage evidence across providers without
pretending that ambiguous provider-specific pricing is knowable.

The primary user is a developer running Fabrica locally who wants trustworthy
model usage evidence for debugging, planning, and comparing provider behavior.
The first validation provider is Codex because its subscription-backed behavior,
private backend shape, volatile usage endpoints, and uncertain billing
attribution make it the hardest case.

The goal is not exact cost accounting in v1. The goal is an application-level
contract that can represent token counts, quota or rate-limit evidence, evidence
source attribution, and pricing confidence independently of any single backend.

## Current context

- `docs/ideas/provider-agnostic-usage-cost-evidence.md` identifies the need to
  collect reliable model usage evidence before claiming exact pricing.
- Runtime result DTOs currently live in
  `src/fabrica/features/agent_runtime/application/dtos/runtime.py` and do not yet
  expose provider-agnostic usage evidence on `LocalAgentRunResult`.
- Codex transport result DTOs currently live in
  `src/fabrica/features/codex_transport/application/dtos/transport.py` and expose
  normalized completion output plus redacted observations.
- Codex-specific usage probing already exists in
  `src/fabrica/features/codex_transport/application/dtos/usage.py` as
  `CodexUsageEvidence`, `CodexUsageResult`, and `CodexUsageStatus`.
- `CodexUsageEvidence` is currently a safe scalar mapping. It is useful for
  provider-specific observations but is not the desired permanent cross-provider
  model.
- Default automated tests must remain deterministic and offline. Live/private
  Codex probing belongs in explicit opt-in checks, not the default quality gate.

## Assumptions

- A generic usage DTO can represent common token categories across providers
  without flattening away important provider-specific evidence.
- Codex exposes enough safe token, quota, or usage evidence to make collection
  worthwhile even when exact price is unknown.
- Pricing should remain optional enrichment instead of being required for a model
  call or transport result to be useful.
- Every collected evidence item should record where it came from, such as a
  response payload, stream event, header, usage endpoint, manual observation, or
  source-code observation.
- Confidence vocabulary can start small and expand when new providers or evidence
  sources require more precision.
- Provider-specific raw payloads are not needed for the v1 application contract
  and should not be persisted by default.

## Desired behavior

Fabrica should expose normalized model usage evidence through an application-level
contract that can be attached to model-call results when available and omitted
when unavailable.

### Provider-agnostic usage evidence

Add a generic usage evidence DTO family with fields for:

- provider identifier, such as `codex`, `openai`, or another stable provider
  label;
- model identifier when safe and known;
- collection status, such as collected, partially collected, unavailable,
  unsupported, or failed;
- evidence source, such as response payload, stream event, response header, usage
  endpoint, manual observation, or source-code observation;
- confidence, such as observed, extracted, inferred, manual, estimated, or
  unknown;
- token counts when available:
  - input tokens;
  - output tokens;
  - total tokens;
  - cached input tokens;
  - reasoning tokens;
- quota or rate-limit evidence when available, represented as safe normalized
  observations rather than raw provider payloads. V1 structured quota/rate-limit
  evidence should use `limit`, `remaining`, `reset_at`, and `window_seconds`
  fields when those values are safely known;
- redacted observations for missing, partial, or ambiguous evidence.

Usage evidence must be valid without a cost estimate. Missing token categories
should be represented as absent values, not zero, unless the provider explicitly
reported zero.

### Cost and pricing evidence

Add a separate optional sibling cost or pricing evidence DTO with fields for:

- pricing status, such as unknown, not available, subscription included,
  public-price estimate, manual estimate, or unsupported;
- currency when a monetary estimate exists;
- estimated amount when a monetary estimate exists;
- confidence and source attribution;
- redacted explanatory observations.

Codex subscription-backed usage should default to unknown, unavailable, or
subscription-included pricing status unless there is a trustworthy source for a
more specific claim. Public API pricing must not be treated as exact Codex
subscription billing without explicit evidence.

### Codex mapping

Codex should be the first provider-specific mapping into the generic contract.
The Codex mapping should:

- translate safe response usage fields into generic token fields when present;
- translate safe stream-event usage fields if supported;
- translate safe usage-endpoint evidence into quota, rate-limit, or token
  evidence where applicable;
- preserve provider-specific facts only as safe normalized observations when the
  generic fields are not expressive enough;
- avoid storing raw response bodies, account identifiers, secrets, private
  endpoint details, or billing-page content;
- report unknown pricing explicitly instead of silently omitting cost ambiguity.

### Second-provider validation

Before treating the generic contract as stable, validate it against at least one
conventional API-style usage shape in addition to Codex. This second provider can
be represented by a focused synthetic fixture in v1; live integration is not
required.

The validation target should prove that the DTO can represent a normal response
shape with token usage and, when applicable, a public-price estimate without
embedding Codex-specific assumptions.

## Non-goals

- Do not calculate exact Codex pricing in v1.
- Do not scrape billing pages.
- Do not persist raw provider payloads.
- Do not make live Codex probes part of default tests or quality gates.
- Do not add provider billing integrations.
- Do not make public API token pricing look like exact subscription-backed Codex
  billing.
- Do not add Codex-only token fields directly into generic runtime result DTOs as
  the permanent model.

## Commands and validation

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`
- Focused unit tests during implementation:
  - `uv run pytest tests/unit/features/agent_runtime/application/`
  - `uv run pytest tests/unit/features/codex_transport/application/`
  - `uv run pytest tests/unit/features/codex_transport/adapters/`

Manual verification, if live probing is implemented later, must be explicit and
opt-in. It must use redacted output and must not be part of the default local or
CI validation path.

## Project structure

- Spec: `docs/specs/provider-agnostic-usage-cost-evidence-spec.md`.
- Generic usage and cost evidence DTO location for v1:
  `src/fabrica/features/agent_runtime/application/dtos/usage.py`.
- Do not create a standalone `model_usage` feature slice in v1. Reconsider that
  only after usage/cost evidence grows into its own use case family.
- Existing Codex-specific usage DTOs:
  `src/fabrica/features/codex_transport/application/dtos/usage.py`.
- Codex usage mapping should live in the Codex transport slice, either in
  application mapping code or an adapter-local mapper depending on where the raw
  provider shape is handled.
- Runtime result integration:
  `src/fabrica/features/agent_runtime/application/dtos/runtime.py`.
- Relevant model/runtime result boundaries should expose tuples of usage evidence
  items and tuples of cost evidence items so multiple sources can contribute
  evidence with distinct provenance.
- Unit tests should mirror the owning source location under `tests/unit/features/`.

Avoid `shared_kernel` for v1 unless the usage evidence types become pure domain
concepts genuinely reused by multiple slices. These DTOs are more likely to be
application boundary types than shared-kernel domain concepts.

## Conventions

- Preserve hexagonal boundaries: generic usage evidence belongs at an application
  boundary, while provider payload extraction belongs in provider-specific
  adapters or application mapping code.
- Use immutable dataclasses and `StrEnum` values consistent with existing DTOs.
- Public DTOs and ports must have explicit type annotations.
- Keep provider identifiers, evidence sources, confidence values, and pricing
  statuses as closed vocabularies where practical.
- Use this closed v1 confidence vocabulary: `observed`, `extracted`, `inferred`,
  `manual`, `estimated`, and `unknown`.
- Use `None` only for legitimate absence, such as a token category not reported
  by the provider.
- Keep observations redacted and bounded.
- Represent provider-specific facts as safe normalized observations in v1. Do not
  add a generic provider-specific extension mapping to the usage DTO.
- Never log secrets, raw provider payloads, authentication headers, cookies,
  account identifiers, or billing-page content.
- Treat pricing claims as evidence-bearing statements with status, source, and
  confidence, not as implicit arithmetic hidden inside a transport adapter.

## Testing strategy

- Unit-test generic usage DTO validation:
  - token counts accept non-negative integers;
  - missing token categories remain absent rather than defaulting to zero;
  - total token count may be provided by the provider or derived only when the
    derivation rule is explicit;
  - provider, source, confidence, and status vocabularies reject invalid values.
- Unit-test pricing evidence validation:
  - unknown or unavailable pricing requires no amount or currency;
  - monetary estimates require currency, amount, source, and confidence;
  - subscription-included status does not imply a per-call price.
- Unit-test Codex mapping:
  - present response usage maps to generic token fields;
  - missing usage maps to unavailable or partially collected evidence;
  - partial usage preserves only reported categories;
  - usage-endpoint quota or rate-limit values map to safe normalized evidence;
  - structured quota or rate-limit evidence uses `limit`, `remaining`,
    `reset_at`, and `window_seconds` only when safely known;
  - pricing remains unknown or subscription-oriented unless explicit evidence is
    available;
  - unsafe raw fields are not exposed in DTOs or observations.
- Unit-test an OpenAI-style synthetic conventional provider mapping:
  - normal API-style input/output/total token fields map into the same generic
    contract;
  - optional public-price estimates are represented as estimates with source and
    confidence.
- Preserve existing Codex transport and agent runtime tests while extending result
  DTO tests for optional usage evidence if runtime results are changed.
- Keep all default tests offline and deterministic.

## Boundaries

- Always collect token or quota evidence even when exact cost is unknown.
- Always attach source attribution and confidence to evidence that may influence
  planning, cost estimates, or user-facing output.
- Always represent unknown or unavailable pricing explicitly.
- Always keep provider-specific extraction behind provider-owned code.
- Always redact observations and avoid raw provider payload persistence.
- Always keep generic usage/cost evidence DTOs under `agent_runtime` for v1.
- Ask before introducing a new `model_usage` feature slice.
- Ask before adding generic provider-specific extension fields to the usage DTO.
- Ask before adding live probes to developer workflows, CI, or default quality
  gates.
- Ask before introducing a dependency for currency, decimal money arithmetic, or
  provider pricing catalogs.
- Never claim exact Codex per-call cost from subscription-backed usage without a
  trustworthy source.
- Never scrape billing pages or store account-private billing evidence in source
  artifacts.

## Success criteria

- The spec defines provider-agnostic usage evidence separately from Codex-specific
  backend details.
- The spec treats Codex as the first validation adapter, not the permanent core
  model.
- The spec makes unknown, unavailable, subscription-included, public-price
  estimate, and manual-estimate pricing states explicit.
- The spec requires evidence source and confidence labels for usage and pricing
  evidence.
- The spec documents resolved v1 project structure, boundaries, non-goals, validation
  commands, and testing strategy.
- The first implementation slice can add generic DTOs and Codex mapping without
  requiring exact cost calculation or live private probes.

## Resolved v1 decisions

- Generic usage and cost evidence DTOs live in
  `src/fabrica/features/agent_runtime/application/dtos/usage.py` for v1.
- Do not create a new `model_usage` feature slice in v1.
- Represent provider-specific facts only as safe normalized observations in v1;
  do not add a generic provider-specific extension map.
- Use the v1 confidence vocabulary `observed`, `extracted`, `inferred`,
  `manual`, `estimated`, and `unknown`.
- Model cost evidence as a sibling DTO to usage evidence rather than nesting cost
  inside usage evidence.
- Use an OpenAI-style synthetic fixture as the second provider validation case.
- Use generic structured quota/rate-limit evidence fields `limit`, `remaining`,
  `reset_at`, and `window_seconds` when safely known.
- Relevant model/runtime result DTOs should expose tuples of usage evidence items
  and tuples of cost evidence items so multiple evidence sources can retain their
  own source and confidence.

## Proposed first implementation slice

1. Add generic usage and cost evidence DTOs in
   `src/fabrica/features/agent_runtime/application/dtos/usage.py`.
2. Add focused DTO validation tests for token counts, source attribution,
   confidence, status, and pricing states.
3. Add Codex mapping from safe response usage or existing `CodexUsageEvidence`
   values into the generic contract.
4. Add Codex mapping tests for present, missing, partial, quota/rate-limit, and
   unknown-pricing cases.
5. Add one OpenAI-style synthetic conventional provider mapping test or fixture
   to validate that the generic contract is not Codex-shaped.
6. Attach usage evidence and cost evidence tuples to `LocalAgentRunResult`.
