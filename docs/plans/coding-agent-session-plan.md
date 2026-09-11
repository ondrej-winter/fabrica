# Implementation Plan: Coding-Agent Session

## Status

- State: Ready for implementation. Maintainer-confirmed decisions are recorded below.
- Source specification: [`docs/specs/coding-agent-session-spec.md`](../specs/coding-agent-session-spec.md).
- Related decision: [ADR 0010](../adr/0010-use-terminal-hosted-workspace-scoped-coding-agent-composition.md).
- Created: September 8, 2026.

## Confirmed Planning Decision

Version 1 uses a conservative command policy: **every command requires an
individual terminal approval**. No executable or argv pattern is pre-approved.

Before a command can be submitted for terminal approval, it must pass the
existing workspace containment, filtered-environment, permission-evaluation,
sandbox-preflight, timeout, and process-supervision rules. Interactive commands,
shell escapes, background execution, Git mutation, web access, and Agent Skill
scripts remain unavailable from the default session.

This resolves the blocking question in the source specification. A future
no-prompt command allowlist requires a separate accepted policy decision and
coverage; it is not part of this plan.

## Confirmed Version 1 Host Decisions

- For command admission, prohibited forms return `DENY`; commands that pass the
  static host policy return `REQUIRE_APPROVAL`; no command returns `ALLOW` in
  Version 1. The terminal host approves only the resolved `PlannedCommand`.
- Patch approval renders only the existing immutable, bounded approval preview,
  affected workspace-relative paths, derived effects, and plan digest. Version 1
  does not render a unified diff; that usability enhancement is deferred.

## Scope

### In scope

- First-class interactive `fabrica agent` CLI command.
- Explicit canonical workspace selection through required `--workspace`.
- Tool-aware Codex session exposing only:
  - `read_files`;
  - `search_codebase`;
  - `run_commands` with per-command terminal approval;
  - `ask_question` in the interactive terminal host;
  - `apply_patch` only when mutation recovery and capability gates pass.
- Terminal adapters for questions, command approval, patch-plan rendering, and
  digest-bound patch approval.
- Read-only fallback and accurate final session evidence when mutation is not
  available.
- Deterministic offline unit and integration coverage, plus an optional opt-in
  live smoke test after offline coverage is complete.
- README and session-documentation updates after implementation.

### Out of scope

- VS Code, browser, web, remote, daemon, reconnectable, or multi-user hosts.
- Detached or background command execution.
- Generic shell access, public web access, and Agent Skill script execution.
- Git commits, pushes, branches, rebases, merges, releases, or other Git
  mutations.
- Persistent approvals, session-wide approval, and command allowlists.
- A non-interactive `--read-only` product mode.

## Architecture and Dependency Order

Create one `coding_agent_session` vertical slice for the user-facing workflow
and terminal host adapters. It composes existing feature contracts rather than
reimplementing their behavior:

```text
coding_agent_session CLI and terminal adapters
    -> session application boundary and result rendering
        -> bootstrap composition
            -> agent_runtime tool loop
            -> workspace_reading / workspace_searching
            -> workspace_command_execution
            -> user_interaction
            -> workspace_editing
```

The bootstrap layer owns cross-slice dependency wiring. The new feature must not
make one feature adapter import another feature's adapter directly. Primitive
workspace containment, patch recovery, approval, cancellation, redaction, and
tool output contracts remain authoritative.

## Progress Tracking

- [x] **CAS-01** Define session DTOs, ports, and final disposition model.
- [x] **CAS-02** Build terminal adapters for questions and approvals.
- [x] **CAS-03** Generalize interactive tool-loop composition for explicit tools.
- [x] **CAS-04** Compose the workspace-scoped coding-agent runtime.
- [x] **CAS-05** Add feature-owned `agent` CLI parsing, rendering, and exit codes.
  - [x] **CAS-05-AC-01** The feature-local registrar accepts `agent` with canonical
        workspace and explicit skill/resource context.
  - [x] **CAS-05-AC-02** Invalid workspace values are rejected before the injected
        feature handler runs.
  - [x] **CAS-05-AC-03** The feature-local runner renders stable session evidence
        and maps completed, cancelled, and failed results to stable exit codes.
  - [x] **CAS-05-V-01** Focused registration and runner tests pass with injected
        streams and faked runtime dependencies.
- [x] **CAS-06** Register bootstrap handlers and production composition.
  - [x] **CAS-06-AC-01** The public bootstrap CLI reaches `fabrica agent` with an
        injected typed session-runtime override and injectable streams.
  - [x] **CAS-06-AC-02** The default terminal composition creates a Codex-backed
        tool-aware runtime with only the Version 1 workspace and interaction tools.
  - [x] **CAS-06-V-01** Focused bootstrap CLI and composition tests plus
        import-linter contracts pass.
- [x] **CAS-07** Add deterministic offline tests and optional live-smoke scaffold.
- [x] **CAS-08** Update user-facing documentation and specification status.
- [x] **CAS-09** Run and record final validation.

Keep this plan current while implementing: update this checklist and every
matching detailed task, acceptance, and verification checkbox after each
completed task, and record evidence, blockers, scope changes, and newly
discovered work in the affected task.

## Detailed Tasks

### CAS-01 — Define the session boundary

- [x] **CAS-01** Define session DTOs, ports, and final disposition model.

**Likely files**

```text
src/fabrica/features/coding_agent_session/application/dtos/session.py
src/fabrica/features/coding_agent_session/application/dtos/__init__.py
src/fabrica/features/coding_agent_session/application/ports/session_runner.py
src/fabrica/features/coding_agent_session/application/ports/__init__.py
src/fabrica/features/coding_agent_session/application/use_cases/run_coding_agent_session.py
src/fabrica/features/coding_agent_session/application/use_cases/__init__.py
```

**Work**

1. Define a command DTO with a canonical workspace root, prompt, and explicit
   selected-skill/resource context compatible with existing runtime contracts.
2. Define immutable session statuses: completed, cancelled, failed, and
   completed read-only because mutation was unavailable.
3. Define a narrow application-owned session-runtime port that accepts the session
   command and cancellation and returns the tool-loop result and mutation-gate
   evidence. Bootstrap must compose and supply this port without the session
   application layer importing bootstrap or another feature's adapters.
4. Define safe, bounded mutation-gate and tool-disposition evidence for final
   terminal rendering.
5. Keep terminal streams, environment reads, and current-working-directory access
   out of application contracts.

**Acceptance criteria**

- The result cannot report that an edit was applied when approval was denied,
  mutation was unavailable, or patch state is indeterminate.
- Invalid empty prompts or invalid session state fail before model execution.
- The slice follows inward dependency direction and does not import bootstrap or
  product CLI code.

**Verification**

- Add focused DTO/use-case unit tests.
- Run `uv run ruff check src/fabrica/features/coding_agent_session tests/unit/features/coding_agent_session`.
- Run `uv run ty check src tests`.

### CAS-02 — Build terminal question and approval adapters

- [x] **CAS-02** Build terminal adapters for questions and approvals.

**Likely files**

```text
src/fabrica/features/coding_agent_session/adapters/inbound/terminal/question_transport.py
src/fabrica/features/coding_agent_session/adapters/inbound/terminal/command_approval.py
src/fabrica/features/coding_agent_session/adapters/inbound/terminal/patch_approval.py
src/fabrica/features/coding_agent_session/adapters/inbound/terminal/rendering.py
src/fabrica/features/coding_agent_session/adapters/inbound/terminal/__init__.py
```

**Work**

1. Implement an `InteractionTransport` adapter that renders structured questions,
   captures an explicit answer through injected streams, and cancels rather than
   inventing an answer on EOF or interruption.
2. Implement a `CommandApprovalResolver` that renders one safe command preview
   and approves only that planned command. Invalid input, denial, EOF, and Ctrl-C
   must deny it.
3. Implement the production workspace-editing approval callback. It must render
   the immutable patch-plan summary, workspace-relative affected paths, derived
   effects, and plan digest before receiving an explicit decision.
4. Do not render a unified diff in Version 1. The terminal host renders only the
   existing immutable, bounded approval preview, workspace-relative affected
   paths, derived effects, and plan digest. Unified-diff rendering is deferred.
5. Bound and redact host-facing output; never display credentials, raw sensitive
   environment values, cookies, authorization headers, or unbounded content as
   host instructions.

**Acceptance criteria**

- Questions, command permissions, and patch permissions are visibly distinct.
- Patch approval is per immutable digest-bound plan, never session-wide.
- EOF, Ctrl-C, or invalid confirmation cannot grant any permission.
- `ask_question` is never reused as destructive-action authorization.

**Verification**

- Unit-test accepted, denied, EOF, and interruption paths with injected streams.
- Test patch digest/affected-path rendering and output redaction.

### CAS-03 — Generalize interactive tool-loop composition

- [x] **CAS-03** Generalize interactive tool-loop composition for explicit tools.

**Likely files**

```text
src/fabrica/bootstrap/composition/user_interaction.py
src/fabrica/bootstrap/composition/tool_loop.py
tests/integration/features/user_interaction/test_ask_question_composition.py
tests/unit/features/agent_runtime/... or tests/unit/features/user_interaction/...
```

**Work**

1. Extend or replace the current interaction composition so it can combine
   `ask_question` with a caller-supplied tuple of explicit registered tools.
2. Preserve interaction-owner isolation and terminal hooks that release pending
   interactions when a run ends.
3. Reject duplicate tool names rather than silently choosing one registration.
4. Preserve headless behavior: a normal tool loop must not implicitly expose
   `ask_question`.

**Acceptance criteria**

- The assembled interactive runtime exposes exactly supplied approved tools plus
  `ask_question`.
- Construction does not call models, read credentials, prompt, execute commands,
  or mutate the workspace.
- Cancellation continues to reach the existing tool-loop and interaction cleanup
  paths.

**Verification**

- Extend interaction composition tests to cover combined tools and duplicate names.
- Run the focused agent-runtime and user-interaction test modules.

### Checkpoint A — Core host boundaries

- [x] **CAS-CP-A** Confirm CAS-01 through CAS-03 expose no extra tools, preserve
      cancellation/approval boundaries, and pass focused tests before production
      workspace composition begins.

### CAS-04 — Compose the workspace-scoped coding session

- [x] **CAS-04** Compose the workspace-scoped coding-agent runtime.

**Likely files**

```text
src/fabrica/bootstrap/composition/coding_agent_session.py
src/fabrica/bootstrap/composition/__init__.py
src/fabrica/features/coding_agent_session/application/use_cases/run_coding_agent_session.py
```

**Work**

1. Add explicit bootstrap options for canonical workspace root, terminal host
   dependencies, Codex/tool-loop settings, selected-context settings, command
   policy dependencies, and patch approval/limits.
2. Compose read-only workspace tools first using the existing read and search
   factories.
3. Compose `run_commands` using the existing command factory with a filtered
   environment builder, static host policy, terminal approval resolver, sandbox
   preflight, bounded limits, and supervised execution. The policy must return
   `DENY` for prohibited forms and `REQUIRE_APPROVAL` for every eligible command;
   Version 1 has no `ALLOW` cases. The resolver acts only on the resolved
   `PlannedCommand`.
4. Perform production workspace-mutation recovery/capability gating before model
   execution using `create_production_workspace_editing_composition(...)`.
5. If the mutation gate fails, retain read/search/command/question tools, omit
   `apply_patch`, and carry safe gate evidence into the final result.
6. Assemble a tool-aware Codex model and the generalized interactive tool loop
   with only the resolved tool set.
7. Apply only explicit existing selected-skill/resource context. A supplied skill
   root must not activate tools, resources, or scripts implicitly.

**Acceptance criteria**

- A valid session has one canonical workspace root, supplied only to the owning
  workspace adapters.
- A successful gate exposes `read_files`, `search_codebase`, `run_commands`,
  `ask_question`, and `apply_patch`.
- A failed gate produces a usable read-only session with no `apply_patch`.
- Default composition exposes no web, script, Git, generic shell, or commit tools.
- No live credentials are read if workspace validation or startup gating fails.

**Verification**

- Offline composition tests with fake tool-aware model turns, host policies, and
  mutation-gate outcomes.
- Assert exact tool names and startup-gate-before-model ordering.

### CAS-05 — Add the feature-owned CLI boundary

- [x] **CAS-05** Add feature-owned `agent` CLI parsing, rendering, and exit codes.

**Likely files**

```text
src/fabrica/features/coding_agent_session/adapters/inbound/cli/command_models.py
src/fabrica/features/coding_agent_session/adapters/inbound/cli/contracts.py
src/fabrica/features/coding_agent_session/adapters/inbound/cli/registration.py
src/fabrica/features/coding_agent_session/adapters/inbound/cli/runner.py
src/fabrica/features/coding_agent_session/adapters/inbound/cli/output.py
src/fabrica/features/coding_agent_session/adapters/inbound/cli/__init__.py
```

**Work**

1. Register the accepted command name, `agent`.
2. Require `--workspace` and `--prompt`.
3. Support existing explicit `--skill`, `--resource`, and `--skill-root` options.
4. Resolve the workspace before runtime composition; reject missing,
   non-existent, non-directory, or unresolvable values before model I/O.
5. Render session scope, enabled-tool disposition, mutation read-only fallback,
   safe final evidence, and a stable final disposition.
6. Map completed, cancelled, configuration, model/session failure, and safety
   denial outcomes to documented stable exit codes.

**Acceptance criteria**

- [x] **CAS-05-AC-01** The feature-local registrar accepts `agent`, requires
      `--workspace` and `--prompt`, canonicalizes the workspace, and decodes explicit
      `--skill`, `--resource`, and `--skill-root` context. Public `fabrica agent`
      reachability is owned by CAS-06.
- [x] **CAS-05-AC-02** Missing, non-existent, non-directory, or unresolvable
      workspaces fail before the injected feature handler can construct or invoke a
      model runtime.
- [x] **CAS-05-AC-03** CLI streams are injectable; the feature-local runner renders
      session evidence and maps completed, cancelled, and failed results to stable
      exit codes without requiring an actual terminal.

**Verification**

- [x] **CAS-05-V-01** Run `uv run pytest --no-cov
tests/unit/features/coding_agent_session/adapters/inbound/cli`; expected result:
      registration, decode, workspace-failure, output, and exit-code tests pass with
      injected streams and fake runtime dependencies.

**Evidence and status**

- Completed by feature-local CLI implementation and focused tests in commit
  `585cd26` (`test_registration.py` and `test_runner.py`). The focused test command
  uses the established `--no-cov` pattern because repository-wide coverage gates are
  meaningful only for the full suite. Public CLI registration and default production
  composition remain required CAS-06 work.

### CAS-06 — Register bootstrap handlers and production defaults

- [x] **CAS-06** Register bootstrap handlers and production composition.

**Likely files**

```text
src/fabrica/bootstrap/cli/features/coding_agent_session.py
src/fabrica/bootstrap/cli/contracts.py
src/fabrica/bootstrap/cli/registration.py
src/fabrica/bootstrap/composition/coding_agent_session.py
tests/integration/bootstrap/cli/test_entrypoint.py
```

**Work**

1. Add the bootstrap-owned `agent` command handler and feature registrar.
2. Add narrow typed dependency overrides for deterministic CLI tests.
3. Build default production dependencies only in bootstrap: Codex tool-aware
   model, terminal adapters, workspace tool adapters, command policy, and patch
   approval callback.
4. Do not wire prohibited default tools into this command.

**Acceptance criteria**

- [x] **CAS-06-AC-01** `fabrica agent` is reachable through the public CLI entry
      point with a narrow `CodingAgentSessionRuntime` dependency override for
      deterministic tests.
- [x] **CAS-06-AC-02** The default command uses
      `create_terminal_workspace_coding_agent_session_runtime()`, which supplies the
      Codex tool-aware model rather than the direct one-shot runtime alone.
- [x] **CAS-06-AC-03** Bootstrap owns cross-slice wiring and exposes only
      `read_files`, `search_codebase`, `run_commands`, `apply_patch` when the mutation
      gate enables it, and interactive `ask_question`; prohibited default tools remain
      unwired.

**Verification**

- [x] **CAS-06-V-01** Ran `uv run pytest --no-cov
tests/unit/bootstrap/cli/test_coding_agent_session.py
tests/unit/bootstrap/composition/test_coding_agent_session.py` (7 passed).
- [x] **CAS-06-V-02** Ran `uv run lint-imports` (11 contracts kept, 0 broken).

**Evidence and status**

- The bootstrap registrar delegates `agent` to the feature-local parser while
  supplying the bootstrap-owned handler. `CliDependencyOverrides` provides the
  narrow typed runtime override used by deterministic public-entrypoint tests.
- The default handler composes the terminal runtime only after CLI workspace
  validation. That composition uses `create_codex_tool_aware_model`, terminal
  question/command/patch approval adapters, the filtered command environment, and
  the mutation startup gate. The focused composition tests verify both the enabled
  tool set and the read-only fallback that omits `apply_patch`.

### Checkpoint B — First complete vertical slice

- [x] **CAS-CP-B** Confirm the registered CLI can create a fully offline
      workspace-scoped session, expose the intended tools, and report mutation-gate
      fallback correctly before expanding edge-case coverage.

**Evidence and status**

- The bootstrap CLI tests exercise the registered `agent` command using an
  injected runtime and streams. The session-composition tests verify exactly the
  five enabled tools after a successful mutation gate and the read-only fallback
  that omits `apply_patch` after gate failure.
- The deterministic CAS-07 integration scenario now exercises the actual
  temporary-workspace inspect → digest-bound approved patch → approved validation
  command flow without Codex credentials or network access.

### CAS-07 — Add deterministic offline coverage

- [x] **CAS-07** Add deterministic offline tests and optional live-smoke scaffold.

**Likely files**

```text
tests/unit/features/coding_agent_session/...
tests/integration/features/coding_agent_session/test_coding_agent_session_composition.py
tests/integration/bootstrap/cli/test_entrypoint.py
tests/support/coding_agent_session.py
tests/integration/features/coding_agent_session/test_live_coding_agent_session.py
```

**Required coverage**

1. [x] CLI rejects missing, non-existent, file, and invalid workspaces before
       model I/O.
2. [x] A successful composition exposes exactly the five Version 1 tools.
3. [x] Mutation-gate failure omits `apply_patch` while retaining read-only tools
       and produces accurate final evidence.
4. [x] A scripted offline model performs inspect → approved digest-bound patch →
       approved validation command.
5. [x] Patch denial, EOF, Ctrl-C, and changed-plan approval attempts do not
       mutate workspace files.
6. [x] Command policy rejects disallowed or interactive execution; command
       denial, timeout, and cancellation preserve the existing primitive behavior.
7. [x] Pending questions are released or cancelled on terminal cancellation.
8. [x] Default tests do not read Codex credentials or call a live backend.

**Optional live smoke test**

Added after deterministic coverage. It is explicitly opt-in,
use a disposable workspace after `codex login`, avoid agent-tool Git mutation and
network fetches, redact diagnostics, and stay outside default pytest and CI. Use
the existing `live_codex` marker and `FABRICA_RUN_LIVE_CODEX_TESTS=1` environment
guard, and document a dedicated non-default invocation by extending
`make test-live-runtime` or adding a dedicated Makefile target.

**Verification**

- [x] **CAS-07-V-01** Ran `uv run pytest --no-cov
tests/unit/features/workspace_editing/application/test_patch_dtos.py
tests/unit/features/workspace_editing/application/test_recovery_state.py
tests/integration/features/coding_agent_session/test_coding_agent_session_composition.py
tests/integration/features/coding_agent_session/test_live_coding_agent_session.py` (30 passed, 1 skipped).
- [x] **CAS-07-V-02** Ran focused Ruff and Ty checks plus `uv run lint-imports`;
      all passed, with 11 import contracts kept.

**Evidence and status**

- Added a real temporary-workspace session integration test that scripts
  `read_files`, an exact-digest host-approved `apply_patch`, and an approved argv
  validation command. It uses an injected model and host ports; it performs no
  model I/O, credential loading, or network access.
- Added `test_live_coding_agent_session.py`, guarded by `live_codex` and
  `FABRICA_RUN_LIVE_CODEX_TESTS=1`, plus `make test-live-agent-session`. The live
  smoke test uses only a disposable pytest workspace and instructs the agent not
  to mutate, execute commands, or ask questions.
- The integration scenario uncovered macOS spawn serialization failures for
  immutable `mappingproxy` metadata in helper-process patch DTOs. `PatchPathEvidence`,
  `PatchError`, and `PatchJournalRecord` now reconstruct immutable metadata after
  pickle round trips; focused regression tests cover the helper-process boundary.

**Acceptance criteria**

- Every required deterministic scenario in the source specification has direct
  offline test coverage.
- The normal inspect/edit/validate path and all critical fail-closed paths are
  tested without live services.

**Verification**

- Run focused unit and integration session tests.
- Verify the live test has an explicit marker and environment guard.

### CAS-08 — Update product documentation

- [x] **CAS-08** Update user-facing documentation and specification status.

**Likely files**

```text
README.md
docs/README.md
docs/specs/coding-agent-session-spec.md
```

**Work**

1. Document command invocation, required workspace and prompt arguments, skill
   selection options, default tool set, exclusions, and terminal approval model.
2. Document that command approval is per command and patch approval is per
   digest-bound plan.
3. Document read-only fallback when workspace mutation capability is unavailable.
4. Document offline default validation and separately opt-in live smoke testing.
5. Update the canonical specification to record the confirmed per-command
   admission mapping and the Version 1 no-unified-diff decision; remove the stale
   blocking open question and update the planning-gate text.
6. Update source-spec implementation status only when all required implementation
   and validation work is complete.

**Acceptance criteria**

- Documentation does not imply blanket authorization or autonomous mutation.
- Documented CLI behavior matches the implementation and test coverage.
- No credentials or unsafe production examples are introduced.

**Verification**

- [x] **CAS-08-V-01** Reviewed README and canonical-spec command, tool-policy,
      approval, fallback, exit-status, and live-smoke statements against CLI
      registration, terminal composition, and deterministic coverage.
- [x] **CAS-08-V-02** Ran `uv run fabrica agent --help` and confirmed its required
      `--workspace` / `--prompt` options plus repeatable `--skill`, `--resource`, and
      `--skill-root` options; confirmed `make help` lists `test-live-agent-session`.

**Evidence and status**

- `README.md` now documents the implemented workspace-scoped command, restricted
  Version 1 tool set, per-command and exact-digest patch approval, read-only
  mutation-gate fallback, exit statuses, and separately opt-in live smoke test.
- Documentation indexes now describe the terminal coding-agent composition as
  implemented rather than planned. The canonical source specification removes the
  resolved transcript-continuity question and records the confirmed Version 1
  command-admission and no-unified-diff patch-approval decisions.

### CAS-09 — Complete quality validation and handoff

- [x] **CAS-09** Run and record final validation.

**Required commands after Python changes**

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check src tests
uv run pytest
uv run lint-imports
```

Run `make quality` as the repository's configured aggregate quality check after
the individual commands. Do not include the opt-in live smoke test in the default
quality gate.

**Acceptance criteria**

- All required quality checks pass without bypasses.
- Handoff notes identify files changed, tests executed, opt-in checks not run,
  and any remaining deferred work.

**Verification evidence**

- [x] **CAS-09-V-01** `uv run ruff format --check .` passed: 804 files already
      formatted.
- [x] **CAS-09-V-02** `uv run ruff check .` and `uv run ty check src tests`
      passed without findings.
- [x] **CAS-09-V-03** `uv run lint-imports` passed: 11 contracts kept and none
      broken.
- [x] **CAS-09-V-04** `uv run pytest` passed: 2,294 passed, 4 skipped, and
      97.53% total coverage.
- [x] **CAS-09-V-05** `make quality` passed after the individual checks; its
      configured Ruff, Ty, import-linter, and default offline pytest steps completed
      without modifying source files.
- [x] **CAS-09-V-06** `git diff --check` passed after validation.

**Opt-in validation not run**

- `make test-live-agent-session` was intentionally not run. It requires
  `FABRICA_RUN_LIVE_CODEX_TESTS=1`, reads local Codex credentials only after that
  explicit gate, and calls the live backend. The default offline suite covers the
  session composition deterministically; the live smoke remains an operator-run,
  disposable-workspace check after `codex login`.

**Handoff status**

- The completed slice changes include terminal CLI/runtime composition, offline
  inspect/edit/validate coverage, an opt-in live read-only smoke scaffold,
  spawn-safe workspace-editing DTO serialization, and product/specification
  documentation. Existing staged work remains preserved; no commit was created.
- Deferred work remains limited to accepted product exclusions and the
  non-interactive `--read-only` session question recorded by the source
  specification.

### Final Checkpoint

- [x] **CAS-CP-FINAL** All tasks, acceptance criteria, and required validation are
      complete; `fabrica agent` is documented, workspace-scoped, tool-aware,
      approval-bound, fail-closed for mutation, and fully covered by offline tests.

## Risks and Guardrails

1. The existing interactive composition currently centers on `ask_question`.
   Generalizing it must preserve interaction ownership and must not accidentally
   expose tools in headless runs.
2. Terminal reads must integrate with existing asynchronous cancellation and
   cleanup contracts. A naïve blocking read must not prevent Ctrl-C/EOF from
   cancelling pending interaction safely.
3. Patch rendering must display only immutable, bounded plan data. A preview must
   not introduce an alternate authorization path.
4. Per-command approval is the confirmed Version 1 safety/usability trade-off.
   Do not add an allowlist opportunistically.
5. The implementation must preserve import-linter hexagonal and cross-slice
   adapter restrictions; bootstrap owns feature composition.
6. This project is pre-release, so prefer a clear composition API over
   compatibility shims for experimental helpers when a replacement is necessary.
