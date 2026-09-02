# Implementation Plan: `ask_question` Tool

- Readiness: **Ready for implementation — AQ-00 architecture decisions confirmed on September 2, 2026.**
- Created: September 2, 2026.
- Source specification: `docs/specs/tools-ask-question-tool-spec.md`.
- Scope: Version 1 live-session human-input interaction only.

## Architecture Decision

`ask_question` gets its own vertical slice: `user_interaction`.

**Selected boundary:** generic model-tool contracts move to a neutral application
package outside `fabrica.features` (and outside `shared_kernel`, which remains
pure-domain-only). Both `agent_runtime` and `user_interaction` depend on that
neutral package; neither feature depends on the other. The neutral package owns
the generic registered-tool protocol, tool definition metadata, execution context,
and lifecycle-hook contracts. It must not own interaction policy, host transport,
or feature-specific behavior.

```text
neutral tool application boundary
├── registered-tool protocol and typed outcome contracts
├── ToolDefinition and ToolBatchPolicy
├── ToolExecutionContext with opaque host-owned context values
└── generic run-terminal lifecycle-hook contract

user_interaction
├── application/
│   ├── dtos/               # question, answer, result, states, stable errors
│   ├── ports/              # interaction transport and published inbound API
│   └── use_cases/          # pending interaction lifecycle and answer resolution
└── adapters/
    ├── inbound/registered_tool/  # ask_question adapter using neutral contracts
    └── outbound/                 # concrete host transports, when introduced

agent_runtime
└── application/use_cases/run_tool_loop.py
    # applies generic batch policy and propagates generic execution context

bootstrap interactive runtime wrapper
    # creates one opaque interaction owner per run, injects it into context,
    # and invokes terminal lifecycle hooks
```

The `user_interaction` slice owns question IDs, one-pending-question policy,
publication, response validation, idempotency, cancellation resolution, and
structured results. `agent_runtime` must not import its private use cases or
adapters. `agent_runtime` remains interaction-agnostic: it validates only the
generic `ToolBatchPolicy` and invokes generic lifecycle hooks. Bootstrap composes
the interaction manager with those hooks; it is the only layer that depends on
both features.

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

- [x] AQ-00 Resolve the orchestration boundary, interaction ownership context, and solo-call mechanism.
- [x] AQ-01 Create the `user_interaction` application contracts and schema DTOs.
- [x] AQ-02 Implement the in-memory interaction manager and transport port.
- [x] AQ-03 Expose `ask_question` through a `user_interaction` registered-tool adapter.
- [ ] AQ-04 Integrate solo-call validation and lifecycle coordination in `agent_runtime`. *(In progress: solo batch validation, opaque context propagation, and external-cancellation mapping are implemented; generic terminal hooks remain deferred.)*
- [ ] AQ-05 Add explicit interactive composition and host response entry points. *(In progress: opt-in composition and per-run host API implemented; acceptance coverage pending.)*
- [ ] AQ-06 Add unit and integration acceptance coverage.
- [ ] AQ-07 Update documentation and run the full quality gate.

Keep these checkboxes and detailed task status current during implementation.
Mark a task complete only after its acceptance criteria and verification pass.

## Dependency Order

```text
AQ-00 boundary and context decision
  -> AQ-01 application contracts
    -> AQ-02 interaction lifecycle
      -> AQ-03 registered tool
        -> AQ-04 runtime integration
          -> AQ-05 composition API
            -> AQ-06 acceptance coverage
              -> AQ-07 documentation and validation
```

## Ordered Tasks

### AQ-00 — Resolve orchestration boundary, interaction ownership context, and solo-call mechanism

**Likely files**

- `docs/plans/ask-question-tool-plan.md`
- The final selected source and test targets from AQ-01 through AQ-06.

**Decision recorded — confirmed September 2, 2026**

Create a neutral application package for generic model-tool contracts. It is not
a feature slice, bootstrap module, compatibility shim, or shared-kernel package.
`agent_runtime` and `user_interaction` may both import its public contracts, but
must not import each other. The composition root alone depends on both features.

**Work**

1. Move generic registered-tool protocol and typed outcome contracts from
   `agent_runtime` into the neutral package. Update all existing registered-tool
   adapters and runtime consumers as a focused boundary migration, without
   compatibility re-exports.
2. Move generic `ToolDefinition` and execution-context contracts into the same
   package. Add `ToolBatchPolicy` with `ALLOW_MIXED` as the default for existing
   tools and `REQUIRE_SOLO` for `ask_question`.
3. Make `_validate_tool_call_batch` reject a batch containing a
   `REQUIRE_SOLO` tool alongside any other call before handlers run. The generic
   runtime reports the stable `ASK_QUESTION_MUST_BE_SOLO` rejection for the
   `ask_question` policy violation; ordinary multi-tool batches remain unchanged.
4. Define an opaque interaction owner value in `user_interaction`. The explicit
   bootstrap interactive runtime wrapper creates a fresh owner for every `.run()`,
   injects it into neutral `ToolExecutionContext`, and never exposes it in
   model-facing arguments or tool results.
5. Define generic terminal lifecycle hooks in the neutral package. Bootstrap
   wires them to `user_interaction` so normal terminal completion releases owner
   records, and structured host answer/cancellation requests authenticate the
   same owner without disclosing whether an unknown ID belongs to another run.
6. Map host/session termination and external runtime cancellation to a structured
   `cancelled` interaction result, allowing the next model turn. On Python task
   cancellation, resolve and clean up the pending interaction, then re-raise
   `CancelledError`; do not attempt another model turn. Human waiting receives no
   ordinary tool deadline in either path.
7. Update the architecture diagram and downstream task targets to match this
   design before beginning AQ-01.

**Acceptance criteria**

- [x] No planned feature-to-feature import cycle remains, and no feature imports
      bootstrap or another feature's private modules.
- [x] The one-pending-per-run, wrong-owner non-disclosure, duplicate replay, and
      cleanup behavior have a concrete context propagation path.
- [x] Mixed tool batches containing `ask_question` can be rejected before any
      handler runs without changing ordinary multi-tool batch behavior.
- [x] The selected ownership and cancellation mapping are specific enough to
      implement and test without further architectural decisions.

**Verification**

- [x] Review the selected imports against `pyproject.toml` import-linter
      contracts. Run `uv run lint-imports` after the first boundary skeleton
      exists.
- [x] Record focused architecture/boundary test targets for the selected design
      before beginning lifecycle implementation.

### AQ-01 — Create `user_interaction` application contracts and schema DTOs

**Likely files**

- `src/fabrica/features/user_interaction/application/dtos/interactions.py`
- `src/fabrica/features/user_interaction/application/dtos/__init__.py`
- `src/fabrica/features/user_interaction/application/ports/__init__.py`
- `tests/unit/features/user_interaction/application/test_interaction_dtos.py`

**Work**

1. Create the dedicated slice and application packages.
2. Define immutable DTOs for question input, publication event, answer submission,
   interaction result, interaction state, opaque interaction owner/run context,
   and stable interaction errors. The owner is created only by the interactive
   bootstrap wrapper and is carried through neutral execution context.
3. Enforce Version 1 input limits: non-whitespace question of 1–4,000 characters;
   exactly 2–5 exact-unique, non-whitespace options of 1–500 characters.
4. Enforce result invariants: `answered` has a non-empty answer and optional valid
   exact-option index; `cancelled` has null answer and selected option.
5. Generate/validate opaque `q_`-prefixed question IDs with a 120-character limit.
6. Keep interaction owner identity out of the model-facing schema and tool result;
   it is host/application context used only for ownership validation.

**Acceptance criteria**

- [x] Invalid question, option-count, whitespace, duplicate-option, and invalid
      result combinations cannot be constructed.
- [x] Interaction-owner values cannot be confused with question IDs, injected by
      model-facing arguments, or created by a host answer/cancellation request.
- [x] Stable codes include `INVALID_INPUT`, `QUESTION_ALREADY_PENDING`,
      `INTERACTION_PUBLISH_FAILED`, `SESSION_NOT_INTERACTIVE`,
      `INTERACTION_NOT_FOUND`, and `INTERNAL_INTERACTION_ERROR`.

**Verification**

- [x] `uv run pytest tests/unit/features/user_interaction/application/test_interaction_dtos.py`

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
   submitting answers, replaying committed results, cancelling a run/session, and
   releasing terminal owner records according to AQ-00.
3. Implement a lock/future-backed in-memory manager with atomic first-resolution-
   wins transitions: `PENDING → ANSWERED` or `PENDING → CANCELLED`.
4. Retain terminal results long enough to acknowledge duplicate/late submissions;
   return non-disclosing `INTERACTION_NOT_FOUND` for unknown or wrong-owner IDs.
5. Keep empty answers pending, prohibit ordinary human-wait timeouts, and remove a
   pending record after definitive publication failure.
6. Validate answer and cancellation ownership through the opaque owner context;
   return non-disclosing `INTERACTION_NOT_FOUND` for unknown or wrong-owner IDs.

**Acceptance criteria**

- [x] Only one question can be pending for a run.
- [x] Duplicate answer submissions return the first committed result without a
      second publication or model-context event.
- [x] Cancellation settles every waiter without leaking a task or resolver.
- [ ] External cancellation, host/session termination, and task cancellation use
      the AQ-00 terminal-result mapping and do not leave pending records.
- [x] No persistence or restart recovery is introduced.

**Verification**

- [x] Focused tests cover answer/cancellation races, publication failure, empty
      answers, duplicate replay, and unknown-ID protection.

### Checkpoint A — Slice boundary

- [x] `user_interaction` application code has no framework, terminal, WebSocket,
      HTTP, or UI imports.
- [ ] Its public application exports are sufficient for the interactive bootstrap
      wrapper according to AQ-00. `agent_runtime` uses only neutral contracts;
      neither feature imports the other's private modules or forms a dependency
      cycle.
- [x] `uv run lint-imports`

### AQ-03 — Add the `ask_question` registered-tool adapter

**Likely files**

- `src/fabrica/features/user_interaction/adapters/inbound/registered_tool/adapter.py`
- `src/fabrica/features/user_interaction/adapters/inbound/registered_tool/__init__.py`
- `tests/unit/features/user_interaction/adapters/inbound/registered_tool/test_adapter.py`

**Work**

1. Create a neutral-contract `AsyncRegisteredTool` named exactly `ask_question`,
   with `ToolBatchPolicy.REQUIRE_SOLO`.
2. Expose the specified JSON schema and concise model-facing guidance.
3. Map model arguments to the slice DTOs and map manager outcomes to structured
   registered-tool outcomes.
4. Preserve the authoritative free-text answer, `question_id`, status, and
   optional `selected_option` exactly once.
5. Fail closed with `SESSION_NOT_INTERACTIVE`; never infer an answer or choose
   option zero.
6. Pass the AQ-00 interaction owner from execution context to the published
   interaction boundary; do not accept it through model arguments.

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

1. Consume neutral tool contracts after their AQ-00 migration; do not add an
   `agent_runtime → user_interaction` dependency.
2. Add generic batch validation that rejects a `REQUIRE_SOLO` tool with any other
   call before any handler runs. For `ask_question`, report
   `ASK_QUESTION_MUST_BE_SOLO`; preserve ordinary multi-tool behavior for
   `ALLOW_MIXED` tools.
3. Propagate opaque execution-context values unchanged through `RunToolLoop` and
   `ToolExecutor`, without exposing the interaction owner to model-facing command
   or tool arguments.
4. Invoke neutral terminal lifecycle hooks on normal completion, external runtime
   cancellation, host/session termination, and Python task cancellation. The
   hooks are composed by bootstrap, not interpreted as interaction behavior by
   `agent_runtime`.
5. Preserve generic tool call-ID replay and tool-loop behavior. Do not apply
   ordinary tool deadlines to the human-wait phase.

**Acceptance criteria**

- [ ] A mixed batch invokes zero tool handlers.
- [ ] A solo question is a synchronization barrier and resumes with one result;
      external cancellation yields structured `cancelled` before the next turn.
- [ ] Ordinary multi-tool batches remain valid when they do not contain a
      solo-classified tool.
- [ ] Python task cancellation while waiting invokes cleanup and re-raises
      `CancelledError`, leaving no pending owner record or resolver.
- [ ] Existing registered tools and loop replay behavior retain their coverage.

**Verification**

- [ ] Async unit tests prove mixed-batch rejection, waiting/resume, and waiting
      cancellation without relying on wall-clock sleeps.

### AQ-05 — Add explicit interactive composition and host API

**Likely files**

- `src/fabrica/bootstrap/composition/user_interaction.py`
- `src/fabrica/bootstrap/composition/tool_loop.py`
- `src/fabrica/bootstrap/__init__.py`
- `tests/unit/test_bootstrap_api.py`
- `tests/integration/features/user_interaction/test_ask_question_composition.py`

**Work**

1. Add an opt-in interactive runtime factory that receives the host transport,
   exposes the `ask_question` registered tool, and returns an interactive wrapper
   that creates one opaque interaction owner per `.run()`.
2. Keep existing offline/headless factories unchanged and without the interactive
   tool by default.
3. Wire the neutral terminal lifecycle hooks to the `user_interaction` manager so
   normal completion releases records, host/session or external cancellation
   resolves `cancelled`, and task cancellation cleans up before it propagates.
4. Expose host methods for structured answer submission and run/session
   cancellation through the `user_interaction` published API; they authenticate
   the owner and return non-disclosing not-found results for wrong owners.
5. Keep composition construction side-effect free.
6. Update the curated bootstrap export contract when the interactive composition
   factory or its host-facing composition object is intentionally public.

**Acceptance criteria**

- [ ] An interactive host receives structured question publication and can answer
      by ID and matching opaque owner context.
- [ ] Headless runtime construction cannot silently make `ask_question` usable.
- [ ] The composition root depends on both slices; neither feature imports
      bootstrap or the other's private modules, and the selected import graph
      passes import-linter validation.
- [ ] The curated bootstrap API test names the intended public interactive
      composition surface; generic headless factories still expose no implicit
      `ask_question` tool.

**Verification**

- [ ] A synthetic-model integration test publishes a question, submits an answer,
      and verifies the next model turn receives the structured tool result.

### AQ-06 — Complete acceptance coverage

**Likely files**

- Unit tests under `tests/unit/features/user_interaction/` and
  `tests/unit/features/agent_runtime/`.
- Integration tests under `tests/integration/features/user_interaction/`.

**Work and acceptance criteria**

- [ ] Cover neutral-contract migration, `ToolBatchPolicy` defaults and solo
      rejection, schema boundaries, free text, exact selected options, ID linkage,
      one pending interaction, duplicate replay, cancellation races, publication
      idempotency/failure, headless failure, owner-context propagation, wrong-owner
      non-disclosure, terminal cleanup, structured external cancellation, and
      task-cancellation cleanup with re-raised `CancelledError`.
- [ ] Use fakes/events; do not require a live terminal, UI, network, or service.
- [ ] Preserve the repository coverage threshold.

**Verification**

- [ ] `uv run pytest tests/unit/features/user_interaction tests/unit/features/agent_runtime`
- [ ] `uv run pytest tests/integration/features/user_interaction`
- [ ] `uv run lint-imports`

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
- [ ] `uv run lint-imports`
- [ ] `uv run pytest`

## Risks and Constraints

- The neutral generic-contract package is an architectural migration across
  registered-tool consumers. Keep its public API narrowly tool-loop-focused; do
  not move interaction policy, host transport, or UI concerns into it.
- The interactive bootstrap wrapper, not `agent_runtime`, creates interaction
  owners and wires interaction-specific terminal handling. Owner identity must
  never reach model-facing arguments or tool results.
- `ToolBatchPolicy` must default to `ALLOW_MIXED` so adding the generic policy
  does not change existing ordinary multi-tool batches.
- The human wait must be cancellation-driven, not generic-timeout-driven.
- Concrete CLI, VS Code, web, and remote transports are follow-on adapter work.
- Do not add persistence, expiry, skip, attachments, multi-select, or
  `submit_and_exit` coupling without a new accepted specification decision.
