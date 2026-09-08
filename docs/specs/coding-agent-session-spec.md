# Spec: Coding Agent Session

## Status

- State: Accepted — implementation planned.
- Implementation status: The primitive runtime, workspace tools, and production patch composition exist; no first-class coding-session CLI or terminal host is implemented yet.
- Accepted by: Maintainer
- Accepted on: September 8, 2026
- Revision: Initial accepted composition contract on September 8, 2026.
- Supersedes: Not applicable.

This document is the canonical source of truth for the coding-agent session product
composition. Derived plans and implementation must preserve its objective,
constraints, execution boundaries, and success criteria; material changes require
an updated and re-confirmed specification.

## Objective

Define a first-class, terminal-hosted Fabrica coding-agent session that runs a
tool-aware model inside one explicitly selected workspace and safely composes the
existing read, search, command, patch, and interaction primitives.

The primary user is a developer who wants to ask Fabrica to investigate, change,
and validate code in a local repository without writing a custom host application.
The session is a product composition, not a new general-purpose tool or a
replacement for the provider-neutral runtime and tool contracts.

## Current Context

- `docs/specs/agent-runtime-spec.md` owns provider-neutral runtime and tool-loop
  behavior.
- `docs/specs/tools-read-files-tool-spec.md`,
  `docs/specs/tools-search-codebase-tool-spec.md`, and
  `docs/specs/tools-run-commands-tool-spec.md` own the read-only workspace and
  command primitives.
- `docs/specs/tools-apply-patch-tool-spec.md` owns patch planning, approval,
  mutation, and recovery semantics.
- `docs/specs/tools-ask-question-tool-spec.md` owns the agent's structured
  missing-information interaction primitive.
- The public `fabrica run` command currently performs one direct runtime prompt
  with optional selected-skill context. It does not expose a workspace coding tool
  loop, terminal interaction transport, or terminal patch-approval host.
- ADR 0010 records the decision to ship this composition as a terminal-hosted,
  workspace-scoped product workflow.

## Assumptions

- A coding session must have one host-selected workspace root; the model must not
  select arbitrary filesystem roots.
- The terminal is sufficient for Version 1 interactive questions and per-patch
  approval, but it is not a replacement for a future VS Code, web, or remote host.
- The default project test suite remains deterministic and offline. Live Codex
  validation remains opt-in and must not be required for normal development or CI.
- Existing primitive contracts remain authoritative. This spec decides their
  composition and defaults; it does not weaken their validation, containment,
  approval, or recovery guarantees.

## Scope

### In Scope

- A planned first-class `fabrica agent` command; the concrete name is accepted as
  `agent` for Version 1.
- Explicit workspace selection, tool exposure, terminal interaction, approval
  behavior, safe defaults, session output, and validation requirements.
- Composition of existing primitives into one tool-aware Codex-backed session.

### Out of Scope

- A VS Code extension, browser UI, daemon, remote multi-user service, or protocol
  for reconnecting to a session.
- Background or detached command execution.
- Autonomous Git commit, push, branch, rebase, merge, or release actions.
- Enabling public web access or Agent Skill script execution by default.
- Replacing tool-specific contracts with a broad, implicit "agent permission."

## Desired Behavior

The planned command shape is:

```bash
uv run fabrica agent --workspace /absolute/path/to/repository --prompt "Fix the failing parser test"
```

The CLI must require `--workspace`. It must resolve the supplied path before
starting the session, reject a missing or non-directory workspace, and pass the
canonical root only to workspace-bound adapters. Model-facing paths remain
workspace-relative wherever the primitive contract requires them.

The command may accept the existing explicit skill-selection options:

```text
--skill <skill-id>
--resource <skill-id>:<resource-id>
--skill-root <path>
```

It must not imply that all discovered skills, resources, or scripts are trusted or
available merely because a skill root was supplied.

### Default Tool Set

An interactive Version 1 session exposes these tools when their composition gates
succeed:

```text
read_files
search_codebase
run_commands
ask_question
apply_patch
```

- `read_files` and `search_codebase` are enabled as bounded, read-only workspace
  inspection primitives.
- `run_commands` is enabled only with the terminal host's explicit default-deny
  permission, environment, approval, sandbox-preflight, timeout, and process
  supervision policy.
- `ask_question` is enabled only for an interactive terminal session.
- `apply_patch` is exposed only when production workspace mutation startup
  recovery and actual-workspace capability verification succeed. If the mutation
  gate fails, the session remains read-only and reports structured gate evidence.

`fetch_web_content`, Agent Skill scripts, Git workflow tools, commits, pushes,
and any generic shell escape hatch are not exposed by default. Later opt-in
surfaces require their own accepted contract and explicit CLI policy.

### Approval and Interaction

The terminal host must distinguish information requests from permission requests:

- `ask_question` asks only for material information or a design decision that the
  model cannot determine from the workspace, prompt, or available tools.
- A patch approval is not an `ask_question` response. Before visible filesystem
  effects, the host renders the immutable patch-plan summary, affected paths,
  derived effects, and plan digest, then obtains a digest-bound approve or deny
  decision.
- A denied, cancelled, EOF, or interrupted approval denies that patch plan only;
  it must not silently approve a changed plan or authorize later plans.
- Terminal EOF or Ctrl-C while a user question is pending cancels the run or the
  pending interaction through the interaction contract. The host must not invent
  a default answer.

The initial command policy must be explicit and documented before implementation.
At minimum it must reject interactive commands and preserve the existing command
tool's workspace containment, filtered environment, timeout, cancellation, and
default-deny requirements. The host may require per-command approval; whether a
safe allowlist can run without confirmation is an implementation-plan decision,
not an implicit grant of unrestricted shell access.

### Session Lifecycle

The terminal host must:

1. Validate the workspace and compose the read-only tools.
2. Perform workspace-mutation recovery and capability gating before exposing
   `apply_patch`.
3. Start the tool-aware Codex-backed runtime with only the tools enabled by the
   resolved session policy.
4. Render model-visible tool outcomes and terminal result evidence without
   exposing credentials, raw sensitive environment values, or untrusted content
   as host instructions.
5. On cancellation or terminal failure, release pending interaction ownership and
   rely on the patch and command primitives for their defined cleanup behavior.

The session must print a clear final disposition: completed, cancelled, failed,
or completed read-only because mutation was unavailable. It must not claim that a
requested edit was applied when the patch gate failed, approval was denied, or the
patch result was indeterminate.

## Boundaries and Constraints

- The CLI and terminal adapters belong at the composition boundary. Domain and
  application layers must not read terminal state, process environment, or current
  working directory directly.
- The session must use a tool-aware model runtime. Direct one-shot completion
  composition is insufficient because it cannot execute the coding tools.
- Every filesystem operation remains constrained to the canonical workspace root
  through its owning adapter. A session-wide root does not authorize arbitrary
  path access.
- Patch safety remains fail-closed: no capability proof, unresolved mutation
  journal, approval failure, or plan-digest mismatch may produce mutation.
- The command tool remains non-interactive and must not be used to bypass
  `apply_patch` for ordinary file edits.
- No raw Codex credential, token, cookie, authorization header, or secret-bearing
  environment value may be printed, stored, or included in tool/model diagnostics.
- The terminal host must not run model-supplied commands through an interactive
  shell or prompt for operating-system escalation.

## Implementation Structure

The first implementation should be one vertical slice that adds a feature-owned
CLI command and terminal adapters, with bootstrap owning dependency wiring. It
may reuse the existing workspace feature compositions, but must not let CLI code
directly orchestrate workspace domain/application behavior.

Expected implementation responsibilities:

- CLI registration and options: product CLI/bootstrap boundary.
- Terminal question publication and answer capture: user-interaction inbound host
  adapter.
- Terminal patch preview and digest-bound approval: workspace-editing host
  adapter.
- Command permission/approval/environment/sandbox policy: command-execution
  composition and host adapters.
- Tool-aware Codex runtime wiring: bootstrap composition.

## Validation

Required deterministic offline coverage includes:

1. CLI rejects a missing, non-directory, or invalid workspace before model I/O.
2. A composed session exposes the intended read/search/command/question tool set.
3. Mutation gating leaves read-only tools available and omits `apply_patch` when
   recovery or capability evidence fails.
4. A model-directed inspect → patch → validate flow applies only a terminal-
   approved digest-bound patch.
5. Denial, EOF, Ctrl-C, and changed-plan approval paths do not mutate files.
6. Command policy rejects disallowed or interactive execution and retains bounded
   timeout/cancellation behavior.
7. No default test reads Codex credentials or calls a live backend.

One small, explicitly opt-in live smoke test may verify the assembled Codex-backed
session after `codex login`. It must run in a disposable workspace, make no Git
commit or network fetch through agent tools, redact diagnostics, and remain
outside the default test suite and CI.

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Documentation | Review links, command status, and tool-policy statements for consistency with primitive specs. | Required now |
| Format | `uv run ruff format --check .` | Required when Python changes are implemented |
| Lint | `uv run ruff check .` | Required when Python changes are implemented |
| Type check | `uv run ty check src tests` | Required when Python changes are implemented |
| Tests | `uv run pytest` | Required when Python changes are implemented |
| Live smoke test | Explicit opt-in only, in a disposable workspace after `codex login`. | Not part of default CI |

## Success Criteria

- `fabrica agent` is a documented and implemented workspace-scoped coding-session
  command, not a custom-host-only composition recipe.
- The session uses the tool-aware runtime and exposes only its policy-approved
  tools.
- Patch mutation is explicitly previewed and approved per digest-bound plan.
- A failed mutation gate produces a usable read-only session with accurate final
  evidence.
- Interactive questions, terminal cancellation, command execution, and patch
  recovery preserve their owning primitive contracts.
- Offline end-to-end tests cover the normal inspect/edit/validate flow and the
  critical denial and fail-closed paths.

## Open Questions

| Question | Impact | Blocking? | Owner | Resolution |
| --- | --- | --- | --- | --- |
| Which direct argv commands, if any, may run without per-command terminal approval? | Defines the usability/safety trade-off for the initial command policy. | Yes, before implementation | Maintainer | Unresolved; default-deny policy remains mandatory. |
| Should the initial terminal host render a unified diff in addition to the immutable patch-plan summary? | Affects approval usability, not patch authorization semantics. | No | Maintainer | Resolve during implementation planning. |
| Should a non-interactive `--read-only` session be included in Version 1? | May support CI-like investigation without terminal interaction. | No | Maintainer | Deferred; interactive terminal session is the accepted first surface. |

## Acceptance and Planning Gate

This accepted specification is ready for implementation planning. The command
permission decision is the only blocking design question; the implementation plan
must resolve and record it before coding begins.

## Execution Boundaries

- Always: Preserve primitive tool contracts, workspace containment, credential
  redaction, explicit approval, and fail-closed mutation behavior.
- Ask first: Expand default tool exposure, enable web/scripts/Git mutation, change
  approval semantics, or introduce a UI/remote-host commitment.
- Never: Treat terminal interaction as blanket authorization, bypass patch
  approval through commands, expose secrets, or make live model access part of
  default tests or CI.
