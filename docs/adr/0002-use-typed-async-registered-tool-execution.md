# 0002. Use Typed Async Registered Tool Execution

Date: 2026-08-23
Status: Accepted

## Context

Fabrica's current model-facing tool runtime grew from deterministic tools that
can be represented as synchronous handlers returning `str`. The v1 `apply_patch`
tool needs stronger runtime semantics: cancellation-aware execution, phase
deadlines, duplicate-delivery protection, recoverable model-facing rejection, and
fatal mutation states that stop the agent loop.

A plain `Callable[..., str]` boundary cannot represent these outcomes safely. It
also cannot guarantee that output bounding preserves mandatory status, mutation
guarantee, error code, and fatal-disposition fields before optional detail.

## Decision

Registered model-facing tools will move to typed async execution contracts.

The runtime-owned execution context will carry narrowly scoped call metadata:
tool call identity, canonical normalized-argument digest, cancellation state, and
phase deadlines. It will not expose arbitrary host services to tool handlers.

Tool handlers will return typed outcomes that distinguish at least:

- successful model-continuing tool completion;
- recoverable rejection that may be shown to the model and continue the loop;
- ordinary tool or adapter failure;
- fatal runtime-stop outcomes for partial, retained, rollback-failed, or
  indeterminate mutation states.

The runtime will keep a per-agent-run ledger keyed by model `call_id` and the
canonical normalized-argument digest. Exact duplicate delivery returns the
recorded terminal result without invoking the handler again. Reusing the same
`call_id` with different normalized arguments fails before handler execution.
Incomplete or indeterminate mutation work is not replayed automatically after
restart; it remains recovery-gated.

Result bounding will be status-prioritized. Stable status, error code, mutation
guarantee, retryability, and fatal disposition must be preserved before optional
preview, excerpt, or evidence detail is truncated.

## Consequences

- Existing deterministic synchronous tools need explicit sync-to-async wrappers
  during the runtime migration.
- `apply_patch` can return recoverable no-mutation rejections without converting
  model mistakes into generic tool failures.
- Partial, retained, rollback-failed, and indeterminate mutation outcomes can stop
  the agent loop deterministically instead of being hidden in text output.
- Duplicate model tool delivery becomes safe for completed terminal outcomes, but
  does not attempt unsafe process-restart replay.
- Runtime DTO and port tests must cover outcome invariants, canonical argument
  digests, duplicate handling, and output bounding.

## Alternatives considered

| Option | Reason rejected |
| ------ | --------------- |
| Keep synchronous `Callable[..., str]` handlers and encode status in text | Text cannot reliably drive runtime loop control, duplicate delivery, or fatal mutation handling. |
| Add `apply_patch`-specific runtime hooks only | This would make a generic tool-loop concern depend on one feature. |
| Replay incomplete mutation calls after restart from the runtime ledger | Filesystem mutation recovery must be journal- and evidence-driven in `workspace_editing`. Runtime replay could duplicate or corrupt edits. |
