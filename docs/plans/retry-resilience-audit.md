# Retry and resilience audit

Status: partially implemented for Codex HTTP transport retries; remaining
findings are still audit notes.

## Context

This note captures a focused audit of retry, timeout, and resilience behavior in
the current Fabrica runtime. It is intentionally stored under `docs/plans/` as a
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

The current implementation has good baseline failure normalization and bounded
timeouts, but it is not yet robust against common transient and partial-failure
scenarios.

Key points:

- Codex HTTP calls now use adapter-owned retry policies with backoff, jitter,
  bounded `Retry-After`, elapsed retry budgets, and secret-safe retry diagnostics.
  Usage `GET` requests use the shared retry defaults. Completion `POST` requests
  intentionally retry only HTTP 429 by default because replay safety for other
  outcomes is not yet proven.
- Automatic retries are not universally safe. Mutating or potentially
  side-effecting operations such as `git commit`, `pre-commit`, and skill-script
  execution should not be retried without explicit idempotency guarantees.
- Agent/tool orchestration is bounded by iteration count and output size, but it
  lacks stronger controls such as per-turn tool-call limits, duplicate tool-call
  suppression, an overall deadline, and cancellation-safe blocking behavior.
- Subprocess timeouts rely on `subprocess.run(..., timeout=...)`; this kills the
  direct child process but may leave descendants running.

## Findings

### Implemented: Codex HTTP transport retry policy

Affected code:

- `src/fabrica/features/codex_transport/adapters/outbound/codex_backend_http/adapter.py`
  - `CodexBackendHttpAdapter.complete()`
  - `CodexBackendHttpAdapter.fetch_usage()`
  - `_post()`
  - `_get()`
- `src/fabrica/features/codex_transport/adapters/outbound/codex_backend_http/response_mapping.py`

Current behavior:

- `fetch_usage()` retries configured retryable HTTPX transport failures and
  retryable statuses with bounded backoff, jitter, `Retry-After`, and elapsed
  budget handling.
- `complete()` uses a cautious default retry policy: HTTP 429 can be retried, but
  transport exceptions and backend 5xx responses are not replayed by default.
- `httpx.HTTPError` is mapped to `TRANSPORT_ERROR`.
- HTTP 429 and rate-limit-like headers are normalized as `RATE_LIMITED`.
- Authentication, quota, backend-shape, and transport errors are kept
  secret-safe.
- Retry observations record `attempt_count`, `retry_count`, `last_retry_reason`,
  `last_http_status`, `last_error_type`, `elapsed_seconds`, and
  `budget_exhausted` without including credentials, raw headers, request bodies,
  or response bodies.

Remaining risk:

- Completion `POST` replay safety is still not proven for transport failures,
  backend 5xx responses, or ambiguous partial stream outcomes. Keep those
  single-attempt unless an idempotency or pre-acceptance guarantee is established.

Implemented direction:

- Add an adapter-owned retry policy DTO/settings object in the Codex HTTP adapter
  package, not in the application core unless retry configuration becomes a
  stable application boundary.
- Retry only clearly retryable outcomes:
  - usage `GET`: retry transport errors, 408, 429, and bounded 5xx responses;
  - completion `POST`: retry 429 and pre-response transport failures only when
    replay is considered safe enough for the observed backend contract;
  - do not retry authentication failure, quota exhaustion, backend shape
    mismatch, edge challenge, 4xx other than 408/429, or ambiguous partial
    stream completion.
- Honor `Retry-After` when safe and bounded.
- Use exponential backoff with jitter, maximum attempts, and maximum elapsed
  budget.
- Add secret-safe observations such as `attempt_count`, `retry_count`,
  `retry_reason`, `last_http_status`, and `elapsed_seconds`.

Regression tests added:

- `fetch_usage()` retries a transient `httpx.ConnectError` and then succeeds.
- `fetch_usage()` honors a bounded `Retry-After` on 429.
- `complete()` does not retry authentication, quota, backend-shape mismatch, or
  non-retryable 4xx responses.
- Retry observations do not include bearer tokens, account IDs, raw headers,
  request bodies, or response bodies.
- Retry budget exhaustion returns the final normalized failure and records the
  attempt count.

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

### High: subprocess timeout may leave descendant processes running

Affected code:

- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/command_runner.py`
  - `run_git_command()`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/commit.py`
  - `GitCommitSubprocessCreator`
- `src/fabrica/features/developer_workflow/adapters/outbound/git_subprocess/pre_commit.py`
  - `PreCommitSubprocessRunner`
- `src/fabrica/features/agent_runtime/adapters/outbound/skill_script_subprocess/adapter.py`
  - `SkillScriptSubprocessExecutor.execute()`

Current behavior:

- Subprocess calls use explicit argv, `shell=False`, captured output, and
  configured timeouts.
- On timeout, Python's `subprocess.run()` kills and waits for the direct child.

Risk:

- Descendant processes from `uv`, `pre-commit`, git hooks, or skill scripts may
  survive after timeout and continue mutating files or consuming resources.
- The actual elapsed time can exceed the configured timeout while waiting for
  subprocess cleanup.

Recommended direction:

- Do not add automatic retries for these operations.
- Consider a process-group/session based runner for subprocess adapters that can
  terminate descendant processes on timeout.
- Preserve current explicit-argv and `shell=False` safety properties.
- Add tests with an injected runner where possible; avoid tests that rely on
  fragile real descendant-process behavior in the default suite.

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

## Recommended first implementation tranche

If implementation proceeds, the narrowest high-value change is Codex HTTP retry
hardening only:

1. Add Codex HTTP adapter-owned retry settings with conservative defaults.
2. Implement retry classification for usage `GET` and cautious completion `POST`.
3. Honor bounded `Retry-After`, exponential backoff, jitter, max attempts, and
   max elapsed time.
4. Add deterministic tests using `httpx.MockTransport` and injected sleep/random
   functions so default tests remain offline and fast.
5. Add observations for attempt/retry counts and final retry reason while keeping
   all diagnostics secret-safe.

Follow-up tranches can separately address:

- tool-loop per-turn bounds and duplicate-call detection;
- runtime deadline and cancellation semantics;
- process-group termination for subprocess timeouts.

## Open decisions

- Should completion `POST` retry on pre-response transport errors, or should it
  retry only 429/rate-limit responses until the backend idempotency contract is
  better understood?
- What are the default retry values for attempts, total elapsed budget, initial
  delay, max delay, and jitter?
- Should retry settings remain purely adapter-owned, or become part of a runtime
  configuration surface documented in README/settings docs?
- Should robust subprocess timeout cleanup be prioritized before broader runtime
  work because it can leave file-mutating descendants alive?
