# Provider-Agnostic Usage and Cost Evidence

## Problem Statement

How might we collect reliable model usage evidence for Fabrica across model providers without pretending that ambiguous provider-specific pricing, especially Codex subscription pricing, is knowable before we have trustworthy sources?

## Recommended Direction

Define a provider-agnostic usage evidence concept first, then map Codex into it as the first messy provider-specific source. The immediate coding direction should not be to add Codex-only token fields directly into the transport result as a permanent model. Instead, introduce an application-level usage contract that can represent tokens, quota/rate-limit evidence, source attribution, and pricing confidence independently of any single backend.

Token and usage evidence should be collectable even when exact cost is unavailable. Pricing should be modeled as optional enrichment with explicit status and confidence, such as unknown, not available, subscription-included, public-price estimate, or manual estimate. This keeps the system useful now while avoiding false precision.

Codex remains important as the first adapter because it exposes the hardest case: private/subscription-backed behavior, volatile usage endpoints, and uncertain billing attribution. If the abstraction works for Codex without leaking secrets or overclaiming cost, it should be usable for more conventional model providers later.

## Key Assumptions to Validate

- [ ] A generic usage DTO can represent common token categories across providers without flattening away important provider-specific evidence. Test by mapping Codex response usage, Codex usage endpoint evidence, and at least one conventional API-style usage shape into the same contract.
- [ ] Codex exposes enough safe token or usage evidence to make collection worthwhile even when exact price is unknown. Test with synthetic response shapes first, then optional redacted live probes.
- [ ] Pricing can remain an enrichment layer rather than a transport concern. Test by designing the usage contract so it can be returned without any cost estimate.
- [ ] Future planning benefits from source and confidence labels. Test by requiring every collected evidence item to say where it came from, such as response payload, stream event, header, usage endpoint, manual observation, or source-code observation.

## MVP Scope

The minimum useful implementation is a generic application-level usage evidence contract plus Codex mapping into it.

In scope:

- A provider-agnostic usage DTO, for example `ModelUsageEvidence` or `ModelTokenUsage`, owned outside Codex-specific adapter details.
- Token counts where available: input tokens, output tokens, total tokens, cached input tokens, and reasoning tokens.
- Evidence metadata: provider, model identifier when safe, evidence source, confidence, and collection status.
- A pricing placeholder or separate cost-estimate DTO that can explicitly say pricing is unknown or unavailable.
- Codex adapter mapping from safe response/stream/usage-endpoint shapes into the generic contract.
- Unit tests for present usage, missing usage, partial usage, and unknown pricing.

Out of MVP scope:

- Exact Codex price calculation.
- Billing-page scraping.
- Persisting raw provider payloads.
- Making live Codex probes part of default tests or quality gates.

## Suggested Next Coding Step

Start with the generic usage contract before changing Codex result semantics:

1. Inspect existing model/transport result DTOs and decide where a provider-agnostic usage DTO belongs.
2. Add a small usage DTO with explicit optional token fields, source, confidence, and pricing status.
3. Add the usage DTO to the relevant model result boundary without requiring usage to be present.
4. Map Codex response usage into the generic DTO in the Codex outbound adapter.
5. Add focused unit tests for direct JSON usage, stream-event usage if supported, missing usage, and unknown pricing.

## Not Doing and Why

- Exact Codex pricing — no trusted per-call billing source is available yet, and subscription-backed use may not map to public API pricing.
- Codex-only permanent DTO design — the binding constraint is a general model-provider abstraction, not a one-provider implementation detail.
- Raw response or billing evidence persistence — it risks secrets, account identifiers, private payloads, or personal data entering the repository.
- Hidden live probes — live/private backend access must stay explicit and opt-in.
- Provider billing integrations — premature until the generic usage evidence shape proves useful.

## Open Questions

- Should the generic usage DTO live in `agent_runtime`, `codex_transport`, a new model-usage feature slice, or `shared_kernel`?
- Should provider-specific raw evidence be represented as safe normalized observations, or should the generic DTO include extension fields for provider-specific categories?
- What confidence vocabulary is enough: observed, extracted, inferred, manual, estimated, unknown?
- Should pricing status be part of usage evidence, or should cost estimation be a separate use case that consumes usage evidence?
- Which provider besides Codex should be used as the second validation case for the abstraction?
