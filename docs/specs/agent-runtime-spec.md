# Spec: Agent Runtime

## Status

- State: Accepted — Version 1 runtime baseline.
- Implementation status: Substantially implemented before formal Version 1 acceptance; this revision records the confirmed runtime baseline and its ownership boundaries.
- Accepted by: Maintainer
- Accepted on: September 4, 2026
- Revision: Accepted Version 1 runtime-baseline clarification on September 4, 2026.
- Supersedes: Not applicable.

This document is the canonical source of truth for the requirements it defines. Derived plans and implementation must preserve its objective, constraints, execution boundaries, and success criteria; material changes require an updated and re-confirmed specification.

## Objective

Define the Version 1 direction for a local Python agent runtime that can run
developer workflows through replaceable model transports and explicit tool
boundaries.

The primary user is an agent power user who wants local Python agent workflows
with clear runtime contracts, opt-in tool access, and subscription-backed Codex
support as the first high-risk transport capability.

This spec owns the runtime-level design and the shared model-callable tool-loop
contract. Codex-specific authentication, private-backend request details, and
live validation rules belong in
`docs/specs/codex-transport-spec.md`. Provider-neutral usage and pricing evidence
belongs in `docs/specs/model-usage-and-cost-evidence-spec.md`.

## Current Context

- Project: `fabrica`, a Python 3.14 application scaffold for local agent
  runtime experiments.
- Architecture: `src/` layout with hexagonal architecture organized by vertical
  feature slices.
- Tooling: `uv` for environment and command execution, `ruff` for
  formatting/linting, `ty` for type checking, and `pytest` for tests.
- Existing runtime code lives under `src/fabrica/features/agent_runtime/`. Codex
  transport code lives under `src/fabrica/features/codex_transport/`, and
  composition and dependency wiring live under `src/fabrica/bootstrap/`.
- Tests mirror source ownership under `tests/unit/` and `tests/integration/`.

## Assumptions

- A useful local runtime can start with a narrow model-call loop before becoming
  a full agent orchestration platform.
- Provider-specific details should stay behind transport ports and adapters so
  the runtime can remain provider-agnostic.
- Codex is the first validation provider because subscription-backed access,
  private backend behavior, usage evidence, and quota semantics are the riskiest
  unknowns.
- Default local tests and quality gates must not call live model backends or
  require real subscription credentials.
- Agent Skills are an optional runtime extension. The core runtime must support
  explicit Skills integration boundaries, but must not require skill discovery,
  activation, or script execution in every composition.

## Scope

### In Scope

- The provider-agnostic local agent runtime direction, normalized run results,
  and explicit tool registration.
- The shared model-callable tool-loop lifecycle and control contract defined
  below.
- The integration boundary for optional Agent Skills support.

### Out of Scope

The detailed exclusions already recorded below remain authoritative.

## Desired Behavior

Fabrica should expose a local Python agent runtime that can:

- accept an application-level runtime command;
- construct model requests through provider-agnostic DTOs and ports;
- call a configured model transport without leaking provider schemas into the
  runtime core;
- collect normalized output, usage evidence, and redacted observations when the
  transport provides them;
- expose selected tools explicitly rather than granting ambient access to local
  system capabilities;
- apply the shared tool-loop lifecycle contract below when it invokes registered
  model-facing tools;
- keep all filesystem, process, network, credential, and framework I/O inside
  adapters or composition-root code;
- keep default automated tests deterministic and offline.

### Shared tool-loop lifecycle contract

The runtime baseline owns the following rules for every registered model-facing
tool:

- Tools must execute through typed asynchronous contracts and return typed
  outcomes rather than using free-form text to control the loop.
- The runtime-owned execution context must propagate cancellation and phase
  deadlines with narrowly scoped call metadata; it must not expose arbitrary host
  services to tool handlers.
- The runtime must keep a per-run ledger keyed by model `call_id` and canonical
  normalized-argument digest. An exact duplicate must return the recorded terminal
  result without re-invoking the handler; reusing a `call_id` with different
  normalized arguments must fail before handler execution. Incomplete or
  indeterminate mutation work must not be automatically replayed after restart.
- Outcomes must explicitly distinguish model-continuing completion, recoverable
  rejection or failure, and terminal or fatal runtime-stop dispositions. Fatal
  partial, retained, rollback-failed, or indeterminate mutation outcomes must
  stop the agent loop.
- Result bounding must preserve stable status, error code, mutation guarantee,
  retryability, and terminal or fatal disposition before truncating optional
  preview, excerpt, or evidence detail.

### Runtime milestones

1. Validate Codex transport support separately in
   `docs/specs/codex-transport-spec.md`.
2. Use the validated Codex transport through application-level runtime ports and
   DTOs.
3. Add provider-agnostic usage and cost evidence according to
   `docs/specs/model-usage-and-cost-evidence-spec.md`.
4. Add model-callable tools through explicit, bounded capabilities, with
   tool-specific schemas, authorization, side effects, recovery, and sandbox
   policy owned by the applicable capability or orchestration specification.
5. Integrate Agent Skills as an optional extension according to
   `docs/specs/tools-skills-tool-spec.md`. Skill discovery, activation, resource
   routing, and script-execution guarantees are not prerequisites for core
   runtime compositions.

## Explicitly out of scope for the runtime baseline

- Treating `codex exec` as the main integration path.
- Coupling runtime DTOs to private Codex backend request or response schemas.
- Live backend calls in the default test suite or quality gate.
- Unbounded arbitrary shell, filesystem, or network tools.
- Concrete Python import paths, bootstrap factories, adapters, and DTOs as stable
  public APIs. They remain experimental in Version 1.
- Mandatory Agent Skills discovery, activation, or script execution in every
  runtime composition.
- Production sandboxing guarantees for skill scripts.
- RAG or vector search for skills.
- Multi-provider polish before the Codex support path proves viable.

## Project Structure

- Spec: `docs/specs/agent-runtime-spec.md`.
- Codex support spec: `docs/specs/codex-transport-spec.md`.
- Runtime source: `src/fabrica/features/agent_runtime/`.
- Runtime application ports and DTOs: under the owning slice's
  `application/ports/` and `application/dtos/` packages.
- Runtime adapters: under the owning slice's `adapters/` package.
- Optional Agent Skills integration, including selected script execution, is owned
  by `docs/specs/tools-skills-tool-spec.md` and its relevant feature ports and
  adapters.
- Composition and optional CLI wiring: under `src/fabrica/bootstrap/` or a
  driving adapter owned by the relevant feature slice.
- Unit tests: under `tests/unit/features/agent_runtime/`.
- Integration tests: under `tests/integration/features/agent_runtime/`, with
  live or credential-backed tests skipped unless explicitly opted in.

## Conventions and Constraints

- Keep dependencies pointing inward toward domain and application code.
- Define application-owned ports before depending on concrete adapters.
- Use application DTOs for normalized commands and results when crossing
  application boundaries.
- Keep provider-specific schemas, credentials, headers, SDKs, and private backend
  details out of the runtime core.
- Keep environment, filesystem, credential, process, and network I/O inside
  adapters or composition-root code.
- Implement runtime-shared tool lifecycle semantics in the runtime layer. Keep
  tool-specific schemas, authorization, side effects, recovery, and sandbox policy
  with their owning capability or orchestration specification.
- Use explicit type annotations on public ports, DTOs, services, and adapter
  APIs.
- Use layer-appropriate exceptions and preserve context with exception chaining.
- Use module-level loggers for production code and never log secrets, tokens,
  cookies, raw auth headers, credential files, personal data, or sensitive
  request/response bodies.

## Testing Strategy

- Unit-test runtime orchestration and the shared tool-loop contract against fake
  model transports and fake tools.
- Unit-test DTO mappings, result normalization, cancellation and deadline
  propagation, duplicate-call protection, outcome disposition, and
  status-prioritized result bounding without provider credentials.
- Keep provider adapter tests in the provider-owning feature slice.
- Keep live backend checks opt-in and isolated from the default `uv run pytest`
  suite.
- Optional Agent Skills tests, including script policy, snapshot binding, and
  subprocess cleanup, belong with the Skills extension and must use deterministic
  filesystem/subprocess fakes in the default suite.

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Format | `uv run ruff format --check .` | Required for implementation changes |
| Lint | `uv run ruff check .` | Required for implementation changes |
| Type check | `uv run ty check src tests` | Required for implementation changes |
| Tests | `uv run pytest` | Required for implementation changes |
| Documentation | Review this specification and its internal references for accuracy and consistency. | Required |
| Migration or compatibility | Not applicable unless this specification explicitly introduces a migration. | Not applicable by default |

Documentation-only changes should be reviewed for clarity and consistency.
Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Live backend validation, when intentionally performed, must be manual or
explicitly opt-in. It must not be part of the default local or CI test suite; it
remains owned by the Codex transport specification.

## Success Criteria

- The spec is accepted and clearly distinguishes runtime responsibilities from
  provider and tool-specific responsibilities.
- The runtime uses provider-agnostic ports and DTOs instead of private transport
  schemas.
- The shared tool-loop contract defines typed async execution, cancellation and
  deadline propagation, duplicate-call protection, status-prioritized bounding,
  and continue, terminal, and fatal dispositions.
- The first provider support path can be Codex without making the runtime Codex
  specific.
- Core runtime compositions do not require Agent Skills discovery, activation, or
  script execution.
- Concrete Python import paths and bootstrap factories remain experimental in
  Version 1.
- The default project quality gate passes without live backend calls or
  credentials.

## Open Questions

| Question | Impact | Blocking? | Owner | Resolution |
| --- | --- | --- | --- | --- |
| What additional approval, isolation, and sandbox policy is sufficient before Agent Skill scripts are exposed beyond constrained local subprocess execution? | May constrain a future Skills extension; it does not change the accepted core runtime baseline. | No | Maintainer | Unresolved; retain the Version 1 limitation that no production sandbox guarantee is made. |

## Acceptance and Planning Gate

This accepted Version 1 specification is ready for downstream planning. The
non-blocking Skills sandbox question may constrain only future extension work; it
must not be interpreted as a production sandbox guarantee or as a requirement for
core runtime compositions.

## Execution Boundaries

- Always: Preserve the explicit safety and ownership constraints in this specification.
- Ask first: Expand scope, introduce dependencies, change public contracts, or
  promote experimental concrete Python APIs to stable support commitments.
- Never: Bypass documented security, privacy, architecture, provider, or
  tool-specific boundaries.
