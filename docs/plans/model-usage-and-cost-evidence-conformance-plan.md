# Model Usage and Cost Evidence Conformance Plan

## Status

- **Readiness:** Ready.
- **Created:** September 4, 2026.
- **Source of truth:** `docs/specs/model-usage-and-cost-evidence-spec.md`.
- **Working-tree discipline:** Check `git --no-pager status --short` immediately
  before implementation and again before handoff; record any pre-existing changes
  separately from this conformance work.
- **Resolved implementation decision:** Retain the existing `ModelCostEvidence`
  and `cost_evidence` names as independent result-level collections, but make
  their Version 1 contents strictly non-monetary pricing-state evidence. Do not
  add compatibility shims or a new `model_usage` feature slice.
- **Plan maintenance:** During implementation, update both the Progress Tracking
  checkbox and the matching detailed-task checkbox after each completed task,
  validation result, scope change, blocker, or newly discovered work. Keep
  unverified work unchecked.

## Goal

Bring the existing evidence implementation into conformance with the accepted
Version 1 specification by removing monetary estimate vocabulary, bounding
generic observation metadata, and making Codex-owned metadata allowlisting
explicit and testable.

## Audit Findings

The current implementation already has provider-neutral evidence DTOs, Codex
completion and usage-endpoint mapping, runtime propagation, CLI presentation,
and deterministic offline coverage. The remaining accepted-Version-1 gaps are:

1. `ModelPricingStatus` still includes `public_price_estimate` and
   `manual_estimate`; `ModelCostEvidence` still exposes `estimated_amount` and
   `currency`; production code and tests still use `Decimal` estimate semantics.
2. `ModelUsageObservation` bounds its message but not metadata keys or string
   metadata values.
3. The Codex usage-endpoint mapper has a safe-key allowlist, but provider-owned
   generic-evidence metadata construction and direct unsafe-field exclusion
   coverage need to be more explicit.
4. Synthetic conventional-provider and CLI tests still validate monetary
   estimates rather than the accepted non-monetary pricing-state boundary.

## Scope

### In Scope

- Restrict pricing states to `unknown`, `not_available`,
  `subscription_included`, and `unsupported`.
- Remove monetary fields, decimal/currency validation, exports, rendering,
  fixtures, and assertions.
- Add named bounds for generic observation metadata keys and string values.
- Keep generic observation validation to scalar/type/length validation;
  provider-specific redaction remains provider-owned.
- Make Codex generic-evidence metadata allowlists explicit and test unsafe-field
  exclusion.
- Update affected unit, runtime, transport, and CLI tests.
- Clarify the `--print-prices` help text as non-monetary pricing-state evidence
  while retaining the established command name.
- Run focused checks and the full configured quality gate.

### Out of Scope

- Renaming `ModelCostEvidence`, `cost_evidence`, or `--print-prices`.
- A second production provider adapter or generic provider-extension contract.
- Pairing pricing-state evidence to a usage item, call, or invocation.
- Currency, decimal-money arithmetic, public prices, estimates, price catalogs,
  billing integrations, or account/billing-page scraping.
- Live Codex probes in default tests, CI, or the quality gate.

## Dependency Order

```text
Shared non-monetary evidence contract and observation bounds
 ├─> Codex mapper allowlist tightening and mapping tests
 ├─> Synthetic conventional-provider validation cleanup
 └─> CLI presentation and downstream result/adapter tests
      └─> Focused validation, full quality gate, documentation review
```

Tasks MUCE-1 and MUCE-2 are foundational. Tasks MUCE-3 and MUCE-4 may proceed
in parallel after their contract changes are complete.

## Progress Tracking

- [x] **MUCE-1** Remove Version 1 monetary pricing vocabulary from shared
  evidence contracts.
- [x] **MUCE-2** Enforce generic observation metadata key and string-value
  bounds.
- [x] **MUCE-3** Make Codex generic-evidence metadata allowlists explicit and
  test unsafe-field exclusion.
- [x] **MUCE-4** Align synthetic-provider, runtime/transport, and CLI evidence
  tests with non-monetary pricing states.
- [x] **MUCE-5** Complete focused and full validation and review documentation
  consistency.

## Detailed Tasks

### MUCE-1 — Remove Version 1 monetary pricing vocabulary from shared evidence contracts

- [x] **MUCE-1** Update the shared evidence contract to eliminate monetary
  estimate semantics.

**Likely files**

- `src/fabrica/shared_kernel/model_usage.py`
- `src/fabrica/shared_kernel/__init__.py`
- `src/fabrica/features/agent_runtime/application/dtos/__init__.py`
- `tests/unit/shared_kernel/test_model_usage.py`

**Implementation requirements**

- Remove the `decimal.Decimal` import, `MODEL_USAGE_CURRENCY_CODE_CHARS`, and
  their relevant exports.
- Restrict `ModelPricingStatus` to `UNKNOWN`, `NOT_AVAILABLE`,
  `SUBSCRIPTION_INCLUDED`, and `UNSUPPORTED`.
- Remove `estimated_amount` and `currency` from `ModelCostEvidence`.
- Delete estimate-specific validation and paired-field validation.
- Update docstrings to state that `ModelCostEvidence` represents independent,
  non-monetary result-level pricing-state evidence.
- Replace estimate-oriented tests with exact Version 1 vocabulary and immutable
  boundary-value assertions.

**Acceptance criteria**

- [x] **MUCE-1-A** Production source contains no `Decimal`, `estimated_amount`,
  `currency`, `public_price_estimate`, or `manual_estimate` vocabulary.
- [x] **MUCE-1-B** `ModelPricingStatus` exactly matches the accepted Version 1
  state set.
- [x] **MUCE-1-C** `ModelCostEvidence` contains pricing status, source,
  confidence, and observations only.
- [x] **MUCE-1-D** Existing immutability and tuple-boundary behavior remains
  intact.

**Verification**

```bash
uv run pytest tests/unit/shared_kernel/test_model_usage.py
uv run ruff check src/fabrica/shared_kernel tests/unit/shared_kernel/test_model_usage.py
uv run ty check src tests
```

### MUCE-2 — Enforce generic observation metadata key and string-value bounds

- [x] **MUCE-2** Add and enforce documented generic metadata bounds.

**Likely files**

- `src/fabrica/shared_kernel/model_usage.py`
- `src/fabrica/shared_kernel/__init__.py`
- `src/fabrica/features/agent_runtime/application/dtos/__init__.py`
- `tests/unit/shared_kernel/test_model_usage.py`

**Implementation requirements**

- Retain `DEFAULT_MAX_MODEL_USAGE_OBSERVATION_MESSAGE_CHARS = 240`.
- Add named public constants for metadata key length and string metadata value
  length.
- Use a maximum metadata key length of 80 characters and a maximum string-value
  length of 240 characters.
- Require metadata keys to be non-empty strings within their bound.
- Continue allowing only `str`, `int`, `float`, `bool`, and `None` scalar
  metadata values; require strings to meet their bound.
- Preserve immutable copied metadata through `MappingProxyType`.
- Do not implement redaction, key-name secret detection, recursive validation,
  or provider-specific semantic checks in the generic DTO.

**Acceptance criteria**

- [x] **MUCE-2-A** Empty, oversized, and non-string metadata keys are rejected.
- [x] **MUCE-2-B** Oversized string metadata values are rejected.
- [x] **MUCE-2-C** Valid scalar metadata remains accepted and immutable.
- [x] **MUCE-2-D** Message, key, and string-value bounds have focused boundary
  tests.
- [x] **MUCE-2-E** Generic validation does not claim to redact secrets.

**Verification**

```bash
uv run pytest tests/unit/shared_kernel/test_model_usage.py
uv run ruff check src/fabrica/shared_kernel tests/unit/shared_kernel/test_model_usage.py
```

### MUCE-3 — Make Codex generic-evidence metadata allowlists explicit

- [x] **MUCE-3** Ensure Codex-owned generic-evidence paths construct only
  explicitly allowlisted metadata and test unsafe-field exclusion.

**Likely files**

- `src/fabrica/features/codex_transport/application/mappers/completion_usage.py`
- `src/fabrica/features/codex_transport/application/mappers/usage_endpoint.py`
- `src/fabrica/features/codex_transport/application/mappers/generic_usage_evidence.py`
  if a narrow shared Codex-only helper or constants improve cohesion
- `tests/unit/features/codex_transport/application/test_usage_mapping.py`
- `tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_response_mapper.py`

**Implementation requirements**

- Keep provider-payload extraction and safe metadata selection within the Codex
  transport slice; do not move these duties into `shared_kernel`.
- Define explicit safe metadata construction for completion usage, completion
  pricing-state, usage-endpoint usage, and usage-endpoint pricing-state
  observations.
- Preserve only safe operational facts such as provider label, normalized Codex
  status, collection status, quota field count, and intentionally allowlisted
  plan/rate-limit summaries.
- Accept usage-endpoint metadata only when its key is allowlisted and its value
  is scalar and within generic bounds.
- Exclude account IDs, tokens, authentication headers, cookies, raw payloads,
  private endpoint details, and billing-page content before generic evidence DTO
  construction.
- Preserve all safe token and provider-local quota facts independently of the
  pricing state.

**Acceptance criteria**

- [x] **MUCE-3-A** Every Codex generic-evidence observation path uses explicit
  provider-owned safe metadata construction.
- [x] **MUCE-3-B** Secret-like, account-like, cookie/header-like, raw-body, and
  private-endpoint-like values are absent from emitted generic metadata.
- [x] **MUCE-3-C** Completion and usage-endpoint mappings continue to emit one
  explicit non-monetary pricing-state item for each subscription-backed result.
- [x] **MUCE-3-D** Tests inspect emitted metadata mappings directly rather than
  relying only on string rendering.
- [x] **MUCE-3-E** Oversized allowlisted string values are safely dropped before
  generic observation construction, or otherwise handled without leaking them.

**Verification**

```bash
uv run pytest tests/unit/features/codex_transport/application/test_usage_mapping.py
uv run pytest tests/unit/features/codex_transport/adapters/outbound/codex_backend_http/test_response_mapper.py
uv run ruff check src/fabrica/features/codex_transport tests/unit/features/codex_transport
```

### MUCE-4 — Align synthetic-provider, runtime/transport, and CLI tests

- [x] **MUCE-4** Remove monetary evidence behavior from presentation and
  validation fixtures while preserving result-level pricing-state reporting.

**Likely files**

- `src/fabrica/adapters/inbound/cli/model_evidence.py`
- `src/fabrica/adapters/inbound/cli/options.py`
- `tests/unit/adapters/inbound/cli/test_output.py`
- `tests/unit/adapters/inbound/cli/test_shell.py`
- `tests/unit/features/agent_runtime/application/test_synthetic_provider_usage_mapping.py`
- `tests/unit/features/agent_runtime/application/test_runtime_dtos.py`
- `tests/unit/features/agent_runtime/adapters/outbound/codex_transport_model/test_adapter.py`
- `tests/unit/features/codex_transport/application/test_transport_dtos.py`
- Any additional downstream tests identified by a final monetary-vocabulary
  search.

**Implementation requirements**

- Remove amount/currency rendering from CLI pricing evidence output.
- Preserve CLI output of pricing status, source, confidence, and bounded safe
  observation details.
- Update CLI tests to use a supported non-monetary pricing state.
- Reduce the synthetic conventional API-style fixture to normal model/input/
  output/total token mapping only.
- Remove synthetic public-price estimate dataclasses, mapping helper, imports,
  and tests.
- Assert that conventional API-style synthetic usage may yield an empty
  `cost_evidence` tuple.
- Replace downstream assertions for removed monetary fields with assertions on
  pricing status, provenance, confidence, and independent evidence tuples.
- Update `--print-prices` help wording to clarify that it prints non-monetary
  pricing-state evidence, without renaming the command surface.

**Acceptance criteria**

- [x] **MUCE-4-A** CLI output never renders a monetary amount or currency.
- [x] **MUCE-4-B** CLI pricing evidence remains clear as non-monetary state plus
  provenance and confidence.
- [x] **MUCE-4-C** `--print-prices` help describes non-monetary pricing-state
  evidence without renaming the command surface.
- [x] **MUCE-4-D** Synthetic provider validation covers only generic token
  evidence and an allowed empty pricing-state tuple.
- [x] **MUCE-4-E** Runtime and transport tests preserve independent usage and
  cost-evidence collections without positional correlation.

**Verification**

```bash
uv run pytest tests/unit/adapters/inbound/cli/test_output.py
uv run pytest tests/unit/adapters/inbound/cli/test_shell.py
uv run pytest tests/unit/features/agent_runtime/application/test_synthetic_provider_usage_mapping.py
uv run pytest tests/unit/features/agent_runtime/application/test_runtime_dtos.py
uv run pytest tests/unit/features/agent_runtime/adapters/outbound/codex_transport_model/test_adapter.py
uv run pytest tests/unit/features/codex_transport/application/test_transport_dtos.py
```

### MUCE-5 — Complete conformance validation and documentation review

- [x] **MUCE-5** Perform final regression, quality-gate, and consistency checks.

**Likely files**

- No documentation edit is expected unless a final review finds CLI help or
  project documentation that implies monetary estimates or billing attribution.
- Review `README.md`, `docs/README.md`, `docs/specs/README.md`, and the accepted
  evidence specification for accuracy after implementation.

**Implementation requirements**

- Search executable production code, tests, and user-facing CLI text for removed
  monetary vocabulary:
  `Decimal`, `estimated_amount`, `currency`, `public_price_estimate`,
  `manual_estimate`, and `MODEL_USAGE_CURRENCY_CODE_CHARS`.
- Review documentation matches separately. The accepted evidence specification
  may retain deferred monetary vocabulary solely to describe work excluded from
  Version 1; no user-facing documentation or CLI help may imply exact cost or
  subscription billing attribution.
- Confirm documentation and CLI help describe non-monetary pricing-state
  evidence and do not imply exact cost or subscription billing attribution.
- Confirm default checks remain offline and deterministic.
- Inspect the final diff for unrelated churn, live probes, credentials, raw
  payloads, or billing data.

**Acceptance criteria**

- [x] **MUCE-5-A** No removed monetary identifier remains in executable
  production code, tests, or user-facing CLI text.
- [x] **MUCE-5-B** Documentation and CLI help do not imply exact cost or
  subscription billing attribution.
- [x] **MUCE-5-C** Default validation remains offline and deterministic.
- [x] **MUCE-5-D** Formatting, linting, type checking, import-linter contracts,
  and the complete test suite pass with no unapproved failures.

**Verification**

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check src tests
uv run lint-imports
uv run pytest
```

**Completed validation — September 4, 2026**

- Exact-identifier scan found no removed monetary identifiers in executable
  Python source or tests.
- Focused evidence coverage passed: 126 tests passed with `--no-cov`; the
  repository-wide coverage threshold intentionally requires the full suite.
- Full quality gate passed: `ruff format --check`, `ruff check`, `ty check src
  tests`, `lint-imports`, and the offline `pytest` suite (1,736 passed, 3
  skipped, 93.03% coverage).
- Documentation and CLI help were reviewed. The accepted specification status
  was corrected to reflect completed Version 1 conformance; no user-facing text
  implies monetary cost or subscription billing attribution.

## Risks and Guardrails

- `ModelCostEvidence` is a legacy name only; it must not justify new monetary
  semantics in Version 1.
- Generic DTO validation is not a redaction engine. Provider-owned mappers must
  select safe metadata before construction.
- New generic bounds can cause current mapper strings to fail construction;
  mapper tests must cover oversized allowlisted values.
- Do not create a `model_usage` feature slice. The current shared-kernel DTO and
  provider-owned mapper boundaries satisfy the accepted architecture.
- Do not add compatibility aliases, pricing dependencies, live test expansion,
  or command renames as part of this work.
