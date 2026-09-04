# Spec: Model Usage and Cost Evidence

## Status

- State: Accepted — Version 1.
- Implementation status: Usage evidence, Codex mapping, runtime propagation, CLI
  presentation, non-monetary pricing-state boundaries, and offline tests are
  implemented in conformance with this accepted Version 1 contract.
- Accepted by: Maintainer.
- Accepted on: September 4, 2026.
- Revision: Accepted Version 1 evidence-boundary clarification on September 4,
  2026.
- Supersedes: Draft — unconfirmed model-usage-and-cost-evidence specification.

This document is the canonical source of truth for the requirements it defines.
Derived plans and implementation must preserve its objective, constraints,
execution boundaries, and success criteria; material changes require an updated
and re-confirmed specification.

## Objective

Provide provider-neutral model usage and non-monetary pricing evidence for
Fabrica model calls. The evidence must help a developer running Fabrica locally
debug and compare provider behavior without implying that ambiguous,
provider-specific billing or per-call cost is knowable.

The first validation provider is Codex because its subscription-backed behavior,
private backend shape, volatile usage endpoints, and uncertain billing
attribution make it the hardest case.

Version 1 is not an exact cost-accounting system. It provides application-level
contracts for token counts, provider-local quota or rate-limit evidence, evidence
source attribution, confidence, and explicit non-monetary pricing state.

## Current Context

- Runtime result DTOs live in
  `src/fabrica/features/agent_runtime/application/dtos/runtime.py` and expose
  usage and cost-evidence tuples on `LocalAgentRunResult`.
- Codex transport result DTOs live in
  `src/fabrica/features/codex_transport/application/dtos/transport.py` and expose
  normalized completion output, redacted observations, and evidence tuples.
- Codex-specific usage probing is represented by `CodexUsageEvidence`,
  `CodexUsageResult`, and `CodexUsageProbeCommand` in
  `src/fabrica/features/codex_transport/application/dtos/transport.py`.
- Generic evidence DTOs live in `src/fabrica/shared_kernel/model_usage.py` because
  both `agent_runtime` and `codex_transport` use them as provider-neutral boundary
  concepts.
- Default automated tests remain deterministic and offline. Live or private Codex
  probing belongs in explicit opt-in validation, never in the default quality gate.

## Assumptions

- A generic usage DTO can represent common token categories without flattening
  provider-specific evidence into false equivalence.
- Codex exposes enough safe token, quota, or usage evidence to make collection
  worthwhile even when billing attribution is unknown.
- Pricing evidence is optional for conventional API-style providers, but
  subscription-backed providers need an explicit non-monetary pricing state so an
  empty tuple is not mistaken for a zero or attributable cost.
- Every emitted evidence item records an evidence source and confidence label.
- Provider-specific raw payloads are unnecessary in Version 1 and must not be
  persisted.

## Scope

### In Scope

- Provider-neutral usage evidence exposed through application boundaries.
- Non-monetary provider-neutral pricing-state evidence.
- Provider-owned mapping of safe usage, quota, rate-limit, and pricing-state facts.
- Offline Codex and synthetic conventional API-style validation.

### Out of Scope

- Exact Codex pricing or subscription billing attribution.
- Any monetary cost amount, currency, price calculation, price catalog, or billing
  integration in production Version 1.
- Pairing a cost/pricing evidence item to a particular usage item, model call, or
  provider invocation.
- Cross-provider comparison of quota or rate-limit fields.
- Billing-page scraping, raw provider-payload persistence, or account-private
  billing evidence.
- Live Codex probes in default local tests, CI, or quality gates.

## Desired Behavior

Fabrica exposes normalized usage evidence and optional result-level pricing-state
evidence through model-call results. Evidence is informative and provenance
bearing; it is not a billing ledger.

### Provider-neutral usage evidence

Usage evidence must support:

- a stable provider identifier, such as `codex` or `openai`;
- a model identifier when safe and known;
- a collection status: `collected`, `partially_collected`, `unavailable`,
  `unsupported`, or `failed`;
- an evidence source: response payload, stream event, response header, usage
  endpoint, manual observation, or source-code observation;
- a confidence label: `observed`, `extracted`, `inferred`, `manual`, `estimated`,
  or `unknown`;
- optional reported token categories: input, output, total, cached input, and
  reasoning tokens;
- optional provider-local quota or rate-limit fields: `limit`, `remaining`,
  `reset_at`, and `window_seconds`;
- redacted, bounded observations explaining missing, partial, ambiguous, or
  provider-specific evidence.

Missing token categories must be absent rather than zero unless the provider
explicitly reported zero. A mapper must preserve all provider-reported token
fields independently. It must not derive, replace, reconcile, or reject a
reported `total_tokens` solely because it differs from other reported token
categories.

Structured quota or rate-limit fields are provider-local operational facts. Their
units, scopes, and reset semantics are not normalized in Version 1 and consumers
must not compare them across providers.

### Pricing-state evidence

Pricing-state evidence is a sibling DTO to usage evidence. The usage and
cost-evidence tuples are independent result-level collections: tuple position is
not a pairing rule, and a pricing-state item must not be interpreted as a
per-usage-item or per-invocation cost attribution.

Version 1 supports only these pricing states:

- `unknown`;
- `not_available`;
- `subscription_included`;
- `unsupported`.

Version 1 must not expose, calculate, retain, or render a monetary amount or
currency. `public_price_estimate` and `manual_estimate` are deferred from the
Version 1 vocabulary. A later accepted specification must define provenance,
billing-unit, scope, and calculation semantics before monetary estimates can be
introduced.

Conventional API-style providers may expose an empty `cost_evidence` tuple when
no applicable pricing-state evidence was collected. Subscription-backed providers
must emit explicit pricing-state evidence. Codex subscription-backed usage should
normally use `unknown`, `not_available`, or `subscription_included`, according to
the safe facts available; public API token pricing must never be represented as
Codex subscription billing.

### Observation safety

Generic observations must accept only scalar metadata and enforce documented
maximum lengths for messages, metadata keys, and string metadata values. Generic
DTO validation is not a redaction engine.

Each provider-owned mapper must maintain a tested allowlist of safe observation
metadata keys. Mappers must drop secrets, authentication headers, cookies, raw
request or response payloads, account identifiers, private endpoint details, and
billing-page content before generic evidence DTO construction.

### Codex mapping

Codex is the first provider-specific mapping into the generic contract. Its
mapping must:

- map safe completion-response or stream-event usage into generic token fields;
- map safe usage-endpoint facts into provider-local quota or rate-limit fields;
- preserve facts not represented by generic fields only as allowlisted safe
  observations;
- avoid raw response bodies, account identifiers, secrets, private endpoint
  details, and billing-page content;
- emit an explicit non-monetary pricing-state evidence item for every
  subscription-backed result covered by the mapping.

### Second-provider validation

Before treating the generic contract as provider-neutral, maintain a test-only
synthetic conventional API-style fixture that maps normal input, output, and total
token fields into the same contract. The fixture proves that the DTO family is not
Codex-shaped; it is not a production integration and does not establish a reusable
provider-adapter contract.

## Project Structure

- Spec: `docs/specs/model-usage-and-cost-evidence-spec.md`.
- Generic evidence DTOs: `src/fabrica/shared_kernel/model_usage.py`.
- Codex-specific usage probe DTOs:
  `src/fabrica/features/codex_transport/application/dtos/transport.py`.
- Codex generic-evidence mappings:
  `src/fabrica/features/codex_transport/application/mappers/`.
- Runtime result integration:
  `src/fabrica/features/agent_runtime/application/dtos/runtime.py`.
- Provider extraction belongs in provider-owned adapters or mapping code.
- Unit tests mirror their source ownership under `tests/unit/`.

Do not create a standalone `model_usage` feature slice unless a later accepted
specification establishes a distinct use-case family.

## Conventions and Constraints

- Preserve hexagonal boundaries: generic evidence is an application-boundary
  concept; provider-payload extraction remains provider-owned.
- Use immutable dataclasses and `StrEnum` values consistent with existing DTOs.
- Public DTOs and ports require explicit type annotations.
- Keep provider identifiers, sources, collection statuses, confidence labels, and
  pricing states as closed vocabularies where practical.
- Use `None` only for legitimate absence, including a token category that the
  provider did not report.
- Keep observations bounded, scalar, redacted, and sourced from tested
  provider-owned allowlists.
- Do not add a generic provider-specific extension mapping in Version 1.
- Never log or persist secrets, tokens, authentication headers, cookies, account
  identifiers, raw provider payloads, or billing-page content.
- Do not introduce dependencies for currency, decimal-money arithmetic, or
  provider pricing catalogs in Version 1.

## Testing Strategy

- Unit-test generic DTO validation:
  - non-negative token and quota values are accepted;
  - missing token categories remain absent rather than defaulting to zero;
  - reported token fields are preserved without total derivation or reconciliation;
  - the Version 1 source, confidence, collection-status, and pricing-state
    vocabularies are enforced;
  - observation messages, metadata keys, and string values obey their bounds.
- Unit-test Codex mapping:
  - complete, missing, and partial completion usage;
  - safe quota/rate-limit mapping and provider-local treatment;
  - explicit subscription-backed non-monetary pricing states;
  - unsafe raw fields, secret-like fields, and account-like fields are excluded by
    tested mapper allowlists.
- Unit-test the synthetic conventional API-style fixture against generic token
  evidence only; it must not exercise monetary estimates.
- Extend runtime and CLI tests for optional usage evidence and non-monetary
  pricing-state presentation.
- Keep all default tests offline and deterministic.

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Format | `uv run ruff format --check .` | Required for implementation changes |
| Lint | `uv run ruff check .` | Required for implementation changes |
| Type check | `uv run ty check src tests` | Required for implementation changes |
| Tests | `uv run pytest` | Required for implementation changes |
| Documentation | Review this specification and its internal references for accuracy and consistency. | Required |
| Manual acceptance | Recorded in this specification's Status section. | Completed |

Focused implementation checks should include:

- `uv run pytest tests/unit/shared_kernel/test_model_usage.py`;
- `uv run pytest tests/unit/features/codex_transport/application/test_usage_mapping.py`;
- `uv run pytest tests/unit/features/agent_runtime/application/test_synthetic_provider_usage_mapping.py`;
- relevant runtime-adapter and CLI evidence-output tests.

Live backend validation, if later performed, must be explicit, opt-in, redacted,
and excluded from default local and CI validation.

## Execution Boundaries

- Always retain available token or provider-local quota evidence even when pricing
  state is unknown.
- Always attach source and confidence to emitted usage and pricing-state evidence.
- Always emit explicit pricing-state evidence for subscription-backed providers.
- Never infer a monetary amount, exact Codex per-call cost, or billing attribution
  from subscription-backed usage.
- Never treat result-level pricing-state evidence as paired with a usage item.
- Never compare provider-local quota or rate-limit values across providers.
- Always keep provider-specific extraction and metadata allowlisting in
  provider-owned code.
- Ask before adding a `model_usage` feature slice, generic provider-extension
  fields, live probes in CI/default workflows, monetary estimates, currency,
  pricing catalogs, or billing integrations.

## Implementation Status and Deferred Work

### Implemented baseline

- Generic usage and cost-evidence DTOs exist in `shared_kernel`.
- Codex completion and usage-endpoint mapping exists in the Codex transport slice.
- Runtime results propagate both evidence tuples.
- CLI output can render usage and pricing evidence.
- Offline generic-DTO, Codex-mapping, runtime, CLI, and synthetic-provider tests
  exist.

### Required Version 1 conformance work

- Remove or defer monetary fields and estimate pricing states from the production
  DTO vocabulary, CLI rendering, and tests.
- Add generic observation key and string-value bounds.
- Make provider-owned observation metadata allowlists explicit and test them for
  unsafe secret-like and account-like fields.
- Align synthetic-provider validation and CLI tests with the non-monetary Version
  1 pricing boundary.

### Deferred beyond Version 1

- Monetary public-price or manual estimates.
- Price-source provenance, effective dates, billing-unit and scope semantics.
- Pricing catalogs, currency arithmetic, and billing integrations.
- Per-call correlation between usage and pricing evidence.
- Generic quota unit/scope normalization and cross-provider quota comparison.
- A production second-provider adapter or reusable provider-adapter contract.

## Success Criteria

- The contract separates provider-neutral usage and pricing-state evidence from
  Codex-private backend details.
- Codex is the first validation adapter, not the permanent core model.
- Pricing states are explicitly non-monetary in Version 1 and never imply exact
  Codex subscription billing.
- Usage and pricing-state evidence are independent result-level collections with
  no implied per-call or per-usage correlation.
- Subscription-backed providers emit explicit pricing-state evidence, while a
  conventional provider may have no applicable pricing-state evidence.
- Token fields are preserved as reported, and quota/rate-limit facts remain
  provider-local rather than cross-provider comparable.
- Provider-owned mappings use tested allowlists to prevent unsafe observation
  metadata from reaching generic evidence DTOs.
- The specification documents the implemented baseline, required conformance
  work, deferred work, boundaries, and validation strategy.

## Open Questions

| Question | Impact | Blocking? | Owner | Resolution |
| --- | --- | --- | --- | --- |
| No open Version 1 questions remain. | None known. | No | Maintainer | Resolved through Version 1 acceptance on September 4, 2026. |

## Acceptance and Planning Gate

This accepted Version 1 specification may be handed to implementation planning.
Any plan must preserve the non-monetary pricing boundary and treat the listed
Version 1 conformance work as required before claiming full conformance.
