# Test Plan: `submit_and_exit`

- **Readiness:** **Needs revision** — resolve SAE-00's completion-runtime,
  durable-storage, recovery, and presentation boundary before implementation.
- **Source specification:** `docs/specs/tools-submit-and-exit-tool-spec.md`

- **Specification status:** Accepted on September 3, 2026; not yet implemented.

- **Scope:** Version 1 contract, run lifecycle, persistence, and presentation test coverage.
- **Test tooling:** `pytest` via `uv`, `ruff`, `ty`, and `import-linter`.

This is a living test plan. During implementation, update the progress checkboxes
and add brief notes when scope, sequencing, or assumptions change. The deferred
design questions must be resolved before the affected implementation task is
marked complete.

## Scope and Non-Goals

### In scope

- Exact Version 1 model-facing schema for `submit_and_exit`.
- Atomic `CompletionRecord` and `RUNNING → COMPLETED` commit behavior.
- Solo terminal batching, required-completion mode, idempotency, guards, timeout,
  cancellation races, and single-render presentation.
- Integration with the current agent runtime, registered-tool flow, and optional
  `ask_question` composition.

### Out of scope

- Concrete CLI, UI, or web presenter implementations beyond the host-facing
  completion-presenter port and composition tests.
- Version 1 model-input fields for verification evidence, changed files, or
  verification commands.
- New outcome or verification enum values.
- Automatic retries for terminal submissions.

## Progress Tracking

- [x] SAE-00 Resolve completion runtime, durable storage, recovery, and presentation boundaries.
- [x] SAE-01 Define and test completion DTOs, schema, and record contracts.
- [x] SAE-02 Define and test run state and the atomic completion boundary.
- [x] SAE-03 Test the `submit_and_exit` inbound registered-tool adapter.
- [ ] SAE-04 Extend tool-loop tests for terminal batching and required-completion mode.
- [ ] SAE-05 Test guards, failures, idempotency, timeout, and cancellation races.
- [ ] SAE-06 Add integration coverage for storage, presentation, and interactive composition.
- [ ] SAE-07 Run the full quality gate and record validation evidence.

## Test Foundations

- Use deterministic in-memory fakes for completion storage, run state, guards,
  clock, cancellation, model turns, tool execution, and presentation.
- Use `asyncio` events and barriers for race-condition tests; do not sleep for 15
  seconds to test the submission deadline.
- Do not require live network, provider, filesystem, database, or UI services in
  the default suite.

## Ordered Test Work

### SAE-00 — Completion Runtime, Storage, Recovery, and Presentation Boundary

**Readiness gate:** Do not start SAE-01 through SAE-06 until the decisions below
are recorded in this plan. The current `RunToolLoop` can stop after a typed tool
outcome, but it does not own run IDs, run state, completion records, durable
storage, recovery, or completion presentation.

**Likely files**

- `src/fabrica/features/agent_runtime/application/dtos/`
- `src/fabrica/features/agent_runtime/application/ports/`
- `src/fabrica/features/agent_runtime/application/use_cases/`
- `src/fabrica/features/agent_runtime/application/dtos/tools.py`
- `src/fabrica/features/agent_runtime/application/use_cases/run_tool_loop.py`
- `src/fabrica/bootstrap/composition/`
- `tests/unit/features/agent_runtime/application/`
- `tests/integration/features/agent_runtime/`
- `pyproject.toml`, if the selected boundary requires an import-linter contract.

- [ ] SAE-00.1 Define the application-owned completion contracts.
  - **Decision required:** Name the DTOs, stable errors, `CompletionGuard`, atomic
    `commit_completion(run_id, record)` port, cancellation/state-transition
    ownership, and completion-presentation/recovery port.
  - **Acceptance:** The port atomically persists one immutable record and changes
    the same run from `RUNNING` to `COMPLETED`; it returns typed committed,
    already-completed, or cancelled outcomes without exposing infrastructure
    types through the registered-tool boundary.
- [ ] SAE-00.2 Select the Version 1 durable storage and recovery adapter.
  - **Decision required:** Identify the concrete adapter, its durable artifact or
    backing store, how a fresh composition reopens it, and the recovery-time
    exactly-once presentation idempotency key. An in-memory fake is sufficient
    for unit tests but cannot satisfy crash/restart recovery by itself.
  - **Fallback:** If Version 1 is intentionally limited to in-memory storage,
    defer SAE-06.2 recovery behavior and obtain a maintainer-approved
    specification revision before implementation begins.
- [ ] SAE-00.3 Define the host-facing completion runtime API and result/effect shape.
  - **Decision required:** Specify how a host generates an opaque run ID at
    `start_run()`, injects it into `ToolExecutionContext.opaque_values`, receives
    `CompletionCommitted(record)`, and exposes the canonical summary. Decide
    whether accepted completion adds a `COMPLETED` `ToolLoopRunStatus` and typed
    completion data to `ToolLoopRunResult`, or retains `SUCCESS` with an explicit
    completion effect.
  - **Acceptance:** A committed completion terminates without another model turn;
    presentation uses only the committed record summary, and ordinary terminal
    cleanup hooks cannot accidentally render failed or cancelled submissions.
- [ ] SAE-00.4 Define required-completion configuration and reminder transport.
  - **Decision required:** State whether registering `submit_and_exit`
    automatically enables required-completion mode, where the option/default
    lives, and how one bounded reminder reaches the next model turn despite the
    current model port accepting only command, definitions, tool results, and
    cancellation.
- [ ] SAE-00.5 Add boundary tests and validate architecture before lifecycle work.
  - **Verification:** Run focused DTO/port tests and `uv run lint-imports` after
    the boundary skeleton exists.

### SAE-01 — Completion DTOs, Schema, and Record Contracts

**Likely files**

- `tests/unit/features/agent_runtime/application/test_completion_dtos.py`
- Selected SAE-00 completion DTO module(s) under
  `src/fabrica/features/agent_runtime/application/dtos/`

- [ ] SAE-01.1 Test the exact public name, required fields,
      `additionalProperties=false`, and solo batch policy.
  - **Acceptance:** `outcome` is exactly `completed`, `partial`, `blocked`;
    `verification` is exactly `verified`, `not_verified`, `not_applicable`;
    `summary` is a string with length 1 through 12,000.
  - **Verification:** Parameterized valid and invalid schema/DTO tests.
- [ ] SAE-01.2 Test independent outcome and verification values.
  - **Acceptance:** All nine outcome/verification combinations are structurally
    valid, including `completed + not_verified`.
  - **Verification:** Parameterized matrix test.
- [ ] SAE-01.3 Test invalid input.
  - **Acceptance:** Missing or extra fields, unknown enums, empty/overbound/non-
    string summaries, and non-object payloads return `INVALID_INPUT`; no guard or
    persistence call occurs.
  - **Verification:** Assert fake guard and store collectors remain empty.
- [ ] SAE-01.4 Test immutable `CompletionRecord` behavior.
  - **Acceptance:** Record contains run ID, tool call ID, outcome, verification,
    summary, timezone-aware timestamp, and canonical payload digest.
  - **Verification:** Equivalent valid payloads hash stably; changed payloads have
    distinct digests.

### SAE-02 — Run State, Atomic Commit, and Submission Use Case

**Likely files**

- `tests/unit/features/agent_runtime/application/test_submit_run_completion.py`
- `tests/unit/features/agent_runtime/application/test_run_state_machine.py`
- Selected SAE-00 completion port and use-case module(s) under
  `src/fabrica/features/agent_runtime/application/`

- [ ] SAE-02.1 Test successful terminal submission from `RUNNING`.
  - **Acceptance:** Guard allow, record persistence, and `RUNNING → COMPLETED`
    commit together; result reports `accepted`.
  - **Verification:** Cover every outcome with at least one verification value.
- [ ] SAE-02.2 Test failed submission leaves the run active.
  - **Acceptance:** Validation, guard, persistence, timeout, and pre-commit
    cancellation failures leave no record and preserve `RUNNING`.
  - **Verification:** A subsequent valid submission succeeds.
- [ ] SAE-02.3 Test completion only from `RUNNING`.
  - **Acceptance:** `WAITING_FOR_USER`, `CANCELLED`, `ERROR`, and `COMPLETED`
    reject new submission; exact accepted duplicate replay is the sole exception.
  - **Verification:** State-machine parameterized tests.

### SAE-03 — Registered-Tool Adapter and Terminal Batch Barrier

**Likely files**

- `tests/unit/features/agent_runtime/adapters/inbound/registered_tool/test_submit_and_exit_adapter.py`
- `tests/unit/features/agent_runtime/application/test_run_tool_loop.py`
- Selected SAE-00 `submit_and_exit` registered-tool adapter module.

- [ ] SAE-03.1 Test adapter mapping.
  - **Acceptance:** Validated model arguments and host-controlled execution context
    reach the completion use case; success returns structured `accepted` content;
    application errors map to stable tool error codes.
  - **Verification:** Adapter never persists, retries, verifies work, or prompts a
    user directly.
- [ ] SAE-03.2 Test terminal solo batching.
  - **Acceptance:** `submit_and_exit` alone is allowed. A batch containing it plus
    `read_files`, `run_commands`, `apply_patch`, `ask_question`, or an ordinary
    tool is rejected before any tool executes.
  - **Verification:** Both execution recorders remain empty and the result carries
    `TERMINAL_TOOL_MIXED_WITH_OTHER_TOOLS` regardless of call ordering. Extend
    the current generic `REQUIRE_SOLO` handling so this terminal tool does not
    fall back to `TOOL_MUST_BE_SOLO`.

### SAE-04 — Required-Completion Runtime Behavior

**Likely files**

- Extend `tests/unit/features/agent_runtime/application/test_run_tool_loop.py`

- [ ] SAE-04.1 Test conversational mode.
  - **Acceptance:** Plain model text completes a run when the completion tool is
    not required; no record or reminder is produced.
- [ ] SAE-04.2 Test the first plain-text response in required-completion mode.
  - **Acceptance:** Text becomes a non-user-visible observation; exactly one
    reminder is added through the SAE-00.4-selected model-turn transport and
    consumes normal iteration budget.
- [ ] SAE-04.3 Test reminder followed by valid submission.
  - **Acceptance:** Only the submitted summary is rendered and no post-submission
    model turn occurs.
- [ ] SAE-04.4 Test ignored reminder and exhausted budget.
  - **Acceptance:** Stop with `COMPLETION_TOOL_REQUIRED`; do not issue a second
    reminder, create a record, or render plain text as a final answer.

### SAE-05 — Guards, Idempotency, Failures, and Races

- [ ] SAE-05.1 Test allowing and blocking completion guards.
  - **Acceptance:** A blocked guard preserves the active run, persists nothing,
    returns `COMPLETION_GUARD_FAILED`, and does not leak sensitive host context.
  - **Verification:** An optional stricter verification guard maps failure to
    `VERIFICATION_REQUIREMENT_NOT_MET` without adding model-input evidence fields.
- [ ] SAE-05.2 Test idempotency.
  - **Acceptance:** Repeating the same `(run_id, tool_call_id, tool_name,
    payload_digest)` returns the committed result or `already_accepted`, creates
    one record, and does not render twice. Different payload/tool name returns
    `IDEMPOTENCY_KEY_CONFLICT`; a different later terminal call returns
    `RUN_ALREADY_COMPLETED`.
- [ ] SAE-05.3 Test persistence, timeout, and internal failures.
  - **Acceptance:** `PERSISTENCE_ERROR`, `SUBMIT_TIMEOUT`, and
    `INTERNAL_COMPLETION_ERROR` leave no record and retain `RUNNING`; there are no
    automatic retries.
- [ ] SAE-05.4 Test cancellation races.
  - **Acceptance:** Whichever compare-and-set transition commits first,
    `COMPLETED` or `CANCELLED`, wins; never both. A completion record exists only
    when completion wins.
  - **Verification:** Cover cancellation before guard execution, during guard
    evaluation, immediately before atomic commit, and after durable commit but
    before presentation.

### SAE-06 — Integration and Presentation Coverage

**Likely files**

- `tests/integration/features/agent_runtime/test_submit_and_exit_composition.py`
- `tests/integration/features/agent_runtime/test_completion_store_composition.py`
- Extend `tests/integration/features/user_interaction/test_ask_question_composition.py`
- Selected SAE-00 durable store, recovery, and completion-presentation composition
  modules.

- [ ] SAE-06.1 Test synthetic-model end-to-end completion.
  - **Acceptance:** A sole terminal call commits completion, stops the run, and
    presents the committed summary. The synthetic model fails if called after the
    commit.
- [ ] SAE-06.2 Test presentation and recovery.
  - **Acceptance:** `CompletionRecord.summary` is rendered exactly once; executor
    acknowledgement prose is never a duplicate final answer. A crash after atomic
    commit retains the record and `COMPLETED` state for recovery-time presentation
    by a fresh composition that reopens the SAE-00.2-selected durable adapter.
- [ ] SAE-06.3 Test `ask_question` then `submit_and_exit`.
  - **Acceptance:** The answer result reaches the model, then a sole terminal call
    completes the run; owner and pending-interaction cleanup still occurs. Headless
    composition does not expose `ask_question` by default.

### SAE-07 — Quality Gate

- [ ] SAE-07.1 Run focused tests after each task before broader validation.
- [ ] SAE-07.2 Run the full repository gate before handoff:

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check src tests
uv run lint-imports
uv run pytest
```

## Resolved Design Decisions

The following design decisions were confirmed on September 3, 2026. They are
binding for Version 1 implementation and its dependent test work.

- [x] DQ-01 Keep generic registered-tool contracts in `agent_runtime` as
  application-owned contracts. Extract them to a neutral boundary only when a
  second feature has a concrete need.
- [x] DQ-02 The runtime host generates an opaque UUID or ULID when a run starts
  and propagates it through `ToolExecutionContext` for idempotency and completion
  record linkage. Model-facing tool arguments never include `run_id`.
- [x] DQ-03 Define one atomic outbound
  `commit_completion(run_id, record)` operation. It compare-and-sets
  `RUNNING → COMPLETED`, persists the `CompletionRecord`, and returns a typed
  `committed`, `already_completed`, or `cancelled` outcome.
- [x] DQ-04 The runtime emits typed effects, including
  `CompletionCommitted(record)`, for the host to render the committed summary
  exactly once. While required completion is pending, the runtime injects a
  structured reminder into each subsequent model turn; no post-submission model
  turn is required for final presentation.

## Unresolved Decisions and Blockers

- [x] DQ-05 **Resolved September 3, 2026.** Version 1 uses the agent-runtime-owned
  `JsonCompletionStore` adapter at a host-supplied root. One JSON artifact per
  opaque run ID contains both the immutable record and `completed` state, published
  with an atomic no-overwrite link. A fresh composition reopens the same root;
  `root/.presented/<run_id>.json` is the durable exactly-once presentation
  acknowledgement key.
- [x] DQ-06 **Resolved September 3, 2026.** `CompletionToolLoopRuntime.start_run()`
  generates `run_<UUID>` and supplies it only through
  `ToolExecutionContext.opaque_values["agent_runtime.run_id"]`. Accepted terminal
  completion will emit the application-owned `CompletionCommitted(record)` effect
  to the host; it will not use generic terminal hooks. Required-completion
  configuration will be a `ToolLoopLimits` option and the one-time reminder will
  be carried by an application-owned model-turn instruction DTO. SAE-01 through
  SAE-04 implement those model-facing and loop behaviors.

## SAE-00 Implementation Notes

- Completion contracts now include immutable `CompletionRecord`, typed commit
  results, `CompletionGuard`, `CompletionStore`, and `CompletionPresenter` ports.
- `JsonCompletionStore` provides the selected durable/reopenable Version 1 storage
  boundary and durable presenter acknowledgement. The registered tool, state-machine
  integration, model reminder transport, and presenter invocation remain intentionally
  deferred to SAE-01 through SAE-06.

## SAE-01 Implementation Notes

- Added immutable `CompletionSubmission` validation and the canonical
  `SUBMIT_AND_EXIT_TOOL_DEFINITION`. The model-facing schema has exactly the three
  specified fields, rejects additional properties, requires solo batching, and keeps
  outcome and verification independent. Registered-tool mapping remains deferred to
  SAE-03.

## SAE-02 Implementation Notes

- Added application-owned completion run states, an in-memory state-machine
  implementation, and `SubmitRunCompletion`. The use case builds the canonical
  digest-backed record, applies optional guard policy, and only mirrors
  `RUNNING → COMPLETED` after the `CompletionStore` atomically accepts the durable
  record. Guard and pre-commit persistence failures leave the run `RUNNING` so a
  later valid submission can proceed. Registered-tool mapping, full idempotency,
  timeout, and cancellation-race behavior remain deferred to SAE-03 through SAE-05.

## SAE-03 Implementation Notes

- Added the agent-runtime-owned `submit_and_exit` registered-tool adapter. It maps
  the exact model payload plus opaque run ID and tool-call ID to `SubmitRunCompletion`,
  returns structured acceptance content, and maps application errors to stable tool
  rejection codes without adding persistence, retry, verification, or interaction behavior.
- Extended the generic solo-batch rejection to report
  `TERMINAL_TOOL_MIXED_WITH_OTHER_TOOLS` for `submit_and_exit`; validation occurs
  before any tool execution regardless of terminal-call ordering.

## Risks and Implementation Constraints

- Keep completion policy and durable state out of the registered-tool adapter; the
  adapter only maps arguments and context at the boundary.
- Do not allow terminal behavior to depend on tool-call ordering within a batch.
- Never persist a completion record without a `COMPLETED` state, or mark a run
  complete without its record.
- Never render executor acknowledgement prose as a second final answer.
- Do not use the current generic terminal hooks as the sole completion presenter:
  they run for every loop exit, including failed and cancelled runs.
- Do not claim crash/restart recovery from an in-process fake; prove it by reopening
  the selected durable adapter in SAE-06.2.
- Preserve the September 3, 2026 Version 1 specification decisions unless the
  specification is updated and reconfirmed.

## Traceability

| Specification concern | Plan coverage |
| --- | --- |
| Completion contracts, durable adapter, recovery, presentation, and runtime result shape | SAE-00, DQ-05–DQ-06 |
| Canonical schema, enums, and summary bounds | SAE-01 |
| Atomic completion record and state transition | SAE-02, SAE-05.3–SAE-05.4, SAE-06.2 |
| Solo terminal batching | SAE-03.2 |
| Required-completion reminder lifecycle | SAE-04 |
| Guards, idempotency, timeout, and cancellation | SAE-05 |
| Final summary rendering and no extra model turn | SAE-06.1–SAE-06.2 |
| `ask_question` coexistence and headless limits | SAE-06.3 |
