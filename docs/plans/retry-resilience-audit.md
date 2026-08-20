# Retry and resilience audit

Status: open findings only.

## Context

This note captures remaining retry, timeout, and resilience findings in the
current Fabrica runtime. It is intentionally stored under `docs/plans/` as a
temporary planning artifact until the findings are either implemented, promoted
into specs/ADRs, or closed as intentional trade-offs.

Open areas reviewed:

- Agent runtime async model execution under `src/fabrica/features/agent_runtime/`.
- Current specs in `docs/specs/`, especially `codex-transport.md`,
  `agent-runtime.md`, and tool contract specs.

## Summary verdict

The remaining audit findings focus on runtime cancellation.

Key points:

- Completion `POST` retry safety for transport failures, backend 5xx responses,
  and ambiguous partial stream outcomes is still unproven; keep those outcomes
  single-attempt unless an idempotency or pre-acceptance guarantee is established.
- Agent/model orchestration lacks an overall deadline and cancellation-safe
  blocking behavior.

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

## Follow-up tranches

Remaining implementation work can address:

- runtime deadline and cancellation semantics.

## Open decisions

- Should completion `POST` retry on pre-response transport errors, or should it
  retry only 429/rate-limit responses until the backend idempotency contract is
  better understood?
