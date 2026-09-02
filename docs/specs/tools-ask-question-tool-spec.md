# Spec: Ask Question Tool

## Status

- State: Accepted.
- Implementation status: Implemented — Version 1 in-memory interactive composition.
- Accepted by: Maintainer (interactive approval)
- Accepted on: September 2, 2026
- Revision: Version 1 interaction-contract decisions recorded on September 2, 2026.
- Supersedes: Not applicable.

This document is the canonical source of truth for the requirements it defines. Derived plans and implementation must preserve its objective, constraints, execution boundaries, and success criteria; material changes require an updated and re-confirmed specification.

## Objective

Define the model-facing and host-facing specification for the `ask_question`
agent orchestration tool.

`ask_question` is the agent's synchronous human-input primitive. It allows an
agent run to suspend when progress materially depends on information, intent, or
a decision only the user can provide.

Typical uses include:

```text
clarify an ambiguous requirement
choose between materially different implementations
obtain missing configuration or intent
resolve a destructive or irreversible design choice
ask for information unavailable from tools
```

The governing principle is:

```text
ask_question suspends the agent because information is missing; it must never
fabricate that information simply to keep the run moving.
```

## Current Context

- Project: `fabrica`, a Python 3.13 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime-spec.md`.
- Primitive capability specs include `docs/specs/tools-read-files-tool-spec.md`,
  `docs/specs/tools-search-codebase-tool-spec.md`, `docs/specs/tools-run-commands-tool-spec.md`,
  `docs/specs/tools-fetch-web-content-tool-spec.md`, and
  `docs/specs/tools-apply-patch-tool-spec.md`.
- `docs/specs/tools-skills-tool-spec.md` already classifies `ask_question` as an agent
  orchestration primitive alongside `skills` and `submit_and_exit`.
- This spec defines the desired `ask_question` tool contract only. It does not
  implement the tool.

## Assumptions

- The primary caller is a model-driven coding agent operating inside a configured
  workspace and runtime run.
- The runtime can distinguish interactive sessions from headless or unattended
  sessions.
- The host can expose an interaction channel that publishes structured questions
  and later receives user responses.
- Cline compatibility matters for the public tool name, one-question behavior,
  suggested options, blocking interaction, no ordinary human-wait timeout, and
  one-pending-question model.
- Documentation-only changes should be reviewed for clarity and consistency;
  implementation changes will require tests and the project quality gate.

## Architectural classification

`ask_question` belongs to the agent orchestration layer. It is not an external
capability and does not access filesystem, process, network, credential, or other
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

The tool changes run state from `RUNNING` to `WAITING_FOR_USER` and later back to
`RUNNING` when the user answers, or to a terminal state when the run is cancelled
or terminated.

## Scope

### In Scope

- The interactive agent orchestration contract for one pending user question.
- Version 1 live-session publication, waiting, answer resolution, cancellation,
  and duplicate-response replay semantics.

### Out of Scope

- Durable pending-interaction storage, restart recovery, interaction expiry,
  Skip/dismissed results, strict option-only answers, multi-selection, and answer
  attachments.

## Desired Behavior

`ask_question` must allow a model to:

- ask one focused logical question when a material uncertainty cannot be resolved
  from the current conversation, workspace, or available tools;
- provide 2–5 concise, meaningful suggested answer options;
- suspend the current run until a user response, cancellation, or termination is
  received;
- resume with a structured answer result that preserves the user's non-empty
  response text exactly;
- preserve linkage between each question and answer through an explicit
  `question_id`;
- fail safely in non-interactive sessions rather than fabricating an answer.

The preferred decision hierarchy is:

```text
can determine from repository/tools/context?
        ↓ yes
determine it autonomously

        ↓ no

does the answer materially affect the result?
        ↓ yes
ask_question

        ↓ no
make a reasonable assumption and continue
```

The model should ordinarily perform independent investigation before asking.

## Tool interface

Tool name:

```text
ask_question
```

Keep this name. It is clearer than alternatives such as `ask_user`,
`request_input`, `clarify`, or `followup`, and it matches Cline's public
operation.

Canonical Version 1 model-facing JSON schema:

```json
{
  "type": "object",
  "properties": {
    "question": {
      "type": "string",
      "minLength": 1,
      "maxLength": 4000
    },
    "options": {
      "type": "array",
      "minItems": 2,
      "maxItems": 5,
      "uniqueItems": true,
      "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 500
      }
    }
  },
  "required": ["question", "options"],
  "additionalProperties": false
}
```

Example with suggestions:

```json
{
  "question": "Which database should this implementation target?",
  "options": [
    "PostgreSQL",
    "SQLite",
    "MySQL"
  ]
}
```

`question` and every option must contain at least one non-whitespace character.
Option uniqueness is determined from their exact submitted strings. Options are
required in Version 1 to provide a consistently actionable interaction UI, but
they are suggestions rather than an enum: the user may submit arbitrary non-empty
free text.

## Current Cline behavior

Cline currently exposes this input shape:

```json
{
  "question": "Which implementation should I use?",
  "options": [
    "Approach A",
    "Approach B"
  ]
}
```

Its schema requires:

```text
question → non-empty string
options  → 2–5 non-empty strings
```

Cline's tool description says to ask one question, use the tool for clarification
or information needed to complete the task, provide 2–5 selectable options, and
not offer an option to switch into Act mode. Cline treats the tool as
non-retryable.

## Options are suggested answers

Current Cline UI receives `question` plus `options[]`, but the pending
interaction ultimately resolves with an arbitrary answer string, not necessarily
one of the options. The actual interaction model is therefore:

```text
question
+
suggested answer buttons
+
free-text response
```

This is more expressive than strict multiple choice and is required in Version 1.
Options must not be treated as an enum.

For example, the user may answer:

```text
Use PostgreSQL for production, but SQLite is fine for unit tests.
```

even when the suggested options were `PostgreSQL`, `SQLite`, and `MySQL`. The
resulting tool result must preserve the user's answer text.

## One question per invocation

One invocation asks one logical question.

Good:

```text
Which database should this target?
```

Bad:

```text
Which database should this target, what Python version should we support,
and should migrations be automatic?
```

Multiple independent uncertainties should not be bundled merely to save tool
calls. Closely related choices may remain one question when they are one decision
with several alternatives.

## Question quality

Questions should be specific, decision-oriented, self-contained, and brief.

Prefer:

```text
Should the API preserve backward compatibility with the existing v1 payload?
```

over:

```text
What do you want me to do?
```

Options should encode actual choices.

Good:

```json
[
  "Keep the existing public API",
  "Allow a breaking API change",
  "Add a compatibility adapter"
]
```

Bad:

```json
[
  "Yes",
  "No",
  "Maybe"
]
```

when the labels lose meaning outside the rendered UI. Option text becomes part of
the conversation record and should remain understandable independently.

## Model-facing description

Recommended concise description:

```text
Ask the user one focused question when progress depends materially on
information or a decision that cannot be determined from the current
conversation, workspace, or available tools.

Before asking, investigate information that can be determined autonomously.

Provide 2–5 concise suggested answers. Suggestions do not constrain the user's
final answer; the user may respond with non-empty free text.

Do not ask for confirmation of ordinary reversible implementation decisions.
Do not use this tool for tool permission, destructive-action approval, or
Plan → Execute approval.
```

## Result contract

Return structured results rather than magic strings.

Every result contains an opaque `question_id` with the `q_` prefix and at most
120 characters. The runtime generates it before publication and uses it as the
publication idempotency key. Version 1 statuses are exactly `answered` and
`cancelled`.

Answered with free text:

```json
{
  "question_id": "q_01J...",
  "status": "answered",
  "answer": "Use PostgreSQL, but SQLite is fine for unit tests.",
  "selected_option": null
}
```

Answered by selecting a known suggestion, when the host can detect it:

```json
{
  "question_id": "q_01J...",
  "status": "answered",
  "answer": "PostgreSQL",
  "selected_option": 0
}
```

`answer` remains authoritative. Do not return only `selected_option`, because
that forces later context reconstruction against the original question.

Cancellation result:

```json
{
  "question_id": "q_01J...",
  "status": "cancelled",
  "answer": null
}
```

This distinguishes cancellation from a user answer. Do not represent cancellation
as an empty string.

For `answered`, `answer` is a non-empty string and `selected_option` is either
the zero-based index of an exactly selected suggestion or `null`. For
`cancelled`, `answer` and `selected_option` are both `null`. Human non-response
is not an error. Version 1 has no `dismissed`, `expired`, or skipped result.

## Question IDs and linkage

Every question should have an interaction ID:

```json
{
  "question_id": "q_01J...",
  "question": "Which database should this use?",
  "options": [
    "PostgreSQL",
    "SQLite"
  ]
}
```

The eventual response contains the same ID:

```json
{
  "question_id": "q_01J...",
  "status": "answered",
  "answer": "PostgreSQL"
}
```

Do not rely solely on "currently pending question". An ID protects against stale
frontend events, duplicate UI submissions, and cancellation races within the
live host process. Version 1 does not recover pending interactions after a host
or runtime restart.

Answer handling must be atomic and idempotent. The interaction manager must
compare and set a pending interaction to its first terminal resolution:
`PENDING → ANSWERED` for a valid non-empty answer or `PENDING → CANCELLED` for
run/session termination. A later submission for the same `question_id` must
receive an idempotent acknowledgment containing that committed result, regardless
of whether its submitted answer text matches. It must not create another
transcript entry or another model-context message.

## Interaction and run state machines

The runtime run state and the interaction-record state are distinct.

`RunStateMachine` owns the run lifecycle:

```text
RUNNING
   │
   │ ask_question
   ▼
WAITING_FOR_USER
   │
   ├── user answers
   │      ▼
   │    RUNNING
   │
   ├── run cancelled
   │      ▼
   │    CANCELLED
   │
   └── session or host terminated
          ▼
        CANCELLED
```

The interaction manager owns the in-memory interaction lifecycle:

```text
PENDING
   ├── valid non-empty answer → ANSWERED
   └── run/session/host termination → CANCELLED
```

Only the atomic transition from `PENDING` is permitted. `ANSWERED` and
`CANCELLED` retain their committed result long enough to acknowledge duplicate or
late submissions. Version 1 does not persist this record for process recovery.

The UI should expose a pending state such as `turn_phase = awaiting_user` or,
matching Cline terminology more closely, `awaiting_followup`. After the user
answers, the run returns to `RUNNING` and the UI returns to its normal streaming
or executing state.

## Blocking and synchronization

`ask_question` suspends the current agent turn. Conceptually:

```python
answer = await ask_question(...)
```

The model does not continue reasoning with an imaginary answer. No dependent tool
call may execute until the answer arrives.

Unlike independent tools such as `read_files`, `search_codebase`, or
`fetch_web_content`, `ask_question` should not participate in ordinary parallel
tool execution. It forms a synchronization barrier.

`ask_question` must be the sole tool call in its model response. If a response
contains `ask_question` and any other tool call, the runtime tool-call batch
validator must reject the whole batch with `ASK_QUESTION_MUST_BE_SOLO` before any
tool handler executes. `AskQuestionTool` cannot enforce this safely because the
current runtime executes a validated batch before inspecting its results.

## Timeouts and retries

Do not apply normal tool timeouts such as 15, 30, or 60 seconds to the human-wait
phase. Human latency is not tool latency. A pending `ask_question` must remain
unsettled after ordinary elapsed time such as 60 seconds, 5 minutes, 1 hour, or
overnight.

Separate two phases:

```text
A. publish question to frontend
B. wait for user response
```

Phase A may have a normal short operational timeout, for example 5–15 seconds.
Phase B should not. Do not wrap both phases in one `Promise.race(timeout)`.

Recommended retry policy:

```text
retryable = false
maxRetries = 0
```

Repeating the same question because of infrastructure retry is unacceptable UX.
The transport must therefore accept `question_id` as its publication idempotency
key. If publication acknowledgement is ambiguous, the interaction manager retains
the registered pending interaction rather than creating a second question. A
definitive publication failure cancels and removes that interaction before
returning `INTERACTION_PUBLISH_FAILED`.

## Pending-question concurrency

The runtime should permit at most one outstanding `ask_question` interaction per
agent run.

If another question is attempted while one is pending, return a structured error:

```json
{
  "success": false,
  "error": {
    "code": "QUESTION_ALREADY_PENDING"
  }
}
```

Concurrent questions create unnecessary orchestration complexity, including
ambiguous answer routing, partial answers, resumption ordering, and dependent
question ordering. Keep user interaction sequential.

## Interactive-session requirement

If no human interaction channel exists, return `SESSION_NOT_INTERACTIVE`. The
runtime should not expose `ask_question` to an unattended agent unless it has some
asynchronous interaction mechanism.

Examples that may need this tool disabled include cron jobs, headless CI agents,
and non-interactive batch execution.

Do not fake an answer in headless mode. In particular, do not silently resolve to
the first option when no interactive question handler is installed. If the agent
asks `Production or staging?`, automatically choosing `Production` because it is
option zero is dangerous. Return `SESSION_NOT_INTERACTIVE` instead.

## Cancellation and session lifecycle

If the user cancels the run while a question is pending, transition the run from
`WAITING_FOR_USER` to `CANCELLED` and atomically resolve the interaction from
`PENDING` to `CANCELLED`. The waiting operation must settle so the runtime can
unwind and no promise, coroutine, or resolver leaks indefinitely after the owning
run is destroyed.

Cancellation should produce a structured `cancelled` result with `answer: null`,
not an empty string.

Version 1 is live-session only. A frontend may reconnect while the same host
process retains the interaction manager's pending record. A host or runtime
restart terminates the pending interaction; it must not attempt suspended-run
recovery. Duplicate responses, stale answers, session termination, and run
cancellation belong to the session interaction layer. The tool schema should not
be overloaded to encode every session-management concern.

## Empty answers

If free-text answers are supported, empty or whitespace-only submissions should
not resolve the pending question by default. The UI keeps the question pending.

This avoids ambiguous results. Version 1 provides no `Skip` or
"continue without answer" action; only an answer or cancellation can resolve the
interaction.

## UI and transcript representation

The frontend should receive structured data:

```json
{
  "type": "question",
  "question_id": "q_01J...",
  "question": "Which database?",
  "options": [
    "PostgreSQL",
    "SQLite"
  ]
}
```

Do not serialize this internally into JSON inside a generic text field when the
event protocol can represent it structurally.

The frontend may render options as buttons, chips, radio-style suggestions, or
keyboard shortcuts, but the protocol should not dictate presentation widgets. If
free-form responses are supported, the UI must also permit the host's normal
textual input path.

The displayed transcript should logically become:

```text
Assistant:
Which database should this use?

[PostgreSQL] [SQLite] [MySQL]

User:
PostgreSQL
```

The answer should become ordinary user-visible conversational state. The
model-context builder should represent the answer once semantically and avoid
unnecessary duplication as both a tool result and a user message unless the
provider protocol genuinely requires both.

## User-input provenance

The answer enters model context with semantic provenance such as
`user_response_to_question`, not as tool-generated data. This matters for
instruction hierarchy because the content genuinely came from the user.

## Relationship to approval and execution modes

`ask_question` is not tool approval.

`ask_question` asks for task information:

```text
What behavior should this feature have?
```

Permission or approval systems ask for permission for a specific proposed action:

```text
May the agent execute this destructive command?
```

Do not encode approval as:

```json
{
  "question": "Can I delete the database?",
  "options": ["Yes", "No"]
}
```

if the runtime already has a proper permission mechanism.

Likewise, do not hard-code Plan → Execute approval into `ask_question`. A Plan →
Execute product mode may use an explicit phase transition or user UI action.
`ask_question` should remain a general-purpose information primitive.

## Avoid unnecessary confirmation loops

Do not ask `Should I proceed?`, `Is that okay?`, or `Would you like me to
continue?` after every plan step. Agentic coding becomes ineffective if normal
execution requires constant confirmation.

Distinguish information uncertainty from tool permission and ordinary
implementation discretion.

## Error codes

Stable infrastructure and tool error codes should include:

- `INVALID_INPUT`;
- `ASK_QUESTION_MUST_BE_SOLO`;
- `QUESTION_ALREADY_PENDING`;
- `INTERACTION_PUBLISH_FAILED`;
- `SESSION_NOT_INTERACTIVE`;
- `INTERACTION_NOT_FOUND`;
- `INTERNAL_INTERACTION_ERROR`.

`INTERACTION_NOT_FOUND` must cover unknown, wrong-run, and wrong-session IDs
without disclosing whether another session owns the ID. A resolved interaction is
not stale: it returns its committed result idempotently. Human non-response is not
an error.

## Recommended internal architecture

Separate the tool, interaction state, and transport concerns:

```text
AskQuestionTool
      ↓
InteractionManager
      ↓
InteractionTransport
      ↓
UI / CLI / remote client
```

The tool should not know anything about React, VS Code webviews, terminal
prompts, WebSockets, or HTTP polling.

`InteractionManager` responsibilities:

```text
question IDs
single pending interaction
state transitions
answer validation
idempotency
cancellation
atomic first-resolution-wins transition
live-session lifecycle
committed-result replay
```

`InteractionTransport` responsibilities:

```text
display question
display options
receive user input
publish idempotently by question ID
signal live-session disconnect/reconnect
```

Potential transport implementations include `VsCodeInteractionTransport`,
`CliInteractionTransport`, `WebInteractionTransport`, and
`RemoteInteractionTransport`.

Conceptual implementation sketch:

```text
askQuestion(input, runContext):
    validate(input)

    if interactionManager.hasPending(runContext.runId):
        return QUESTION_ALREADY_PENDING

    interaction = createInteraction(input, questionId=generateQuestionId())

    interactionManager.register(interaction)

    try:
        transport.publish(interaction, idempotencyKey=interaction.questionId)

        response = await interaction.wait()

        return response
    finally:
        interactionManager.retainCommittedResultThenClearPending(interaction.id)
```

The human wait itself has no ordinary tool timeout.

## Architecture and project structure

Version 1 implementation ownership:

- Spec and implementation plan: `docs/specs/tools-ask-question-tool-spec.md` and
  `docs/plans/ask-question-tool-plan.md`.
- `user_interaction` owns the interaction DTOs, application ports, in-memory
  interaction manager, and the inbound `ask_question` registered-tool adapter
  under `src/fabrica/features/user_interaction/`.
- `agent_runtime` remains interaction-agnostic. Its tool loop applies generic
  batch policy, propagates opaque host context to the tool executor, and invokes
  terminal lifecycle hooks under `src/fabrica/features/agent_runtime/`.
- `src/fabrica/bootstrap/composition/user_interaction.py` composes both slices,
  creates one opaque owner per interactive run, and exposes structured answer and
  cancellation entry points. It accepts a host-provided `InteractionTransport`;
  Version 1 includes no concrete UI, CLI, web, or remote transport.
- Unit tests live under `tests/unit/features/user_interaction/` and
  `tests/unit/features/agent_runtime/`; composition coverage lives under
  `tests/integration/features/user_interaction/`.

Implementation must preserve hexagonal boundaries: application code may define
ports and DTOs for interaction management, but UI frameworks, WebSockets,
terminal prompts, and process/session details must remain adapter or
composition-root concerns.

## Differences from current Cline behavior

Keep these Cline-compatible concepts:

- `ask_question` name;
- one focused question;
- suggested answer options;
- arbitrary textual response in the actual interaction layer;
- blocking user interaction;
- no normal timeout while waiting for the user;
- no automatic retry;
- explicit `awaiting_followup`-style UI state;
- return to running or streaming after response;
- one pending question model.

Change these behaviors for this implementation:

- do not fake a first-option answer in headless mode;
- do not represent cancellation as an empty answer;
- do not serialize structured questions into opaque JSON text when the host
  protocol can carry structured data;
- do not duplicate answers unnecessarily in both tool result and transcript;
- require 2–5 unique, meaningful suggestions in every Version 1 call while
  preserving non-empty free-text answers;
- reject a mixed tool-call batch before execution instead of attempting deferred
  execution after a question;
- do not couple `ask_question` and `submit_and_exit` without architectural reason.

Add these requirements beyond current Cline behavior:

- explicit question IDs;
- explicit interaction state machine;
- structured answer result;
- selected-option metadata;
- unknown-ID protection without ownership disclosure;
- idempotent answer processing;
- clear cancellation status;
- explicit non-interactive failure;
- interaction transport abstraction;
- synchronization-barrier semantics;
- persisted-suspension option retained as a future architectural choice.

## Testing Strategy

Required future acceptance tests include the following scenarios.

### Schema

- Non-empty question accepted.
- Empty question rejected.
- Too-long question rejected.
- Duplicate options rejected.
- Empty option rejected.
- Too many options rejected.
- Missing `options` rejected.
- Whitespace-only question or option rejected.

### Interaction

- Question published.
- Run enters awaiting-user state.
- User answers.
- Tool resolves.
- Run returns to running state.
- Answer is preserved exactly.
- Question ID linkage is preserved.

### Free text

Free text is required alongside suggestions:

- Click suggested option.
- Type exact suggested option.
- Type different text.
- Unicode answer.
- Multiline answer.

All should yield explicit `answered` state.

### Lifecycle

- Wait longer than 60 seconds without timeout.
- Session cancellation.
- Run cancellation.
- Frontend disconnect.
- Frontend reconnect within the same live host process.
- Duplicate answer.
- Duplicate answer with different text replays the committed result.
- Unknown or wrong-owner question ID returns `INTERACTION_NOT_FOUND` without
  ownership disclosure.
- Session termination.
- Host or runtime restart terminates the in-memory pending interaction and does
  not resume the run.

No pending promise, coroutine, or resolver may leak indefinitely after the owning
run is destroyed.

### Concurrency and synchronization

- One pending question accepted.
- Second ask rejected with `QUESTION_ALREADY_PENDING`.
- A model response containing `ask_question` plus another tool call is rejected
  with `ASK_QUESTION_MUST_BE_SOLO` before any call executes.
- Duplicate frontend response replays the committed result without duplicating
  conversation state.

### Publication

- Publication uses `question_id` as an idempotency key.
- Lost publication acknowledgement does not create a second visible question.
- Definitive publication failure clears the pending interaction and returns
  `INTERACTION_PUBLISH_FAILED`.

### Headless mode

- Interactive transport available works.
- Interactive transport unavailable returns `SESSION_NOT_INTERACTIVE`.
- Runtime never silently selects the first option.

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Format | `uv run ruff format --check .` | Required for implementation changes |
| Lint | `uv run ruff check .` | Required for implementation changes |
| Type check | `uv run ty check src tests` | Required for implementation changes |
| Tests | `uv run pytest` | Required for implementation changes |
| Documentation | Review this specification and its internal references for accuracy and consistency. | Required |
| Migration or compatibility | Not applicable unless this specification explicitly introduces a migration. | Not applicable by default |
| Manual acceptance | Obtain documented human acceptance before implementation planning when the status is Draft. | Required for drafts |

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Future implementation should start with focused schema, interaction-manager,
state-transition, cancellation, idempotency, synchronization, and headless-mode
tests before adding concrete UI, CLI, or remote transports.

## Execution Boundaries

- Always use `ask_question` only when material uncertainty cannot be resolved
  from available conversation, workspace, or tool context.
- Always ask one focused logical question per invocation.
- Always preserve arbitrary user answer text in structured results when an answer
  is received.
- Always use explicit `question_id` linkage between question publication and
  answer handling.
- Always require 2–5 unique, meaningful suggestions while allowing arbitrary
  non-empty free-text answers.
- Always treat `ask_question` as a blocking synchronization barrier and as the
  sole tool call in its model response.
- Always keep the human-wait phase free from ordinary tool timeouts.
- Always fail safely with `SESSION_NOT_INTERACTIVE` when no interaction channel
  exists.
- Always keep permission approval and Plan → Execute mode transitions separate
  from `ask_question`.
- Ask before adding persisted suspension or restart recovery, expiry, skip
  behavior, strict option-only choice, multiple selection, or answer attachments.
- Never fabricate an answer, select the first option automatically, or continue
  with an imaginary response.
- Never auto-retry the same question as ordinary infrastructure retry.
- Never allow more than one pending question per run.
- Never represent cancellation as an empty user answer.
- Never duplicate the same answer unnecessarily in model context.

## Success Criteria

- The spec defines `ask_question` as a synchronous human-input orchestration
  primitive for material user-only information.
- The public name remains `ask_question`.
- The Version 1 input schema requires a bounded non-empty `question` and bounded
  2–5 unique non-empty `options`.
- One focused question, question quality, and suggested-answer semantics are
  specified.
- The result contract is structured and includes `question_id`, status, answer,
  and selected-option metadata.
- Separate run and interaction state machines, standalone-call batch rejection,
  no-human-wait timeout, no-retry, one-pending-question, and synchronization
  semantics are specified.
- Headless mode fails with `SESSION_NOT_INTERACTIVE` and never fabricates a first
  option answer.
- Cancellation, empty answers, idempotent committed-result replay, live-session
  restart termination, transcript representation, answer provenance, and answer
  deduplication are specified.
- The architecture separates `AskQuestionTool`, `InteractionManager`, and
  `InteractionTransport` responsibilities.
- Future acceptance tests are explicit enough to drive implementation.

## Open Questions

| Question | Impact | Blocking? | Owner | Resolution |
| --- | --- | --- | --- | --- |
| Future interaction extensions listed below do not block Version 1 implementation planning. | Future product scope. | No | Maintainer | Deferred |

- How long may a question remain pending: indefinitely, until session close, for a
  fixed duration such as 24 hours, or through configurable expiration?
- Should multiple-selection answers be supported in a future schema?
- Should answers support attachments such as files or images, or remain text-only
  until the general message and input resource model is settled?
- When the agent is waiting on a question and the user sends an ordinary new
  message, should that message answer the pending question, cancel the pending
  question and become a new request, or queue as a subsequent user turn?
- Should `ask_question` be available in runs that also support `submit_and_exit`,
  or should a specific runtime lifecycle mode make them mutually exclusive?
- Should question metadata include a separate `reason`, or should agents express
  the reason in well-phrased question text?
- Should the schema support a `recommended_option`, or should agents express
  recommendations in question text to avoid UI bias?

## Acceptance and Planning Gate

This accepted specification is ready for implementation planning. Future-scope
questions above do not redefine the accepted Version 1 contract unless a
maintainer updates and re-confirms this specification.

## Conventions and Constraints

Follow the project architecture, typing, logging, secret-safety, and validation conventions recorded in `.clinerules/`.

## Project Structure

- Specification: This file under `docs/specs/`.
- Source and test ownership: The detailed architecture section in this specification remains authoritative.
- Documentation ownership: `docs/specs/` and the relevant documentation indexes.
