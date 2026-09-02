# Implementation Plan: `ask_question` Tool

- Readiness: **Ready for implementation.**
- Created: September 2, 2026.
- Source specification: `docs/specs/tools-ask-question-tool-spec.md`.
- Scope: Version 1 live-session human-input interaction only.

## Architecture Decision

`ask_question` gets its own vertical slice: `user_interaction`.

```text
user_interaction
├── application/
│   ├── dtos/               # question, answer, result, states, stable errors
│   ├── ports/              # interaction transport and published inbound API
│   └── use_cases/          # pending interaction lifecycle and answer resolution
└── adapters/
    ├── inbound/registered_tool/  # ask_question tool adapter
    └── outbound/                 # concrete host transports, when introduced

agent_runtime
└── application/use_cases/run_tool_loop.py
    # validates that ask_question is solo and coordinates run lifecycle only
```

The `user_interaction` slice owns question IDs, one-pending-question policy,
publication, response validation, idempotency, cancellation resolution, and
structured results. `agent_runtime` must not import its private use cases or
adapters; it may depend only on the slice's published application ports and DTOs.

## Scope and Non-Goals

### In scope

- `ask_question` public name, schema, structured result, and stable error codes.
- One in-memory pending interaction per run.
- Structured host publication, free-text response, selected-option metadata,
  cancellation, and duplicate-result replay.
- Explicit interactive composition; headless composition fails closed.
- Runtime solo-call validation and waiting/resume lifecycle integration.

### Out of scope

- Durable interaction persistence, restart recovery, expiry, skip/dismiss,
  option-only answers, multi-selection, attachments, and concrete UI transports.
- Permission approval, destructive-action approval, Plan → Execute approval, and
  coupling to `submit_and_exit`.

## Progress Tracking

- [ ] AQ-01 Create the `user_interaction` application contracts and schema DTOs.
- [ ] AQ-02 Implement the in-memory interaction manager and transport port.
- [ ] AQ-03 Expose `ask_question` through a `user_interaction` registered-tool adapter.
- [ ] AQ-04 Integrate solo-call validation and lifecycle coordination in `agent_runtime`.
- [ ] AQ-05 Add explicit interactive composition and host response entry points.
- [ ] AQ-06 Add unit and integration acceptance coverage.
- [ ] AQ-07 Update documentation and run the full quality gate.

Keep these checkboxes and detailed task status current during implementation.
Mark a task complete only after its acceptance criteria and verification pass.

## Dependency Order

```text
AQ-01 application contracts
  -> AQ-02 interaction lifecycle
    -> AQ-03 registered tool
      -> AQ-04 runtime integration
        -> AQ-05 composition API
          -> AQ-06 acceptance coverage
            -> AQ-07 documentation and validation
```

## Ordered Tasks

### AQ-01 — Create `user_interaction` application contracts and schema DTOs

**Likely files**

- `src/fabrica/features/user_interaction/application/dtos/interactions.py`
- `src/fabrica/features/user_interaction/application/dtos/__init__.py`
- `src/fabrica/features/user_interaction/application/ports/__init__.py`
- `tests/unit/features/user_interaction/application/test_interaction_dtos.py`

**Work**

1. Create the dedicated slice and application packages.
2. Define immutable DTOs for question input, publication event, answer submission,
   interaction result, interaction state, and stable interaction errors.
3. Enforce Version 1 input limits: non-whitespace question of 1–4,000 characters;
   exactly 2–5 exact-unique, non-whitespace options of 1–500 characters.
4. Enforce result invariants: `answered` has a non-empty answer and optional valid
   exact-option index; `cancelled` has null answer and selected option.
5. Generate/validate opaque `q_`-prefixed question IDs with a 120-character limit.

**Acceptance criteria**

- [ ] Invalid question, option-count, whitespace, duplicate-option, and invalid
      result combinations cannot be constructed.
- [ ] Stable codes include `INVALID_INPUT`, `QUESTION_ALREADY_PENDING`,
      `INTERACTION_PUBLISH_FAILED`, `SESSION_NOT_INTERACTIVE`,
      `INTERACTION_NOT_FOUND`, and `INTERNAL_INTERACTION_ERROR`.

**Verification**

- [ ] `uv run pytest tests/unit/features/user_interaction/application/test_interaction_dtos.py`

### AQ-02 — Implement interaction lifecycle and transport boundary

**Likely files**

- `src/fabrica/features/user_interaction/application/ports/interaction_transport.py`
- `src/fabrica/features/user_interaction/application/ports/interaction_manager.py`
- `src/fabrica/features/user_interaction/application/use_cases/manage_interaction.py`
- `tests/unit/features/user_interaction/application/test_manage_interaction.py`

**Work**

1. Define the application-owned `InteractionTransport` port for structured,
   idempotent publication using `question_id` as the idempotency key.
2. Define the published interaction-manager API for creating/waiting on questions,
   submitting answers, replaying committed results, and cancelling a run/session.
3. Implement a lock/future-backed in-memory manager with atomic first-resolution-
   wins transitions: `PENDING → ANSWERED` or `PENDING → CANCELLED`.
4. Retain terminal results long enough to acknowledge duplicate/late submissions;
   return non-disclosing `INTERACTION_NOT_FOUND` for unknown or wrong-owner IDs.
5. Keep empty answers pending, prohibit ordinary human-wait timeouts, and remove a
   pending record after definitive publication failure.

**Acceptance criteria**

- [ ] Only one question can be pending for a run.
- [ ] Duplicate answer submissions return the first committed result without a
      second publication or model-context event.
- [ ] Cancellation settles every waiter without leaking a task or resolver.
- [ ] No persistence or restart recovery is introduced.

**Verification**

- [ ] Focused tests cover answer/cancellation races, publication failure, empty
      answers, duplicate replay, and unknown-ID protection.

### Checkpoint A — Slice boundary

- [ ] `user_interaction` application code has no framework, terminal, WebSocket,
      HTTP, or UI imports.
- [ ] Its public application exports are sufficient for `agent_runtime` and host
      composition without importing private modules.

### AQ-03 — Add the `ask_question` registered-tool adapter

**Likely files**

- `src/fabrica/features/user_interaction/adapters/inbound/registered_tool/adapter.py`
- `src/fabrica/features/user_interaction/adapters/inbound/registered_tool/__init__.py`
- `tests/unit/features/user_interaction/adapters/inbound/registered_tool/test_adapter.py`

**Work**

1. Create an `AsyncRegisteredTool` named exactly `ask_question`.
2. Expose the specified JSON schema and concise model-facing guidance.
3. Map model arguments to the slice DTOs and map manager outcomes to structured
   registered-tool outcomes.
4. Preserve the authoritative free-text answer, `question_id`, status, and
   optional `selected_option` exactly once.
5. Fail closed with `SESSION_NOT_INTERACTIVE`; never infer an answer or choose
   option zero.

**Acceptance criteria**

- [ ] The model-facing schema and tool name match the accepted specification.
- [ ] Answered, selected-option, free-text, cancellation, and headless outcomes
      are all structured and correct.

**Verification**

- [ ] Focused adapter tests pass without a real UI or external transport.

### AQ-04 — Integrate the `agent_runtime` tool-loop barrier and run lifecycle

**Likely files**

- `src/fabrica/features/agent_runtime/application/use_cases/run_tool_loop.py`
- `src/fabrica/features/agent_runtime/application/dtos/tools.py`
- `tests/unit/features/agent_runtime/application/test_run_tool_loop.py`
- `tests/unit/features/agent_runtime/application/test_tool_dtos.py`

**Work**

1. Add batch validation that rejects `ask_question` with any other call before
   any handler runs, reporting `ASK_QUESTION_MUST_BE_SOLO`.
2. Add only the lifecycle coordination required for observable
   `RUNNING → WAITING_FOR_USER → RUNNING/CANCELLED` state changes.
3. Pass the active run interaction context through the published
   `user_interaction` application boundary.
4. Ensure cancellation resolves a pending interaction and prevents further model
   progress; do not apply ordinary tool deadlines to the human-wait phase.
5. Preserve current generic tool call-ID replay and tool-loop behavior.

**Acceptance criteria**

- [ ] A mixed batch invokes zero tool handlers.
- [ ] A solo question is a synchronization barrier and resumes with one result.
- [ ] Existing registered tools and loop replay behavior retain their coverage.

**Verification**

- [ ] Async unit tests prove mixed-batch rejection, waiting/resume, and waiting
      cancellation without relying on wall-clock sleeps.

### AQ-05 — Add explicit interactive composition and host API

**Likely files**

- `src/fabrica/bootstrap/composition/user_interaction.py`
- `src/fabrica/bootstrap/composition/tool_loop.py`
- `src/fabrica/bootstrap/__init__.py`
- `tests/integration/features/user_interaction/test_ask_question_composition.py`

**Work**

1. Add an opt-in interactive runtime factory that receives the host transport and
   exposes the `ask_question` registered tool.
2. Keep existing offline/headless factories unchanged and without the interactive
   tool by default.
3. Expose host methods for structured answer submission and run/session
   cancellation through the `user_interaction` published application API.
4. Keep composition construction side-effect free.

**Acceptance criteria**

- [ ] An interactive host receives structured question publication and can answer
      by ID.
- [ ] Headless runtime construction cannot silently make `ask_question` usable.
- [ ] The composition root depends on both slices; neither feature imports
      bootstrap or the other's private modules.

**Verification**

- [ ] A synthetic-model integration test publishes a question, submits an answer,
      and verifies the next model turn receives the structured tool result.

### AQ-06 — Complete acceptance coverage

**Likely files**

- Unit tests under `tests/unit/features/user_interaction/` and
  `tests/unit/features/agent_runtime/`.
- Integration tests under `tests/integration/features/user_interaction/`.

**Work and acceptance criteria**

- [ ] Cover schema boundaries, free text, exact selected options, ID linkage,
      one pending interaction, duplicate replay, cancellation races, publication
      idempotency/failure, headless failure, and solo-call rejection.
- [ ] Use fakes/events; do not require a live terminal, UI, network, or service.
- [ ] Preserve the repository coverage threshold.

**Verification**

- [ ] `uv run pytest tests/unit/features/user_interaction tests/unit/features/agent_runtime`
- [ ] `uv run pytest tests/integration/features/user_interaction`

### AQ-07 — Documentation and full quality gate

**Likely files**

- `README.md`
- `docs/README.md` if an index update is required.

**Work**

1. Document opt-in interactive composition, host responsibilities, and the
   Version 1 limits.
2. State clearly that the tool is for material missing information, not approval
   workflows, and that headless runtimes never fabricate answers.
3. Run the configured repository quality gate.

**Acceptance criteria**

- [ ] Public documentation reflects actual final APIs and does not claim a
      concrete UI transport exists.

**Verification**

- [ ] `uv run ruff format .`
- [ ] `uv run ruff check .`
- [ ] `uv run ty check src tests`
- [ ] `uv run pytest`

## Risks and Constraints

- `agent_runtime` currently has no explicit host session/run identity model;
  introduce an opaque interaction context at the composition/application boundary
  rather than adding UI concerns to the model-facing command.
- The human wait must be cancellation-driven, not generic-timeout-driven.
- Concrete CLI, VS Code, web, and remote transports are follow-on adapter work.
- Do not add persistence, expiry, skip, attachments, multi-select, or
  `submit_and_exit` coupling without a new accepted specification decision.
