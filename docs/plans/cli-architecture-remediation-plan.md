# Implementation Plan: CLI Architecture Remediation

## Overview

Remediate the CLI architecture audit findings by tightening vertical-slice boundaries, moving concrete CLI wiring into bootstrap, removing the global CLI dependency bag, aligning tests with feature ownership, and strengthening automated architecture contracts. CLI command names, options, output labels, safety gates, and documented exit-code semantics should remain unchanged.

## Architecture Decisions

- Developer workflow owns its inbound result contracts. Its application ports and CLI adapters must not expose `agent_runtime` result/status/observation DTOs.
- Generic model usage and cost evidence belongs in `shared_kernel.model_usage`; complete runtime result families remain slice-owned.
- Agent-runtime DTO translation for commit-message generation belongs inside the developer-workflow outbound adapter package.
- Concrete use-case and adapter selection belongs in bootstrap, not inside feature application use cases or sibling adapters.
- Generic CLI parser/runner modules receive composed contributions explicitly; bootstrap owns default contribution composition.
- Contributions close over their own dependency providers instead of relying on a shell-owned dependency bag listing every feature.
- The product output layer may intentionally render multiple published result families at the product edge, but one feature slice must not publish another slice's DTOs as its own boundary.

## Progress Tracking

Treat this plan as a living document throughout implementation. After each completed task or meaningful change:

- check off completed tasks, acceptance criteria, verification items, and checkpoints
- leave unfinished or unverified items unchecked
- add newly discovered work and update sequencing when scope or dependencies change
- note blockers, deviations, and decisions that affect remaining work

## Task List

### Phase 1: Complete Required Boundary Repairs

- [x] Task 1: Finish developer-workflow-owned result contracts
- [x] Task 2: Translate agent-runtime behavior inside the outbound adapter
- [x] Task 3: Finalize query-executor injection
- [x] Task 4: Finalize metadata-loader injection into subprocess execution

#### Checkpoint: Required Findings 1-3

- [x] Focused developer-workflow tests pass without coverage enforcement
- [x] Focused subprocess adapter tests pass without coverage enforcement
- [x] Existing import-linter contracts pass before strengthening

### Phase 2: Move CLI Composition to Bootstrap

- [x] Task 5: Make parser and dispatcher contribution-driven
- [x] Task 6: Create bootstrap-owned CLI composition
- [x] Task 7: Remove obsolete CLI composition surfaces and dead compatibility module

#### Checkpoint: CLI Composition

- [x] Help remains offline
- [x] Every existing command parses and dispatches through bootstrap-created contributions
- [x] No global feature dependency bag remains
- [x] Generic shell architecture contract passes with expanded protected modules

### Phase 3: Align Tests and Process Coverage

- [x] Task 8: Re-home feature CLI runner tests to mirrored feature paths
- [x] Task 9: Strengthen process-level entrypoint coverage

### Phase 4: Enforce and Document Architecture

- [x] Task 10: Strengthen import-linter contracts
- [x] Task 11: Record the architecture change in an ADR if the final bootstrap/contribution boundary remains materially different

#### Final Checkpoint

- [x] `uv run ruff check . --fix`
- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run ty check .`
- [x] `uv run lint-imports`
- [x] `uv run pytest`

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Existing staged remediation is inconsistent | Medium | Preserve existing changes, fix incrementally, and avoid reset/checkout operations. |
| CLI composition refactor can hide behavior loss | High | Keep observable output and exit-code assertions unchanged while moving tests. |
| Help could gain side effects | High | Keep providers lazy and retain module/console help process tests. |
| Import-linter wildcard contracts may not express sibling ownership well | Medium | Add narrow targeted contracts for known doctrine violations. |
| Product output still renders multiple result families | Low | Keep this as an intentional product-edge aggregation concern, not a feature boundary leak. |

## Open Questions

- None. The approved scope is all audit findings 1-8, including bootstrap CLI redesign, test moves, smoke tests, dead-module removal, and stronger import-linter contracts.
