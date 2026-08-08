# Spec: Python Agent Runtime

## Objective

Define the direction for a local Python agent runtime that can run developer
workflows through replaceable model transports and explicit tool boundaries.

The primary user is an agent power user who wants local Python agent workflows
with clear runtime contracts, opt-in tool access, and subscription-backed Codex
support as the first high-risk transport capability.

This spec owns the runtime-level design. Codex-specific authentication,
private-backend request details, usage evidence, and live validation rules belong
in `docs/specs/codex-transport-support-spec.md`.

## Current context

- Project: `fabrica`, a Python 3.13 application scaffold for local agent
  runtime experiments.
- Architecture: `src/` layout with hexagonal architecture organized by vertical
  feature slices.
- Tooling: `uv` for environment and command execution, `ruff` for
  formatting/linting, `ty` for type checking, and `pytest` for tests.
- Existing runtime code lives under `src/fabrica/features/agent_runtime/`.
- Codex transport code lives under `src/fabrica/features/codex_transport/` and
  is the first provider support path for the runtime.
- Composition and dependency wiring live under `src/fabrica/bootstrap/`.
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
- Agent Skills support is useful, but it should remain separate from transport
  viability and runtime composition concerns.

## Desired behavior

Fabrica should expose a local Python agent runtime that can:

- accept an application-level runtime command;
- construct model requests through provider-agnostic DTOs and ports;
- call a configured model transport without leaking provider schemas into the
  runtime core;
- collect normalized output, usage evidence, and redacted observations when the
  transport provides them;
- expose selected tools explicitly rather than granting ambient access to local
  system capabilities;
- keep all filesystem, process, network, credential, and framework I/O inside
  adapters or composition-root code;
- keep default automated tests deterministic and offline.

### Runtime milestones

1. Validate Codex transport support separately in
   `docs/specs/codex-transport-support-spec.md`.
2. Use the validated Codex transport through application-level runtime ports and
   DTOs.
3. Add provider-agnostic usage and cost evidence according to
   `docs/specs/provider-agnostic-usage-cost-evidence-spec.md`.
4. Add model-callable tools through explicit, bounded capabilities such as the
   read-only git context tools in
   `docs/specs/read-only-git-context-tools-spec.md`.
5. Explore Agent Skills support only after runtime and transport boundaries are
   stable enough to keep script execution explicit and policy-controlled.

## Explicitly out of scope for the runtime baseline

- Treating `codex exec` as the main integration path.
- Coupling runtime DTOs to private Codex backend request or response schemas.
- Live backend calls in the default test suite or quality gate.
- Unbounded arbitrary shell, filesystem, or network tools.
- Production sandboxing guarantees for skill scripts.
- RAG or vector search for skills.
- Multi-provider polish before the Codex support path proves viable.

## Project structure

- Spec: `docs/specs/python-agent-runtime-spec.md`.
- Codex support spec: `docs/specs/codex-transport-support-spec.md`.
- Runtime source: `src/fabrica/features/agent_runtime/`.
- Runtime application ports and DTOs: under the owning slice's
  `application/ports/` and `application/dtos/` packages.
- Runtime adapters: under the owning slice's `adapters/` package.
- Composition and optional CLI wiring: under `src/fabrica/bootstrap/` or a
  driving adapter owned by the relevant feature slice.
- Unit tests: under `tests/unit/features/agent_runtime/`.
- Integration tests: under `tests/integration/features/agent_runtime/`, with
  live or credential-backed tests skipped unless explicitly opted in.

## Conventions

- Keep dependencies pointing inward toward domain and application code.
- Define application-owned ports before depending on concrete adapters.
- Use application DTOs for normalized commands and results when crossing
  application boundaries.
- Keep provider-specific schemas, credentials, headers, SDKs, and private backend
  details out of the runtime core.
- Keep environment, filesystem, credential, process, and network I/O inside
  adapters or composition-root code.
- Use explicit type annotations on public ports, DTOs, services, and adapter
  APIs.
- Use layer-appropriate exceptions and preserve context with exception chaining.
- Use module-level loggers for production code and never log secrets, tokens,
  cookies, raw auth headers, credential files, personal data, or sensitive
  request/response bodies.

## Testing strategy

- Unit-test runtime orchestration against fake model transports and fake tools.
- Unit-test DTO mappings and result normalization without provider credentials.
- Unit-test tool selection and tool-result loops with deterministic test doubles.
- Keep provider adapter tests in the provider-owning feature slice.
- Keep live backend checks opt-in and isolated from the default `uv run pytest`
  suite.
- Add regression tests for runtime contracts when provider behavior changes the
  normalized result shape.

## Commands and validation

Documentation-only changes should be reviewed for clarity and consistency.
Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Live backend validation, when intentionally performed, must be manual or
explicitly opt-in. It must not be part of the default local or CI test suite.

## Success criteria

- The spec clearly distinguishes runtime responsibilities from provider support
  responsibilities.
- The runtime uses provider-agnostic ports and DTOs instead of private transport
  schemas.
- The first provider support path can be Codex without making the runtime Codex
  specific.
- Runtime tests can run offline and deterministically.
- Future tool, PydanticAI, and Agent Skills work has clear boundaries for where
  code and tests belong.

## Open questions

- What is the smallest stable runtime result contract that supports model output,
  tool calls, usage evidence, and redacted observations without overfitting to
  Codex?
- Which runtime surfaces should become public Python APIs before CLI workflows are
  expanded?
- How much PydanticAI integration is useful before the runtime's own ports and
  DTOs become too thin to justify?
- What approval and sandbox policy is sufficient before Agent Skill scripts are
  exposed through the runtime?
