# 0001 - Compose product CLI contributions in bootstrap

## Status

Accepted

## Context

Fabrica exposes one product CLI while the codebase is organized around
hexagonal vertical feature slices. The CLI must keep global command-line
behavior discoverable without allowing the generic product shell to depend on
feature internals or concrete infrastructure.

Feature-owned commands also need default production wiring, test-time injected
dependencies, and offline `--help` behavior that does not read credentials,
read skill roots, call external backends, prompt for approval, or execute
scripts.

## Decision

The product CLI uses a contribution boundary:

- Generic shell modules under `src/fabrica/adapters/inbound/cli/` own global
  options, parser construction, contribution validation, and dispatch only.
- Feature slices own subcommand registration, adapter-local parsed command
  models, CLI runners, and output mapping under
  `src/fabrica/features/<feature>/adapters/inbound/cli/`.
- Bootstrap-owned factories under `src/fabrica/bootstrap/cli_contributions/`
  assemble feature CLI adapters with default concrete dependencies.
- Concrete runtime, filesystem, script, git, and external-service dependencies
  are constructed in bootstrap composition helpers rather than during generic
  parser construction.

## Consequences

- The generic CLI shell remains feature-agnostic and is protected by import-linter
  contracts.
- Feature slices can add CLI commands without modifying generic parser dispatch
  logic beyond contribution aggregation in bootstrap.
- `--help` and parser construction stay offline and side-effect free.
- Composition options crossing the generic shell are intentionally opaque to the
  shell and validated by the owning bootstrap contribution.
- Inbound CLI adapters must map and validate external values before invoking
  application-owned ports or use cases.
- Workflow orchestration belongs behind application-owned inbound ports/use
  cases; CLI adapters should translate input, prompt where user interaction is
  truly adapter-owned, call a port, and map output.

## Validation

The following project checks protect this decision:

- `uv run lint-imports`
- CLI parser and contribution tests under `tests/unit/adapters/inbound/cli/`
- Feature-owned CLI adapter tests under `tests/unit/features/*/adapters/inbound/cli/`
- Offline entrypoint smoke tests under `tests/integration/adapters/inbound/cli/`
