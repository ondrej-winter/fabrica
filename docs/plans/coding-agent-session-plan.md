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
- [ ] **CAS-05** Add feature-owned `agent` CLI parsing, rendering, and exit codes.
- [ ] **CAS-06** Register bootstrap handlers and production composition.
- [ ] **CAS-07** Add deterministic offline tests and optional live-smoke scaffold.
- [ ] **CAS-08** Update user-facing documentation and specification status.
- [ ] **CAS-09** Run and record final validation.

Keep this plan current while implementing: update this checklist and the matching
detailed task checkbox after each completed task, and record blockers, scope
changes, and newly discovered work in the affected task.

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

- [ ] **CAS-05** Add feature-owned `agent` CLI parsing, rendering, and exit codes.

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

- `uv run fabrica agent --workspace /path/to/repository --prompt "..."` is valid.
- Existing `fabrica run` and other commands retain their behavior.
- CLI streams are injectable and no test requires an actual terminal.

**Verification**

- Unit-test registration, decode, workspace failures, output, and exit-code
  mapping.
- Test invalid workspace paths do not construct or invoke the model runtime.

### CAS-06 — Register bootstrap handlers and production defaults

- [ ] **CAS-06** Register bootstrap handlers and production composition.

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

- `fabrica agent` is reachable through the public CLI entry point.
- The default command uses a tool-aware runtime, never the direct one-shot
  runtime alone.
- Cross-slice wiring remains in bootstrap.

**Verification**

- Integration-test `fabrica.bootstrap.cli.run_cli(...)` with fake dependencies
  and injected streams.
- Run `uv run lint-imports` after composition changes.

### Checkpoint B — First complete vertical slice

- [ ] **CAS-CP-B** Confirm the registered CLI can create a fully offline
  workspace-scoped session, expose the intended tools, and report mutation-gate
  fallback correctly before expanding edge-case coverage.

### CAS-07 — Add deterministic offline coverage

- [ ] **CAS-07** Add deterministic offline tests and optional live-smoke scaffold.

**Likely files**

```text
tests/unit/features/coding_agent_session/...
tests/integration/features/coding_agent_session/test_coding_agent_session_composition.py
tests/integration/bootstrap/cli/test_entrypoint.py
tests/support/coding_agent_session.py
tests/integration/features/coding_agent_session/test_live_coding_agent_session.py
```

**Required coverage**

1. CLI rejects missing, non-existent, file, and invalid workspaces before model
   I/O.
2. A successful composition exposes exactly the five Version 1 tools.
3. Mutation-gate failure omits `apply_patch` while retaining read-only tools and
   produces accurate final evidence.
4. A scripted offline model performs inspect → approved digest-bound patch →
   approved validation command.
5. Patch denial, EOF, Ctrl-C, and changed-plan approval attempts do not mutate
   workspace files.
6. Command policy rejects disallowed or interactive execution; command denial,
   timeout, and cancellation preserve the existing primitive behavior.
7. Pending questions are released or cancelled on terminal cancellation.
8. Default tests do not read Codex credentials or call a live backend.

**Optional live smoke test**

Add only after deterministic coverage is complete. It must be explicitly opt-in,
use a disposable workspace after `codex login`, avoid agent-tool Git mutation and
network fetches, redact diagnostics, and stay outside default pytest and CI. Use
the existing `live_codex` marker and `FABRICA_RUN_LIVE_CODEX_TESTS=1` environment
guard, and document a dedicated non-default invocation by extending
`make test-live-runtime` or adding a dedicated Makefile target.

**Acceptance criteria**

- Every required deterministic scenario in the source specification has direct
  offline test coverage.
- The normal inspect/edit/validate path and all critical fail-closed paths are
  tested without live services.

**Verification**

- Run focused unit and integration session tests.
- Verify the live test has an explicit marker and environment guard.

### CAS-08 — Update product documentation

- [ ] **CAS-08** Update user-facing documentation and specification status.

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

- Review docs against CLI registration, composition, and tests.

### CAS-09 — Complete quality validation and handoff

- [ ] **CAS-09** Run and record final validation.

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

### Final Checkpoint

- [ ] **CAS-CP-FINAL** All tasks, acceptance criteria, and required validation are
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
