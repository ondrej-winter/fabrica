# Run Commands Tool — Implementation Plan

**Readiness: Ready for implementation.** The accepted canonical specification
defines `execution` normalization and a complete serialized-result budget that
fits the bounded multipart runtime transport.

**Source of truth:** `docs/specs/tools-run-commands-tool-spec.md` remains the
canonical product contract. Update this plan after each completed task, scope
change, or newly discovered blocker.

## Implementation-scoping follow-ups

The following implementation-scoping decisions must be completed during the
named RC tasks. They do not block the accepted canonical contract:

- Define the host-owned resolution path for `REQUIRE_APPROVAL`, including the
  command/batch scope, unavailable or rejected approval behavior, and stable
  result mapping. The process supervisor must remain UI-free.
- Align plan terminology with the accepted result contract: permission and
  sandbox denials need distinct stable error codes or outcomes, not new statuses
  unless the specification changes its stable status set.
- Identify the source-of-truth `WorkspacePathResolver` reuse or conformance-test
  strategy so command execution does not become a fourth divergent workspace
  containment implementation.
- Define the Version 1 supported-platform and unsupported-platform behavior for
  the public composition factory, since the planned concrete supervisor is POSIX
  process-group based.
- Specify deadline precedence, batch-timeout behavior, termination grace, and
  the host-owned maximum concurrency limit as explicit DTO/port contracts.
- Expand the RC verification items into the canonical direct argv, shell,
  result-status, environment, output, and deterministic POSIX child-tree test
  matrix from the specification.

## Confirmed implementation baseline

The following host-policy decisions were confirmed during the implementation
interview on August 30, 2026. They sharpen the accepted specification and are
binding for this implementation plan.

- The public composition factory must require explicit host-provided permission,
  sandbox, and environment policy dependencies. It must not supply permissive
  fallback policies.
- Version 1 exposes both direct `argv` execution and explicit `shell` mode. The
  host configures the sole permitted shell executable; the model must never
  choose a shell executable.
- The model chooses only `parallel` or `sequential` execution. The host-owned
  limits configuration exclusively determines maximum process concurrency. When
  omitted, `execution` normalizes to `parallel` before planning.
- Commands may include environment overrides only for keys authorized by the
  host-provided environment policy. The model must not receive arbitrary parent
  environment inheritance or unrestricted override keys.
- Permission and sandbox denials must remain command-scoped, use stable distinct
  error codes or outcomes, and include a concise host-safe reason. They must not
  expose policy rules, allowlists, or sandbox internals.
- The 96,000-character limit applies to the complete serialized model-visible
  JSON result, including metadata and JSON escaping. The limiter reserves result
  structure first and fairly allocates the remainder to retained output streams.

## Goal and scope

Add a `workspace_command_execution` vertical slice that exposes the model-facing
`run_commands` tool. It will support direct argv execution and explicit
host-configured shell execution, explicit parallel/sequential batches,
workspace-contained working directories, host-filtered environments, host-owned
permission and sandbox decisions, non-interactive process-tree supervision,
bounded separate-stream output, and structured results in request order.

### In scope

- Feature-owned DTOs, ports, validation, planning, scheduling, output limiting,
  registered-tool adapter, and bootstrap composition.
- POSIX process-group execution with closed stdin, piped stdout/stderr,
  timeout/cancellation cleanup, and TERM-to-KILL escalation.
- Unit and POSIX integration tests, README usage, and public bootstrap export.

### Out of scope

- Detached/background process lifecycle management.
- Interactive stdin, PTY semantics, terminal emulation, or automatic retries.
- Model-controlled shell selection or full host-environment inheritance.
- Strong cross-platform sandbox implementations. Version 1 receives sandbox
  decisions through a host-controlled port.

## Dependency graph

```text
Async registered-tool contracts
  └── run_commands inbound adapter and schema
        └── normalized DTOs and validation
              ├── workspace cwd resolver
              ├── environment builder
              ├── permission and sandbox preflight ports
              ├── batch scheduler and deadline handling
              └── process supervisor and output collector
  └── bootstrap composition and tool-loop integration
```

## Progress tracking

- [x] **RC-01** Extend bounded multipart runtime transport for the canonical serialized-result budget.
- [x] **RC-02** Create feature-owned DTOs, errors, limits, ports, and validators.
- [x] **RC-03** Implement cwd, environment, permission, and sandbox planning.
- [ ] **RC-04** Implement process supervision, output capture, deadline, timeout, and cancellation behavior.
- [x] **RC-05** Implement parallel/sequential scheduling and fair output limiting.
- [ ] **RC-06** Add the registered-tool adapter and canonical schema.
- [ ] **RC-07** Add bootstrap composition, public export, and documentation.
- [ ] **RC-08** Run focused and complete quality validation.

## Ordered tasks

### RC-01 — Align the result contract and runtime transport

**Dependency:** None. Must complete before registered-tool result serialization.

**Likely files**

- `docs/specs/tools-run-commands-tool-spec.md`
- `src/fabrica/features/agent_runtime/application/dtos/tools.py`
- `src/fabrica/features/agent_runtime/adapters/outbound/registered_tool/adapter.py`
- Mirrored agent-runtime DTO and registered-tool adapter tests.

- [x] Keep separate `stdout` and `stderr` fields as the only model-visible command
  output payloads; remove stale single-`output` examples and field lists.
- [x] Extend registered-tool runtime transport to carry the complete bounded
  structured command result in at most two `ToolTextContent` parts, each capped
  at 48,000 characters.
- [x] Ensure a multipart typed outcome does not duplicate its full payload in
  `result_text` or become `LIMIT_EXCEEDED` because of the legacy text-result cap.
- [x] Confirm that every command result is retained when the batch output cap is reached.

**Acceptance criteria**

- [x] **RC-01-A** The specification has exactly one authoritative output field structure: separate `stdout` and `stderr`, never combined `output`.
- [x] **RC-01-B** A complete serialized structured command result of at most 96,000 characters reaches the model in at most two 48,000-character text parts without generic runtime truncation.

**Verification**

- [x] **RC-01-V** Add runtime DTO and adapter regression tests for multipart output, including a near-96,000-character serialized result with escape-heavy output, no duplicate full `result_text`, and no incorrect `LIMIT_EXCEEDED` status.

### RC-02 — Establish feature contracts and validation

**Likely files**

- `src/fabrica/features/workspace_command_execution/application/dtos/run_commands.py`
- `src/fabrica/features/workspace_command_execution/application/ports/workspace_command_execution.py`
- `src/fabrica/features/workspace_command_execution/application/validation.py`
- Matching package exports and tests under `tests/unit/features/workspace_command_execution/application/`.

- [ ] Define immutable batch, command, planned-command, output, result, status,
  skipped-reason, and limits DTOs.
- [ ] Define ports for cwd resolution, environment construction, permission,
  approval resolution, sandbox preflight, process supervision, and optional
  host-private progress.
- [ ] Normalize omitted execution to `parallel`; validate execution policy; exactly
  one of `argv`/`shell`; argv values; NUL
  bytes; command input size; cwd syntax; env keys/values; and finite bounded timeouts.
- [ ] Define the top-level request-rejection versus command-scoped planning-result
  mapping, the host-owned concurrency limit, and the source-of-truth workspace
  resolver contract.

**Acceptance criteria**

- [ ] **RC-02-A** Invalid shapes produce deterministic command-scoped results before spawn.
- [ ] **RC-02-B** Core contracts do not import subprocess, provider, or transport types.

**Verification**

- [ ] **RC-02-V** Run focused DTO, validation, and port tests plus `uv run ruff check .` and `uv run ty check src tests`.

### RC-03 — Implement planning and host-policy boundaries

**Likely files**

- `src/fabrica/features/workspace_command_execution/application/use_cases/plan_commands.py`
- `src/fabrica/features/workspace_command_execution/adapters/outbound/posix_filesystem/path_resolution.py`
- `src/fabrica/features/workspace_command_execution/adapters/outbound/environment/filter.py`
- `src/fabrica/features/workspace_command_execution/adapters/outbound/authorization/adapter.py`
- Mirrored unit tests.

- [ ] Resolve cwd against the canonical workspace root; reject absolute,
  drive-prefixed, backslash, traversal, missing, non-directory, and symlink-escape paths.
- [ ] Build child environments from a host-filtered allowlist and command-local
  overrides without mutating `os.environ`.
- [ ] Require identical permission and sandbox preflight for argv and shell modes;
  never classify safety through command prefixes.
- [ ] Resolve `REQUIRE_APPROVAL` through an explicit host-owned port before
  execution, with no approval UI or prompting in the process supervisor.

**Acceptance criteria**

- [ ] **RC-03-A** No command reaches the executor until planning succeeds.
- [ ] **RC-03-B** Cwd containment is explicitly distinct from sandboxing.
- [ ] **RC-03-C** Denial, sandbox rejection, and cwd failure remain distinct outcomes.

**Verification**

- [ ] **RC-03-V** Test traversal, symlink escapes, environment filtering and override precedence, parent-environment immutability, and policy-port calls.

### RC-04 — Implement non-interactive process supervision

**Implementation note (August 31, 2026):** The slice now includes
`PosixCommandSupervisor`, which runs direct argv or host-configured shell
commands with closed stdin, separate stdout/stderr pipes, a new POSIX process
session, effective command/host deadline checks, and TERM-to-KILL cleanup.
Focused tests cover direct argv and shell execution, non-zero exits, missing
executables, timeout, cancellation, and retained partial output. The remaining
RC-04 verification work is deterministic TERM-to-KILL escalation and child-tree
cleanup coverage, so this milestone remains unchecked.

**Likely files**

- `src/fabrica/features/workspace_command_execution/adapters/outbound/process_supervisor/adapter.py`
- `src/fabrica/features/workspace_command_execution/adapters/outbound/process_supervisor/output_collector.py`
- Potentially a narrow shared extension to `src/fabrica/adapters/outbound/process_group_subprocess/runner.py` only if a genuinely reusable contract emerges.
- Mirrored unit and POSIX integration tests.

- [ ] Spawn argv without shell parsing; invoke only the host-configured shell for explicit shell mode.
- [ ] Use `DEVNULL` for stdin, stdout/stderr pipes, isolated process groups, and graceful-to-forced tree termination.
- [ ] Observe cancellation and the earliest effective deadline while retaining partial separate-stream output.
- [ ] Map spawn failure, exit code, signal, timeout, cancellation, and infrastructure failure to command-scoped results.

**Acceptance criteria**

- [ ] **RC-04-A** No PTY or interactive input is used.
- [ ] **RC-04-B** Timeout and cancellation terminate descendants and preserve partial output.
- [ ] **RC-04-C** Non-zero exits are normal command results.

**Verification**

- [ ] **RC-04-V** Test spawn arguments, TERM-to-KILL escalation, timeout, cancellation, UTF-8 boundaries, and a POSIX child-tree cleanup scenario.

### RC-05 — Implement scheduling and fair output limiting

**Implementation note (August 31, 2026):** The slice now includes `RunCommands`,
which plans the full batch before launch, preserves result order, limits parallel
starts through host-owned concurrency, continues sequential batches after ordinary
per-command failures, maps queued batch cancellation/timeouts to stable skipped
reasons, and maps active batch-timeout outcomes to `BATCH_TIMEOUT`. The canonical
result formatter and limiter preserve all result metadata, keep stdout/stderr
separate, and fairly allocate actual JSON-serialized capacity within the 96,000
character host limit.

**Likely files**

- `src/fabrica/features/workspace_command_execution/application/use_cases/run_commands.py`
- `src/fabrica/features/workspace_command_execution/application/output_limiting.py`
- `src/fabrica/features/workspace_command_execution/application/result_formatting.py`
- Mirrored unit tests.

- [ ] Compute one authoritative batch deadline from host deadline, batch timeout, and active per-command timeouts.
- [ ] Define deadline precedence and termination-grace ownership so the scheduler
  and supervisor cannot introduce competing timeout layers.
- [ ] Run eligible commands concurrently in `parallel` mode without sibling cancellation on individual failure.
- [ ] Run `sequential` commands in order but continue after non-zero exits,
  timeout, rejection, invalid planning, and spawn failure.
- [ ] Skip unstarted commands only for batch cancellation or batch timeout using
  `BATCH_CANCELLED` or `BATCH_TIMED_OUT`.
- [ ] Apply per-command and fair serialized-result output allocation without
  dropping any result, reserving JSON structure and required metadata before
  retained stream content.

**Acceptance criteria**

- [x] **RC-05-A** Results always retain request order.
- [x] **RC-05-B** Sequential execution controls start order only, not short-circuit behavior.
- [x] **RC-05-C** Serialized-result limiting preserves every command result and
  keeps the complete JSON result within the 96,000-character budget.

**Verification**

- [x] **RC-05-V** Test out-of-order parallel completion, sequential continuation, batch-wide stop conditions, and fair allocation of oversized output.
- [x] **RC-05-V2** Test host concurrency enforcement and the resolved deadline,
  batch-timeout, cancellation, and queued-command result mappings.

### RC-06 — Add model-facing adapter and runtime integration

**Likely files**

- `src/fabrica/features/workspace_command_execution/adapters/inbound/registered_tool/adapter.py`
- Associated package exports and adapter tests.
- Runtime transport changes established by RC-01 in
  `src/fabrica/features/agent_runtime/application/dtos/tools.py` and
  `src/fabrica/features/agent_runtime/adapters/outbound/registered_tool/adapter.py`.

- [ ] Add `RUN_COMMANDS_TOOL_NAME`, concise description, and closed JSON schema
  with explicit mutually exclusive argv/shell modes.
- [ ] Convert provider-neutral arguments into feature DTOs and pass cancellation/
  deadlines from `ToolExecutionContext`.
- [ ] Map request-shape errors to recoverable `INVALID_ARGUMENTS`; preserve
  ordinary command failures inside the structured batch result.
- [ ] Serialize the bounded structured result through the RC-01 multipart contract.

**Acceptance criteria**

- [ ] **RC-06-A** Schema and adapter reject unknown/invalid fields before the use case.
- [ ] **RC-06-B** Ordinary command failures do not become generic tool failures.
- [ ] **RC-06-C** Serialization uses separate streams and the bounded multipart response design without duplicating full output.

**Verification**

- [ ] **RC-06-V** Add schema, mapping, cancellation/deadline, separate-stream, and multipart-output-budget regression tests.

### RC-07 — Compose, export, and document

**Likely files**

- `src/fabrica/bootstrap/composition/workspace_command_execution.py`
- `src/fabrica/bootstrap/__init__.py`
- `README.md`
- `tests/integration/features/workspace_command_execution/test_run_commands_tool_composition.py`

- [ ] Add `create_run_commands_registered_tool_adapter(...)` with explicit
  workspace, shell, environment, permission, sandbox, limits, and optional progress dependencies.
- [ ] Define and test fail-closed behavior when the host requests the POSIX
  implementation on an unsupported platform, unless a platform-specific
  supervisor is supplied.
- [ ] Keep construction inert: no workspace inspection, spawn, policy evaluation,
  or model call before tool invocation.
- [ ] Re-export the supported factory from `fabrica.bootstrap`.
- [ ] Document host-policy requirements, argv preference, explicit shell mode, and
  the tool's role alongside read/search/edit tooling.

**Acceptance criteria**

- [ ] **RC-07-A** Composition cannot silently create a permissive command tool.
- [ ] **RC-07-B** README examples match the actual public factory signature.

**Verification**

- [ ] **RC-07-V** Integration-test registration in `create_tool_loop_runtime` and prove factory construction remains inert using fakes.

### RC-08 — Validate and hand off

- [ ] Run focused unit and integration tests for the new slice and changed shared runtime components.
- [ ] Run `uv run ruff format .`.
- [ ] Run `uv run ruff check .`.
- [ ] Run `uv run ty check src tests`.
- [ ] Run `uv run lint-imports`.
- [ ] Run `uv run pytest`.

**Acceptance criteria**

- [ ] **RC-08-A** Validation remains offline and does not require credentials, live network access, or an interactive terminal.
- [ ] **RC-08-B** Full project quality checks pass.
- [ ] **RC-08-C** Handoff records the separate-stream multipart transport contract, platform limitations, and deferred work.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Shell mode bypasses safety controls | Route argv and shell through identical validation, permission, sandbox, deadline, and output controls. |
| Cwd containment is mistaken for sandboxing | Keep resolver and sandbox ports distinct and document the boundary. |
| Child processes survive cancellation | Use process groups with TERM-to-KILL cleanup and test descendant cleanup. |
| Output exhausts memory or model context | Stream to bounded separate buffers, reserve serialized JSON metadata, fairly allocate remaining output capacity, and transport the complete 96,000-character result in at most two 48,000-character text parts. |
| Sequential behavior regresses to short-circuiting | Test continuation after every unsuccessful command outcome. |
| Environment leaks secrets | Require a host-supplied environment filter and test secret exclusion. |
| Approval or path-resolution behavior diverges between tools | Define explicit approval resolution and shared resolver ownership or conformance tests before implementing adapters. |
| POSIX-only implementation appears cross-platform | Fail closed or require an injected platform-specific supervisor; document and test the public factory behavior. |

## Deferred follow-up

- Strong OS-specific sandbox mechanisms.
- A retained host-private progress-event envelope.
- Detached process lifecycle APIs.
- Interactive stdin or PTY semantics.
- Model-selectable shell and full-environment inheritance.
