# 0004. Use Bounded Multimodal Read Tool Runtime Contracts

Date: 2026-08-28
Status: Accepted

## Context

The accepted `read_files` tool contract requires nested JSON arguments and
provider-native multimodal tool returns. The existing runtime accepts only scalar
tool arguments and serializes typed registered-tool outcomes as text. A
`read_files`-specific compatibility path would make generic runtime concerns
depend on one feature and would not provide a safe foundation for later
structured or multimodal tools.

The read tool must also prove workspace containment for the exact filesystem
object read, including symlink replacement races. It must stop blocking local
filesystem reads and complete cleanup within a bounded period when cancellation
or a deadline occurs. Lexical resolve-then-open checks and in-process async or
worker-thread cancellation cannot honestly provide these guarantees.

## Decision

The runtime will use bounded, immutable, provider-neutral contracts for recursive
JSON tool arguments and ordered multipart tool-result content. Provider adapters
will translate those contracts to provider-native tool calls and returns.

`workspace_reading` will support internal symlinks only on macOS and Linux where
a tested, platform-specific descriptor and identity design proves containment for
the object opened. Unsupported platforms or filesystem capabilities will fail
closed. Filesystem reads will execute in supervised helper processes so timeout
and cancellation handling can terminate and join the responsible process within a
bounded cleanup period.

## Consequences

- Runtime argument validation must bound recursive depth, mapping entries,
  sequence entries, and scalar string sizes, reject non-JSON values and non-finite
  numbers, and canonicalize immutable values deterministically for call digests.
- Generic registered-tool outcomes and normalized tool-call results must preserve
  bounded ordered text and image content parts in addition to status and error
  fields. Image bytes remain provider-neutral until the provider adapter renders
  native multipart content.
- The PydanticAI adapter must both accept nested tool-call arguments and render
  ordered multipart tool returns. Its tests must cover nested argument rejection
  limits, canonical duplicate detection, text-only outcomes, and image outcomes.
- The POSIX adapter must probe its required secure-open capabilities, reject
  unsupported platform/filesystem combinations, and use a deterministic seam for
  replacement-race tests. It must not use `Path.resolve()` followed by `open()` as
  a containment guarantee.
- The helper-process protocol needs bounded request/result serialization, deadline
  budgeting across the first attempt and one transient retry, cancellation-aware
  queued-work suppression, process termination, join, and result classification.
- Composition must construct these adapters without filesystem reads or provider
  calls and must expose no provider-specific types to `workspace_reading`.

## Alternatives considered

| Option | Reason rejected |
| ------ | --------------- |
| Add `read_files`-specific nested argument and image-return compatibility shims | It would make generic runtime responsibilities feature-specific and leave later tools without a stable contract. |
| Keep text-only generic tool outcomes and handle images in a provider-facing side channel | It would fragment tool outcome semantics and make ordered text/image results difficult to test provider-neutrally. |
| Reject every symlink or use resolve-then-open containment | Rejecting all internal symlinks unnecessarily reduces useful workspace access; resolve-then-open permits replacement races. |
| Use worker threads for blocking filesystem reads | Threads can prevent queued work and cooperate during streaming, but cannot guarantee termination or handle cleanup when a syscall blocks indefinitely. |
