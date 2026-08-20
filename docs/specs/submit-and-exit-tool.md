# Spec: Submit and Exit Tool

## Objective

Define the model-facing and host-facing specification for the
`submit_and_exit` agent orchestration tool.

`submit_and_exit` is the agent's terminal run-completion primitive. It lets an
agent declare that useful work on the current run is finished, record the final
outcome, provide the final user-facing summary, state verification status, and
terminate the current run after successful submission.

The governing principle is:

```text
submit_and_exit describes why the run is ending and what was achieved; it must
not merely assert verified: yes/no.
```

The intended lifecycle is:

```text
work
  ↓
verify where appropriate
  ↓
submit_and_exit
  ↓
COMPLETED
```

## Current context

- Project: `fabrica`, a Python 3.13 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime.md`.
- Primitive capability specs include `docs/specs/read-files-tool.md`,
  `docs/specs/search-codebase-tool.md`, `docs/specs/run-commands-tool.md`,
  `docs/specs/fetch-web-content-tool.md`, and
  `docs/specs/apply-patch-tool.md`.
- Agent orchestration specs include `docs/specs/skills-tool.md` and
  `docs/specs/ask-question-tool.md`.
- Neighboring specs already classify `submit_and_exit` as an orchestration
  primitive alongside `skills` and `ask_question`.
- This spec defines the desired `submit_and_exit` tool contract only. It does not
  implement the tool.

## Assumptions

- The primary caller is a model-driven coding agent operating inside a configured
  workspace and runtime run.
- Cline compatibility matters for the public tool name, explicit terminal tool
  concept, `lifecycle.completesRun` behavior, required-completion-tool policy when
  enabled, successful-call completion semantics, summary payload, explicit
  verification signal, 15-second submit timeout, no automatic retries, and special
  UI treatment.
- The runtime can distinguish conversational sessions where plain assistant text
  may finish a turn from task-execution sessions that require a terminal
  completion tool.
- The runtime can persist or otherwise durably accept a completion record before
  marking the run complete.
- Documentation-only changes should be reviewed for clarity and consistency;
  implementation changes will require tests and the project quality gate.

## Architectural classification

`submit_and_exit` belongs to the agent orchestration layer. It is not a primitive
capability and must not access filesystem, process, network, credential, or other
external state.

Recommended tool taxonomy:

```text
Primitive capabilities
──────────────────────
read_files
search_codebase
run_commands
fetch_web_content
apply_patch

Agent orchestration
───────────────────
skills
ask_question
submit_and_exit
```

Unlike `ask_question`, `submit_and_exit` is terminal. It transitions a run from
`RUNNING` to `COMPLETED` only after the terminal submission is accepted.

## Desired behavior

`submit_and_exit` must allow a model to:

- finish the current task when all useful work is complete;
- stop cleanly when the task is genuinely blocked and cannot continue without
  external action or information;
- record task completion state independently from verification status;
- provide one concise final user-facing summary;
- terminate the current run only after successful submission;
- preserve structured completion data for runtime, UI, automation, audit, and
  evaluation consumers.

It must not:

```text
perform verification
run tests
modify files
ask the user a question
grant permissions
retry unfinished work
```

Those operations occur before submission through normal tools and runtime
permission flows.

## Tool interface

Tool name:

```text
submit_and_exit
```

Keep this name. It is explicit, Cline-compatible, and makes terminal intent
clearer than names such as `finish`, `done`, `final_answer`, or `complete`.

Canonical provisional model-facing JSON schema:

```json
{
  "type": "object",
  "properties": {
    "outcome": {
      "type": "string",
      "enum": ["completed", "partial", "blocked"]
    },
    "summary": {
      "type": "string",
      "minLength": 1,
      "maxLength": 12000
    },
    "verification": {
      "type": "string",
      "enum": ["verified", "not_verified", "not_applicable"]
    }
  },
  "required": ["outcome", "summary", "verification"],
  "additionalProperties": false
}
```

The exact outcome and verification enums remain provisional. See the open
questions.

## Current Cline behavior

Cline currently accepts:

```json
{
  "summary": "Implemented the requested behavior and verified the failing test.",
  "verified": true
}
```

Its schema requires:

```text
summary  → string, minimum 10 characters
verified → boolean
```

The schema explicitly tells the model not to set `verified=true` unless the
relevant failing tests have actually been run successfully.

Cline declares:

```text
lifecycle.completesRun = true
```

on `submit_and_exit`. When the tool is present, Cline's runtime automatically
configures:

```text
requireCompletionTool = true
```

so ordinary model text does not count as completion. If the model stops without
invoking the terminal tool, the runtime can inject a reminder that the run is not
complete until the terminal completion tool is called and continue the loop.

This strong design should be preserved.

## Replace `verified` with independent fields

The current Boolean conflates several independent concepts:

```text
task complete?
blocked?
verification run?
verification passed?
```

For example, these situations all collapse to `verified=false` except the first:

```text
implementation complete, tests passed
implementation complete, verification unavailable
implementation partially complete, tests fail
cannot implement because required dependency is inaccessible
```

The canonical input separates task outcome from verification status:

```json
{
  "outcome": "completed",
  "summary": "Implemented token refresh handling and added regression coverage.",
  "verification": "verified"
}
```

Documentation-only example:

```json
{
  "outcome": "completed",
  "summary": "Updated the documentation as requested. No executable verification applies.",
  "verification": "not_applicable"
}
```

Blocked example:

```json
{
  "outcome": "blocked",
  "summary": "The implementation could not be completed because the required generated API package is unavailable in this workspace.",
  "verification": "not_verified"
}
```

## Outcome semantics

`outcome` describes task completion state.

### `completed`

The requested task is complete to the best of the agent's knowledge. This does
not imply tests existed or were run.

### `partial`

The agent completed a meaningful subset, but one or more requested parts remain
unfinished.

Example:

```text
Implemented the API changes, but could not update the generated client because
the generator is unavailable.
```

### `blocked`

The agent cannot continue meaningfully without external action or information.

Examples include missing credentials, missing dependencies, unavailable required
services, absent required source files, or unsupported environments. `blocked`
must not be used merely because an implementation is difficult.

## Verification semantics

`verification` describes evidence about correctness independently from task
completion state.

### `verified`

The agent performed appropriate verification and it passed. Examples include
tests passing, a type checker passing, a build passing, or a targeted command
producing expected output.

### `not_verified`

The result has not been successfully verified. This includes tests not being run,
tests failing, the verification environment being unavailable, or verification
being incomplete.

Whether failed verification deserves its own status remains an open question.

### `not_applicable`

No meaningful executable verification applies, such as a pure prose answer,
documentation-only change, analysis task, or configuration explanation without
mutation. This is preferable to falsely calling such work `verified`.

## Completion and verification are independent

Valid combinations include:

| Outcome     | Verification     | Meaning                                      |
| ----------- | ---------------- | -------------------------------------------- |
| `completed` | `verified`       | Done and checked                             |
| `completed` | `not_verified`   | Done, but correctness not confirmed          |
| `completed` | `not_applicable` | Done; executable verification does not apply |
| `partial`   | `not_verified`   | Some work done, task incomplete              |
| `blocked`   | `not_verified`   | Could not finish                             |
| `partial`   | `verified`       | Completed subset was verified                |

Completion does not require `verification="verified"`. A blocked or unverified
terminal submission may still be a successful run-completion event when the agent
has reached a legitimate stopping point.

## Final summary

`summary` is the final user-facing response, not internal reasoning.

It should state what was done, the important result, verification status, and any
remaining limitation when relevant. It should not contain private reasoning, raw
scratchpad, long command logs, every investigated file, or an implementation
diary.

The final summary should usually be one to five short paragraphs.

Example:

```text
Implemented retry handling for expired access tokens and added regression
coverage for both refresh success and refresh failure.

Verification: `uv run pytest tests/test_auth.py -q` passes (18 tests).
```

Do not impose an arbitrary ten-character minimum. A concise valid result such as
`No changes needed.` should be allowed. Meaningful validation should come from
schema, model-facing guidance, and optional host policy rather than an arbitrary
character count.

## Model-facing description

Recommended concise description:

```text
Finish the current task and terminate the agent run.

Call this only after all useful work is complete or when the task cannot proceed
further.

Before submitting, review the original request, ensure all requested changes are
present, and perform appropriate verification where possible. Inspect the
verification results before claiming verification succeeded.

Use outcome to state whether the task was completed, partially completed, or
blocked. Use verification to state whether correctness was actually checked.

The summary is the final user-facing response. Clearly state what was done,
verification performed, and any remaining limitation.

This is a terminal tool. Do not call it together with other tool calls.
```

Before submitting, the model should:

1. Re-read the task requirements.
2. Confirm all requested changes are present.
3. Run appropriate verification when possible.
4. Inspect verification results.
5. Only then call `submit_and_exit`.

## Terminal result and presentation

Recommended successful tool result:

```json
{
  "status": "accepted",
  "outcome": "completed",
  "verification": "verified",
  "summary": "Implemented token refresh handling and verified the regression tests."
}
```

After this result is durably accepted:

```text
run state → COMPLETED
```

Do not return an executor acknowledgement sentence such as:

```text
Submission recorded (verified): <summary>
```

as the semantic final result. Such text is useful as an implementation stub but
is not the final user-facing output.

The clean separation is:

```text
submit input
   ↓
CompletionRecord
   ↓
runtime commits completion
   ↓
presentation layer renders CompletionRecord.summary
```

Final user-facing output must not depend on parsing arbitrary executor prose.
When terminal completion is mandatory, do not require an additional model
generation after `submit_and_exit`. The submitted `summary` is already the final
response:

```text
submit_and_exit
  → tool accepted
  → render summary
  → stop
```

## Completion record

Internally, successful submission should create a completion record:

```text
CompletionRecord
    outcome
    summary
    verification
    submitted_at
    tool_call_id
    run_id
```

Optionally, later versions may include:

```text
verification_evidence
```

depending on the verification-evidence design.

## Run lifecycle

The run has at most one accepted terminal submission.

State transition:

```text
RUNNING
   ↓ successful submit_and_exit
COMPLETED
```

After `COMPLETED`, additional tool calls from the same run are ignored or
rejected.

Completion is irreversible within a run. Do not transition:

```text
COMPLETED → RUNNING
```

for the same run. A subsequent user message starts a new run or continuation
turn within the conversation or session.

This distinction matters:

```text
conversation can continue
current agent run cannot
```

## Successful invocation ends the run

The completion condition is:

```text
terminal tool called
AND
tool execution succeeded
```

Cline searches executed tool results for a successful tool whose
`lifecycle.completesRun == true` and then terminates the run. Preserve the
semantic that a failed `submit_and_exit` call does not complete the run.

## Required completion mode

When `submit_and_exit` is configured for a session, `requireCompletionTool = true`
should normally follow automatically. This matches Cline and prevents the model
from ignoring the terminal protocol and ending with plain text.

If `submit_and_exit` is absent, ordinary conversational agents may use plain
assistant responses to complete a run. This supports both conversational mode and
task-execution mode with explicit terminal state.

## Terminal synchronization barrier

`submit_and_exit` should behave as a terminal synchronization barrier. Once
accepted:

```text
no subsequent work from the same model turn may execute
```

This prevents sequences such as:

```text
submit_and_exit
then
rm / update / test / patch
```

from happening after the agent has declared completion.

Provisional v1 rule:

```text
submit_and_exit must be the sole tool call in its model turn
```

If the model emits `run_commands(...)` and `submit_and_exit(...)` together,
reject the completion call with `TERMINAL_TOOL_MIXED_WITH_OTHER_TOOLS` and let
the next iteration submit after seeing verification results.

This prevents a model from issuing verification and claiming
`verification="verified"` concurrently before it knows whether verification
succeeds.

Whether the sole-call rule is mandatory remains an open question.

## Verification evidence and guards

`verification="verified"` is a model assertion. The model-facing description must
instruct the model to verify before claiming success, but the runtime should not
blindly rely on the assertion where stronger policy is available.

Keep a general `completionGuard` abstraction. A host may register a guard that
returns either:

```text
undefined → submission allowed
```

or:

```text
message → completion blocked, tell model what remains
```

Possible completion guards include unfinished delegated tasks, pending child
agents, uncommitted required artifacts, missing mandatory verification, open
transactions, or required output files being absent.

The terminal tool should not need to know these domain rules itself.

Recommended pipeline:

```text
model calls submit_and_exit
        ↓
validate payload
        ↓
TerminalCallGuard
        ↓
CompletionGuard
        ↓
CompletionPolicy
        ↓
CompletionStore
        ↓
emit final result
        ↓
RUNNING → COMPLETED
```

## Atomicity and persistence

Submission must be atomic. Do not mark the run completed before the completion
record is durably accepted.

Correct ordering:

```text
validate
→ persist completion record
→ emit terminal result
→ mark completed
```

If persistence fails, submission fails and the run remains `RUNNING`.

## Timeout, retries, and idempotency

Recommended default:

```text
SUBMIT_TIMEOUT = 15 seconds
```

Submission should not use automatic retries:

```text
retryable = false
maxRetries = 0
```

Terminal state transition is not the kind of operation that should be replayed
speculatively.

Despite no automatic retries, explicit duplicate delivery can happen. Use
`tool_call_id` as an idempotency key.

If the identical terminal call is delivered again after being accepted, return:

```json
{
  "status": "already_accepted"
}
```

Do not create a second completion record.

## Cancellation race

If cancellation and submission race:

```text
submit begins
user cancels
```

the result must be deterministic. Recommended behavior:

```text
whichever state transition commits first wins
```

Use atomic compare-and-set semantics:

```text
RUNNING → COMPLETED
or
RUNNING → CANCELLED
```

Never both.

## Error codes

Stable infrastructure and tool error codes should include:

- `INVALID_INPUT`;
- `COMPLETION_NOT_ALLOWED`;
- `COMPLETION_GUARD_FAILED`;
- `TERMINAL_TOOL_MIXED_WITH_OTHER_TOOLS`;
- `VERIFICATION_REQUIREMENT_NOT_MET`;
- `RUN_ALREADY_COMPLETED`;
- `SUBMIT_TIMEOUT`;
- `SUBMIT_CANCELLED`;
- `PERSISTENCE_ERROR`;
- `INTERNAL_COMPLETION_ERROR`.

Validation failure, persistence failure, timeout, cancellation before commit, and
guard rejection must leave the run active unless another terminal state wins.

## Relationship to `ask_question`

Conceptually, `ask_question` and `submit_and_exit` are not mutually exclusive.

```text
ask_question
```

means:

```text
I need more information before I can finish.
```

`submit_and_exit` means:

```text
I am finished.
```

Cline currently omits `ask_question` when a `submit_and_exit` executor exists in
some tool-builder paths, and its presets reinforce a mode distinction. This
appears to be a Cline mode or lifecycle choice rather than a fundamental
architectural requirement.

Default recommendation: allow both tools in ordinary interactive task runs.
Headless automation modes may disable `ask_question` by design.

## Relationship to task blocked and runtime failure

Blocked work may terminate cleanly through `submit_and_exit(outcome="blocked")`
when the agent understood the task, worked correctly, and determined it cannot
proceed without external action or information.

This is distinct from agent or runtime failure. Provider crashes, permanent
transport failures, runtime invariant failures, or internal errors should
terminate through an `ERROR` run state, not through `submit_and_exit`.

## Architecture and project structure

Recommended component boundaries:

```text
SubmitAndExitTool
       ↓
SubmitValidator
       ↓
TerminalCallGuard
       ↓
CompletionGuard
       ↓
CompletionPolicy
       ↓
CompletionStore
       ↓
RunStateMachine
       ↓
CompletionPresenter
```

`CompletionGuard` responsibilities:

```text
child agents
team tasks
mandatory checks
required artifacts
host invariants
```

It returns `ALLOW` or `BLOCK(reason)`.

`CompletionStore` responsibilities:

```text
durable completion record
idempotency
tool-call linkage
timestamp
outcome
verification
summary
```

`RunStateMachine` owns:

```text
RUNNING
WAITING_FOR_USER
COMPLETED
CANCELLED
ERROR
```

`submit_and_exit` may transition only:

```text
RUNNING → COMPLETED
```

Potential handling from `WAITING_FOR_USER` should not arise because the agent
itself is suspended there.

Likely future implementation ownership:

- Spec: `docs/specs/submit-and-exit-tool.md`.
- Runtime tool contracts, DTOs, completion records, guard ports, completion
  policy, and orchestration use cases: under
  `src/fabrica/features/agent_runtime/application/`.
- Persistence, UI presentation, CLI rendering, and host-specific completion
  storage: under relevant adapters or composition-root modules.
- Unit tests: under `tests/unit/features/agent_runtime/` for schema validation,
  state transitions, terminal-call guards, completion guards, persistence
  failures, idempotency, cancellation races, and presenter behavior.
- Integration tests: under `tests/integration/features/agent_runtime/` for real
  runtime composition with completion-tool-required sessions and concrete
  presenters or stores.

Implementation must preserve hexagonal boundaries: application code may define
ports and DTOs for completion, but provider schemas, UI frameworks, database
clients, terminal renderers, and process/session details must remain adapter or
composition-root concerns.

## Keep from current Cline behavior

- `submit_and_exit` name.
- Explicit terminal tool.
- `lifecycle.completesRun`.
- Mandatory completion-tool policy when enabled.
- Successful call required to terminate.
- Summary payload.
- Explicit verification signal.
- Ability to terminate even when the task could not be resolved.
- 15-second submit timeout.
- No automatic retries.
- UI treats completion specially.

## Change from current Cline behavior

- Replace ambiguous `verified` Boolean.
- Remove arbitrary summary minimum of 10 characters.
- Do not use `Submission recorded...` executor prose as final output.
- Do not conflate task outcome with verification.
- Do not make `ask_question` mutually exclusive without an explicit mode reason.
- Do not allow terminal semantics to depend on incidental tool execution order.

## Add beyond current Cline behavior

- Structured task outcome.
- Structured verification state.
- Completion record.
- Idempotent terminal call.
- Terminal synchronization barrier.
- Completion persistence.
- Completion guards.
- Explicit blocked and partial outcomes.
- Deterministic cancellation race.
- Final response rendered directly from the completion record.

## Testing strategy

Required future acceptance tests include the following scenarios.

### Basic

- Successful terminal submission.
- Summary preserved.
- Outcome preserved.
- Verification preserved.
- Run becomes completed.
- Final summary rendered.

### Lifecycle

- Plain text does not finish when completion tool is required.
- Successful completion tool finishes.
- Failed completion tool does not finish.
- Duplicate completion is idempotent.
- Tool cannot run after completion.

### Verification

- Verified submission accepted when policy allows it.
- Not-verified submission accepted.
- Not-applicable submission accepted.
- Host verification guard can reject unsupported verified claims.

Exact statuses depend on open questions.

### Guard

- No obligations completes.
- Unfinished obligation rejects completion and keeps the run active.
- Guard message is returned to the model.
- Guard later clears and submission succeeds.

### Terminal batching

If the sole-call rule is adopted:

- `submit_and_exit` alone is allowed.
- `submit_and_exit` plus `read_files` is rejected.
- `submit_and_exit` plus `run_commands` is rejected.
- `submit_and_exit` plus `apply_patch` is rejected.

### Failure

- Validation failure leaves the run active.
- Persistence failure leaves the run active.
- Timeout leaves the run active.
- Cancellation race resolves deterministically.

### Rendering

- Summary is rendered once.
- Executor acknowledgement is not shown as duplicate final answer.
- No additional model turn is required.

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Future implementation should start with focused schema, completion-record,
state-machine, terminal-guard, completion-guard, idempotency, persistence-failure,
cancellation-race, and presentation tests before wiring concrete runtime or UI
adapters.

## Boundaries

- Always use `submit_and_exit` only after all useful work is complete or the task
  cannot proceed meaningfully.
- Always separate task outcome from verification status.
- Always render the final user-facing response from the submitted `summary`.
- Always require successful tool execution before completing the run.
- Always leave the run active when submission validation, guard checks,
  persistence, timeout, or cancellation-before-commit fails.
- Always keep completion persistence atomic with run-state transition.
- Always treat accepted submission as terminal for the current run.
- Ask before enforcing explicit verification evidence references, adding a richer
  outcome enum, adding a richer verification enum, allowing terminal tool calls in
  mixed tool batches, or splitting `summary` into separate machine and user forms.
- Never perform work, verification, tests, permission grants, file mutation,
  retries, or user questions inside `submit_and_exit`.
- Never complete the run from a failed `submit_and_exit` call.
- Never create more than one accepted completion record for a run.
- Never show executor acknowledgement prose as duplicate final output.

## Success criteria

- The spec defines `submit_and_exit` as the terminal run-completion orchestration
  primitive.
- The public name remains `submit_and_exit`.
- The provisional input schema includes independent `outcome`, `verification`,
  and `summary` fields with bounded structured values.
- The spec clearly separates task completion state from verification evidence.
- The spec preserves Cline-compatible lifecycle behavior: `lifecycle.completesRun`,
  required completion tool when enabled, successful call required to terminate,
  ability to terminate unresolved work, 15-second timeout, and no automatic
  retries.
- The spec records intended changes from Cline's Boolean `verified` contract,
  arbitrary summary length minimum, executor acknowledgement prose, and incidental
  terminal ordering.
- The final submitted `summary` is the user-facing final answer and no additional
  model turn is required.
- Atomic persistence, idempotency, terminal synchronization, completion guards,
  cancellation races, and stable error codes are specified.
- Relationship to `ask_question`, conversational sessions, blocked outcomes, and
  runtime failures is explicit.
- Future acceptance tests are explicit enough to drive implementation.

## Open questions

- Should verification evidence remain a model declaration with optional runtime
  policy guards, should the runtime validate recent evidence, or should the schema
  require explicit evidence references such as tool-call IDs?
- Should the outcome enum remain `completed`, `partial`, and `blocked`, or should
  it include another status such as `failed`?
- Should the verification enum remain `verified`, `not_verified`, and
  `not_applicable`, or should it use richer statuses such as `passed`, `failed`,
  `not_run`, and `not_applicable`?
- Should failed verification allow `outcome="completed"`, or should failed
  verification force `outcome="partial"` or another non-completed state?
- Should `submit_and_exit` always be the sole tool call in a model turn, or may
  hosts allow ordered execution where submission runs only after earlier calls
  succeed?
- Should `ask_question` always be available in runs that also support
  `submit_and_exit`, or should particular lifecycle modes make them mutually
  exclusive?
- Should `summary` be the only user-visible final content, or is there a real
  consumer need for separate machine-oriented `summary` and user-facing
  `final_message` fields?
- Should completion input include changed files, or should the runtime derive them
  from patch history, git diff, or workspace transaction logs?
- Should completion input include verification commands, or should the runtime
  derive them from command history and verification-class tool results?
- Should a blocked result always use `submit_and_exit`, or should some blocked
  conditions map to non-completion run states?
