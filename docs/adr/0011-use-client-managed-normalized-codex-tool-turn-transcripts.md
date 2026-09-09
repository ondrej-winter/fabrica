# 0011. Use Client-Managed Normalized Codex Tool-Turn Transcripts

Date: 2026-09-09
Status: Accepted

## Context

Fabrica's provider-neutral tool loop already owns explicit tool definitions,
validated tool calls, tool results, bounded iteration, cancellation, and terminal
disposition. The implemented Codex transport, however, is a one-shot,
final-result-only completion path. It cannot run the `ToolAwareAgentModel` turn
contract required by the accepted `fabrica agent` coding-session composition.

The private Codex backend may expose response or conversation identifiers, but
making those identifiers required runtime state would couple provider-neutral
application DTOs and deterministic tests to a volatile backend protocol.

## Decision

Codex-backed tool-aware turns will use a client-managed, normalized transcript.
For each turn, the Codex adapter will serialize the runtime-owned original
prompt/context, explicit tool definitions, and prior validated tool-call/result
history into its private wire request, then normalize one terminal response into
final text, tool calls with stable IDs, or a safe failure.

Provider response or conversation identifiers may be used only as adapter-private
optimizations. They must not be required for correctness and must not appear in
the provider-neutral `agent_runtime` application boundary.

## Consequences

- The production Codex adapter must add tool-definition, tool-call, and tool-result
  wire serialization plus terminal response normalization.
- The agent runtime keeps ownership of tool-loop limits, duplicate-call handling,
  cancellation, and tool-result bounding.
- Offline fixtures can exercise transcript continuity and backend-shape drift
  without live credentials or provider session state.
- Tool-turn request payloads can grow with session history; existing bounded tool
  iterations and result limits remain required, and future context compaction is
  a separate policy decision.
- `fabrica agent` can share `fabrica run`'s Codex credential and default model
  configuration without attempting to reuse its one-shot model adapter.

## Alternatives considered

| Option | Reason rejected |
| --- | --- |
| Require opaque Codex response or conversation IDs between turns | It leaks volatile provider state into runtime continuity, weakens deterministic fixture coverage, and makes backend drift more disruptive. |
| Reuse the one-shot `fabrica run` Codex adapter | It implements final completion, not the tool-aware turn contract, so it cannot safely expose coding tools. |
| Make PydanticAI the mandatory production tool-turn bridge | It adds an unnecessary framework dependency and leaves private Codex wire behavior outside the owning transport slice. |
