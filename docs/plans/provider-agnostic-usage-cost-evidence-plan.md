# Implementation Plan: Provider-Agnostic Usage and Cost Evidence

## Overview

Implement the v1 provider-agnostic usage and cost evidence model described in
`docs/specs/provider-agnostic-usage-cost-evidence-spec.md`. The first
implementation should add immutable application DTOs in `agent_runtime`, map
Codex transport/usage evidence into those generic DTOs without leaking
provider-private payloads, validate the contract with a synthetic OpenAI-style
provider fixture, and attach evidence tuples to `LocalAgentRunResult` so local
agent workflows can report usage evidence when available.

## Goal

Deliver trustworthy, provider-agnostic usage and pricing evidence for model calls
without claiming exact Codex subscription-backed cost.

## Deliverables

- New generic usage/cost DTO module:
  `src/fabrica/features/agent_runtime/application/dtos/usage.py`.
- Public DTO exports from
  `src/fabrica/features/agent_runtime/application/dtos/__init__.py`.
- Optional `usage_evidence` and `cost_evidence` tuples on
  `LocalAgentRunResult` in
  `src/fabrica/features/agent_runtime/application/dtos/runtime.py`.
- Codex-to-generic mapping code in the Codex transport slice under
  `src/fabrica/features/codex_transport/application/usage_mapping.py`.
- Adapter-local Codex completion/stream extraction that turns raw response/SSE
  shapes into safe bounded facts before application mapping sees them.
- Runtime adapter propagation from `CodexTransportResult` to
  `LocalAgentRunResult` in
  `src/fabrica/features/agent_runtime/adapters/outbound/codex_transport_model/adapter.py`.
- Focused unit tests for DTO validation, Codex mapping, runtime result
  integration, and synthetic second-provider validation.
- Default validation stays offline and deterministic.

## Success Criteria

- Generic usage/cost evidence exists under `agent_runtime` and is independent of
  Codex backend details.
- Usage evidence can represent present, partial, unavailable, unsupported, and
  failed collection states.
- Token categories are optional and distinguish absent values from
  provider-reported zero.
- Cost evidence explicitly represents unknown, unavailable, subscription,
  public, and manual states without requiring cost estimates.
- Codex mapping preserves safe normalized facts only and never exposes raw
  payloads, account IDs, auth material, cookies, or billing content.
- `LocalAgentRunResult` can carry multiple usage and cost evidence items while
  remaining valid when evidence is absent.
- Existing tests continue to pass; new tests cover the spec's evidence and
  pricing cases.

## Constraints and Non-Goals

- Do **not** calculate exact Codex pricing in v1.
- Do **not** scrape billing pages or persist raw provider payloads.
- Do **not** add live probes to default tests or quality gates.
- Do **not** create a new `model_usage` feature slice in v1.
- Do **not** add generic provider-specific extension maps to the usage DTO.
- Do **not** introduce pricing/catalog/currency dependencies without asking
  first.
- Preserve hexagonal boundaries: generic boundary DTOs live in `agent_runtime`;
  provider extraction/mapping remains provider-owned.

## Architecture Decisions

- **Generic DTO ownership:** Put v1 DTOs in
  `src/fabrica/features/agent_runtime/application/dtos/usage.py` because the
  evidence is an application boundary concern for local model-call results, not a
  Codex domain object.
- **Cost as sibling evidence:** Model `ModelCostEvidence` separately from
  `ModelUsageEvidence` so usage remains useful when pricing is unknown.
- **Multiple provenance items:** Store tuples on runtime/model results so
  response payload, stream events, headers, and usage endpoints can each
  contribute evidence with separate source/confidence.
- **Codex mapping boundary:** Raw Codex response/SSE parsing stays adapter-local.
  The adapter extracts only safe bounded facts, then Codex application mapping
  converts those facts into generic evidence DTOs. Runtime adapters only
  propagate already-normalized generic DTOs.
- **Synthetic second provider only:** Validate the generic shape with a
  deterministic OpenAI-style fixture/test rather than adding a live provider
  integration.
- **Money amount representation:** Use standard-library `Decimal` for v1
  monetary estimate amounts and an uppercase currency string. Do not introduce a
  pricing/catalog/currency dependency without asking first.
- **Failure evidence:** `CodexTransportResult` may carry usage/cost evidence on
  non-success results when that evidence explicitly explains failed or
  unavailable collection; failures must not fabricate token counts or amounts.

## Progress Tracking Requirement

Treat this plan as a living artifact during implementation. After each completed
task or meaningful scope change:

- check off completed task, acceptance criteria, verification, and checkpoint
  items;
- leave unverified items unchecked;
- add discovered work or sequencing changes;
- record blockers, assumptions, and deviations that affect remaining work.

## Task List

### Phase 1: Generic Evidence DTO Foundation

#### Task 1: Add generic usage and cost evidence DTOs

**Description:** Add immutable, provider-agnostic application DTOs and closed
vocabularies under `agent_runtime/application/dtos/usage.py`.

**Acceptance criteria:**

- [x] Defines closed `StrEnum` vocabularies for collection status, evidence
  source, confidence, and pricing status.
- [x] Collection status values are exactly `collected`,
  `partially_collected`, `unavailable`, `unsupported`, and `failed` for v1.
- [x] Confidence values are exactly `observed`, `extracted`, `inferred`,
  `manual`, `estimated`, and `unknown` for v1.
- [x] Defines immutable DTOs for token evidence, quota/rate-limit evidence,
  usage evidence, and cost evidence.
- [x] Token counts and quota values reject negative integers.
- [x] Missing token categories remain `None`, not zero.
- [x] Monetary estimates use standard-library `Decimal` for `estimated_amount`
  and require amount, uppercase currency, source, and confidence when
  applicable.
- [x] Unknown/unavailable/subscription pricing does not require or imply a
  per-call amount.
- [x] Defines a dedicated generic `ModelUsageObservation` DTO with safe bounded
  scalar metadata.
- [x] Observation metadata rejects non-string keys and nested/raw values, copies
  inputs, and exposes immutable mapping views consistent with existing DTO style.

**Verification:**

- [x] `uv run pytest tests/unit/features/agent_runtime/application/test_usage_dtos.py`
- [x] `uv run ty check src tests`

**Dependencies:** None

**Files likely touched:**

- `src/fabrica/features/agent_runtime/application/dtos/usage.py`
- `src/fabrica/features/agent_runtime/application/dtos/__init__.py`
- `tests/unit/features/agent_runtime/application/test_usage_dtos.py`

**Estimated scope:** Medium

#### Task 2: Attach evidence tuples to local runtime results

**Description:** Extend `LocalAgentRunResult` with optional `usage_evidence` and
`cost_evidence` tuples while keeping existing no-evidence behavior unchanged.

**Acceptance criteria:**

- [ ] `LocalAgentRunResult` exposes
  `usage_evidence: tuple[ModelUsageEvidence, ...]` defaulting to `()`.
- [ ] `LocalAgentRunResult` exposes
  `cost_evidence: tuple[ModelCostEvidence, ...]` defaulting to `()`.
- [ ] Constructor normalizes provided iterables to tuples if project style
  chooses explicit normalization.
- [ ] Existing runtime result tests still pass with default empty evidence.
- [ ] New test proves evidence is carried immutably and does not affect
  `succeeded` semantics.

**Verification:**

- [ ] `uv run pytest tests/unit/features/agent_runtime/application/test_runtime_dtos.py tests/unit/features/agent_runtime/application/test_usage_dtos.py`

**Dependencies:** Task 1

**Files likely touched:**

- `src/fabrica/features/agent_runtime/application/dtos/runtime.py`
- `tests/unit/features/agent_runtime/application/test_runtime_dtos.py`

**Estimated scope:** Small

#### Task 3: Attach evidence tuples to Codex transport results

**Description:** Extend `CodexTransportResult` with optional generic
`usage_evidence` and `cost_evidence` tuples so Codex completion mapping can pass
normalized evidence through the existing transport-backed runtime adapter.

**Acceptance criteria:**

- [ ] `CodexTransportResult` exposes
  `usage_evidence: tuple[ModelUsageEvidence, ...]` defaulting to `()`.
- [ ] `CodexTransportResult` exposes
  `cost_evidence: tuple[ModelCostEvidence, ...]` defaulting to `()`.
- [ ] Evidence tuples may be populated on non-success results when they explain
  failed or unavailable collection.
- [ ] Failure results do not fabricate token counts, monetary amounts, or exact
  Codex pricing.
- [ ] Existing `output_text` success/non-success validation remains unchanged.

**Verification:**

- [ ] `uv run pytest tests/unit/features/codex_transport/application/test_transport_dtos.py tests/unit/features/agent_runtime/application/test_usage_dtos.py`

**Dependencies:** Task 1

**Files likely touched:**

- `src/fabrica/features/codex_transport/application/dtos/transport.py`
- `tests/unit/features/codex_transport/application/test_transport_dtos.py`

**Estimated scope:** Small

### Checkpoint: Generic Contract

- [ ] Agent runtime DTO tests pass.
- [ ] Generic DTO names and enum values match the spec.
- [ ] No Codex-specific fields or provider extension maps were added to generic
  DTOs.
- [ ] `LocalAgentRunResult` and `CodexTransportResult` can both carry generic
  evidence tuples without requiring evidence to be present.

### Phase 2: Codex Mapping

#### Task 4: Add Codex completion-response safe fact extraction and usage mapping

**Description:** Extract safe Codex response/stream usage facts from completion
responses at the adapter boundary, then map those safe facts into generic
usage/cost evidence in Codex application code when present. Represent missing or
partial evidence explicitly.

**Acceptance criteria:**

- [ ] Raw Codex response bodies and SSE payloads are parsed only in the outbound
  adapter or adapter-local helpers.
- [ ] Only safe bounded facts cross from adapter extraction into Codex
  application mapping.
- [ ] Safe response usage maps input/output/total/cached/reasoning token fields
  where present.
- [ ] Missing usage yields unavailable or partially collected usage evidence with
  a redacted observation.
- [ ] Partial usage preserves only categories actually reported.
- [ ] Pricing evidence for Codex defaults to unknown, unavailable, or
  subscription-oriented status with source/confidence.
- [ ] Raw provider response bodies and unsafe fields are not exposed in DTOs or
  observations.
- [ ] `tests/unit/features/codex_transport/application/test_usage_mapping.py` is
  the required boundary test for generic evidence conversion.

**Verification:**

- [ ] `uv run pytest tests/unit/features/codex_transport/application/test_usage_mapping.py`
- [ ] `uv run pytest tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_response_mapper.py`

**Dependencies:** Tasks 1-3

**Files likely touched:**

- `src/fabrica/features/codex_transport/application/usage_mapping.py` or
  equivalent provider-owned mapper
- `src/fabrica/features/codex_transport/adapters/outbound/codex_backend_http/response_mapper.py`
- `src/fabrica/features/codex_transport/application/dtos/transport.py`
- `tests/unit/features/codex_transport/application/test_usage_mapping.py`
- `tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_response_mapper.py`

**Estimated scope:** Medium

#### Task 5: Map Codex usage-endpoint evidence to generic quota/rate-limit evidence

**Description:** Translate existing `CodexUsageEvidence` scalar maps into
provider-agnostic usage evidence where values are safely known.

**Acceptance criteria:**

- [ ] `limit`, `remaining`, `reset_at`, and `window_seconds` are populated only
  when safely known and type-valid.
- [ ] Provider-specific safe facts such as plan/tier/usage percent are
  represented only as bounded redacted observations.
- [ ] Status mapping distinguishes collected, partially collected, unavailable,
  failed, and unsupported cases where possible.
- [ ] Status mapping follows the v1 status table in this plan.
- [ ] Unsafe raw keys/values remain filtered by existing allowlist behavior or
  stronger checks.

**Verification:**

- [ ] `uv run pytest tests/unit/features/codex_transport/application/test_usage_mapping.py`
- [ ] `uv run pytest tests/unit/features/codex_transport/application/test_probe_codex_usage.py`

**Dependencies:** Tasks 1 and 4

**Files likely touched:**

- `src/fabrica/features/codex_transport/application/usage_mapping.py`
- `tests/unit/features/codex_transport/application/test_usage_mapping.py`
- Existing usage DTO/use-case tests as needed

**Estimated scope:** Medium

#### Task 6: Propagate Codex evidence through transport-backed runtime adapter

**Description:** Ensure the Codex transport runtime adapter copies generic
usage/cost evidence from `CodexTransportResult` into `LocalAgentRunResult`.

**Acceptance criteria:**

- [ ] `CodexTransportResult` can carry generic usage and cost evidence tuples.
- [ ] `CodexTransportAgentModel.run()` passes evidence through to
  `LocalAgentRunResult`.
- [ ] Failure results do not fabricate token/cost values.
- [ ] Non-success transport results may propagate failed/unavailable evidence
  tuples when the upstream result provides them.
- [ ] Existing observation mapping behavior remains unchanged.

**Verification:**

- [ ] `uv run pytest tests/unit/features/agent_runtime/ tests/unit/features/codex_transport/application/`

**Dependencies:** Tasks 2-4

**Files likely touched:**

- `src/fabrica/features/codex_transport/application/dtos/transport.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/codex_transport_model/adapter.py`
- `tests/unit/features/codex_transport/application/test_transport_dtos.py`
- Existing or new codex transport model adapter tests

**Estimated scope:** Small to Medium

### Checkpoint: Codex Evidence Path

- [ ] Codex mapping tests cover present, missing, partial, quota/rate-limit,
  unknown-pricing, and unsafe-field cases.
- [ ] Runtime adapter tests prove evidence reaches `LocalAgentRunResult`.
- [ ] No live Codex probe is required for default tests.

### V1 Codex-to-Generic Status Mapping

Use this table for Codex response and usage-endpoint mapping unless
implementation evidence reveals a necessary deviation. Record any deviation in
this plan or the spec before handoff.

| Codex evidence condition | Generic collection status | Notes |
| --- | --- | --- |
| Successful response or usage endpoint with all relevant safe fields present | `collected` | Preserve only categories actually reported. |
| Successful response or usage endpoint with some, but not all, relevant safe fields present | `partially_collected` | Missing token/quota categories remain `None`, not zero. |
| Successful response with no usable usage fields, backend shape mismatch, rate-limit without usable quota facts, or quota-exceeded without usable quota facts | `unavailable` | Include a redacted observation explaining why evidence is unavailable. |
| Capability or endpoint is not implemented for the provider | `unsupported` | Use only when the provider/integration explicitly lacks the capability. |
| Authentication failure, credential error, transport error, or mapper failure | `failed` | Do not fabricate token counts, quota values, monetary amounts, or exact pricing. |
| Rate-limit or quota response with safe limit/remaining/reset/window facts | `partially_collected` | Attach quota/rate-limit evidence even when completion token evidence is unavailable. |

Codex pricing evidence should default to `unknown`, `not_available`, or
`subscription_included` depending on the evidence source. Public-price and manual
estimates require explicit amount, currency, source, and confidence and must not
be represented as exact subscription-backed Codex cost.

### Phase 3: Second-Provider Validation and Finalization

#### Task 7: Add synthetic OpenAI-style provider validation

**Description:** Add a focused synthetic mapper/test fixture showing that the
generic contract can represent a conventional API-style token usage response and
optional public-price estimate without Codex assumptions.

**Acceptance criteria:**

- [ ] Synthetic response maps prompt/input, completion/output, and total tokens
  into the same generic DTOs.
- [ ] Optional public-price estimate is represented as estimated cost evidence
  with amount, currency, source, and confidence.
- [ ] Test code does not introduce a new live provider integration or runtime
  dependency.
- [ ] The synthetic provider mapper lives in test code only unless a real
  provider integration is explicitly requested.
- [ ] The generic DTO remains free of Codex-specific assumptions.

**Verification:**

- [ ] `uv run pytest tests/unit/features/agent_runtime/application/test_usage_dtos.py`
- [ ] `uv run pytest tests/unit/features/agent_runtime/application/test_synthetic_provider_usage_mapping.py` if a separate test module is created

**Dependencies:** Task 1

**Files likely touched:**

- `tests/unit/features/agent_runtime/application/test_synthetic_provider_usage_mapping.py`
- Optionally `tests/unit/features/agent_runtime/application/test_usage_dtos.py`

**Estimated scope:** Small

#### Task 8: Review exports, documentation impact, and validation commands

**Description:** Finalize public exports and run the configured quality gate.
Update documentation only if implementation changes user-visible usage,
configuration, or CLI behavior.

**Acceptance criteria:**

- [ ] Public DTOs needed by adapters/tests are exported from
  `agent_runtime.application.dtos`.
- [ ] No README/docs update is needed unless CLI/user-visible output changes; if
  it does, update docs accordingly.
- [ ] If implementation enum names, field names, status mappings, or DTO shapes
  differ from the spec or this plan, update the spec or record a plan deviation.
- [ ] Full quality gate commands pass or any unrun/failing checks are documented
  with reason.

**Verification:**

- [ ] `uv run ruff format .`
- [ ] `uv run ruff check .`
- [ ] `uv run ty check src tests`
- [ ] `uv run pytest`

**Dependencies:** Tasks 1-7

**Files likely touched:**

- `src/fabrica/features/agent_runtime/application/dtos/__init__.py`
- `README.md` only if output/usage docs change
- Possibly `docs/specs/provider-agnostic-usage-cost-evidence-spec.md` only if
  implementation reveals a spec correction

**Estimated scope:** Small

### Checkpoint: Complete

- [ ] All task acceptance criteria are complete.
- [ ] Full local quality gate passes.
- [ ] Handoff notes include files changed, validation performed, assumptions, and
  any deviations.
- [ ] No raw provider payloads, account IDs, secrets, auth headers, cookies, or
  billing-page content are introduced.

## Dependency Graph

```text
Generic evidence DTOs
  -> LocalAgentRunResult evidence fields
  -> CodexTransportResult evidence fields
    -> Adapter-local Codex safe fact extraction
      -> Codex application usage/cost evidence mapping
        -> CodexTransportAgentModel evidence propagation
  -> Synthetic conventional provider validation
  -> Full quality gate and docs review
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Generic DTO becomes Codex-shaped | High | Require synthetic OpenAI-style validation before considering DTO stable. |
| Codex raw/private data leaks into observations | High | Keep mapping allowlist-based; assert unsafe strings do not appear in tests. |
| Pricing appears more exact than evidence supports | High | Use explicit pricing status/source/confidence and default Codex to unknown/unavailable/subscription-oriented. |
| Existing runtime result consumers break | Medium | Add evidence fields with tuple defaults and preserve existing constructor behavior where possible. |
| `response_mapper.py` grows beyond its current mixed responsibilities | Medium | Keep raw response/SSE parsing adapter-local but move generic evidence conversion into `codex_transport/application/usage_mapping.py`. |
| Type imports create cross-slice boundary confusion | Medium | Let Codex adapter/application import generic application boundary DTOs only; do not import agent runtime internals outside DTO contracts. |

## Open Questions

None blocking for the implementation plan. The spec has resolved the earlier
placement and modeling questions for v1, and plan-review interview decisions are
captured in the architecture decisions above.

## Assumptions

- Exact Codex cost remains intentionally unknowable in v1.
- Generic evidence DTOs are application boundary DTOs, not shared-kernel domain
  concepts.
- It is acceptable for Codex transport DTOs/adapters to import `agent_runtime`
  usage DTOs as published boundary types for model-call evidence.
- The initial implementation can focus on unit-test-backed deterministic mapping
  and not add CLI output formatting for evidence unless explicitly requested
  later.
- Synthetic second-provider validation is test-local in v1 and does not publish a
  real provider integration.

## Parallelization Opportunities

- Task 7 can be developed in parallel after Task 1 is complete.
- Task 5 can start after Task 4 establishes the shared Codex application mapping
  helpers and status table behavior.
- Task 8 must be last.
