# Retry and resilience audit

Status: open findings only. Completed Codex HTTP retry and subprocess timeout
cleanup implementation notes have been removed from this temporary audit artifact.

## Context

This note captures remaining retry, timeout, and resilience findings in the
current Fabrica runtime. It is intentionally stored under `docs/plans/` as a
temporary planning artifact until the findings are either implemented, promoted
into specs/ADRs, or closed as intentional trade-offs.

Relevant areas reviewed:

- Codex HTTP transport under `src/fabrica/features/codex_transport/`.
- Agent runtime tool loop under `src/fabrica/features/agent_runtime/`.
- Developer workflow subprocess adapters under
  `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/`.
- Skill-script subprocess execution under
  `src/fabrica/features/agent_runtime/adapters/outbound/skill_script_subprocess/`.
- Current specs in `docs/specs/`, especially `codex-transport.md`,
  `agent-runtime.md`, `commit-workflows.md`, and `git-workflow-tools.md`.

## Summary verdict

Codex HTTP retry hardening and subprocess timeout cleanup are implemented. The
remaining audit findings focus on runtime cancellation, tool-loop guardrails, and
deliberately non-retried mutating developer workflows.

Key points:

- Completion `POST` retry safety for transport failures, backend 5xx responses,
  and ambiguous partial stream outcomes is still unproven; keep those outcomes
  single-attempt unless an idempotency or pre-acceptance guarantee is established.
- Automatic retries are not universally safe. Mutating or potentially
  side-effecting operations such as `git commit`, `pre-commit`, and skill-script
  execution should not be retried without explicit idempotency guarantees.
- Agent/tool orchestration is bounded by iteration count and output size, but it
  lacks stronger controls such as per-turn tool-call limits, duplicate tool-call
  suppression, an overall deadline, and cancellation-safe blocking behavior.
- Subprocess timeouts use a process-group runner so timeout cleanup targets
  descendants before reporting timeout.

## Findings

### High: async cancellation does not stop underlying blocking model work

Affected code:

- `src/fabrica/features/agent_runtime/adapters/outbound/codex_transport_model/adapter.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/pydantic_ai_model/agent_model.py`
- `src/fabrica/features/agent_runtime/application/use_cases/run_local_agent.py`

Current behavior:

- Async model entry points use `asyncio.to_thread(...)` around synchronous model
  execution.

Risk:

- Cancelling the async task does not necessarily stop the underlying thread or
  HTTP operation. Work may continue after the caller believes it has been
  cancelled.

Recommended direction:

- Treat this as a separate runtime hardening task from HTTP retry logic.
- Introduce explicit deadlines or cancellation-aware transport boundaries before
  claiming cancellation robustness.
- Prefer fixing the underlying transport timeout/retry budget first so runaway
  background work is at least bounded.

### Medium: tool loop lacks per-turn and duplicate-call controls

Affected code:

- `src/fabrica/features/agent_runtime/application/dtos/tools.py`
  - `ToolLoopLimits`
  - `ToolAwareModelResponse`
- `src/fabrica/features/agent_runtime/application/use_cases/run_tool_loop.py`
  - `RunToolLoop.run()`

Current behavior:

- The loop limits iterations and tool result size.
- It executes all tool calls returned by a model turn.

Risk:

- A single model turn can request an unexpectedly large number of tool calls.
- Duplicate tool-call IDs or repeated identical tool calls are not rejected or
  deduplicated.
- Partial batch semantics are implicit: tools run in sequence until results are
  collected, and the first non-success result stops the loop afterward.

Recommended direction:

- Add a `max_tool_calls_per_turn` bound to `ToolLoopLimits`.
- Reject duplicate `call_id` values in a single turn and across the run.
- Record a clear observation when the loop stops due to too many or duplicate
  tool calls.
- Keep retry policy out of this layer until transport/tool adapters expose
  explicit transient/permanent classifications.

### Medium: mutating developer workflows intentionally should not retry

Affected code/specs:

- `docs/specs/commit-workflows.md`
- `src/fabrica/features/developer_workflow/application/use_cases/commit_workflow.py`
- git commit and pre-commit subprocess adapters.

Current behavior:

- Pre-commit failures, modifications, timeouts, and startup failures stop the
  workflow before commit creation.
- Commit creation is attempted only after explicit approval.

Risk:

- Retrying `git commit`, hooks, or pre-commit automatically could duplicate work,
  mask uncertain commit outcomes, or race against repository state changes.

Recommended direction:

- Keep these operations non-retried by default.
- Improve diagnostics around uncertain outcomes instead of retrying.
- If retry is ever introduced, require a narrow idempotency proof and tests for
  repository state before and after failure.

## Follow-up tranches

Remaining implementation work can separately address:

- tool-loop per-turn bounds and duplicate-call detection;
- runtime deadline and cancellation semantics.

## Open decisions

- Should completion `POST` retry on pre-response transport errors, or should it
  retry only 429/rate-limit responses until the backend idempotency contract is
  better understood?
