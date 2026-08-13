# ADR 0001: Product CLI contribution architecture

## Status

Accepted

## Context

Fabrica exposes one product CLI while multiple feature slices own distinct user workflows. The CLI must keep the generic command shell feature-neutral, preserve hexagonal dependency direction, and avoid import-time plugin discovery or heavyweight composition side effects.

The repository also needs an extension model that lets a feature add subcommands without making the generic CLI import feature internals directly.

## Decision

Use explicit bootstrap-owned CLI contribution aggregation.

- Generic shell modules under `src/fabrica/adapters/inbound/cli/` own global option parsing, contribution validation, generic dispatch, stream context, and expected CLI error translation contracts.
- Feature slices own their subcommand names, argparse registration, adapter-local command models, CLI runners, and output mapping under `features/<feature>/adapters/inbound/cli/`.
- `CliContribution` declares the contribution name, owned subcommand names, owned adapter-local command types, registration callback, and dispatch callback.
- The generic shell validates duplicate contribution names, duplicate subcommand names, duplicate command-type ownership, and overlapping command-type ownership before dispatch.
- Bootstrap factories under `src/fabrica/bootstrap/cli_contributions/` assemble feature CLI adapters with default concrete dependencies.
- Bootstrap may instantiate concrete adapters and composition helpers, but CLI transport-to-application DTO mapping remains in the feature inbound adapter.
- Expected CLI boundary failures use `CliError` subclasses so the process entry point catches known CLI/configuration/dispatch errors without swallowing unrelated programming defects.

## Consequences

- Adding a subcommand requires updating the owning feature contribution metadata and registration together.
- Generic product CLI modules remain feature-agnostic and are protected by import-linter contracts.
- Bootstrap remains the composition root, but should stay thin: it wires dependencies rather than interpreting CLI argv schemas.
- Subcommand collisions fail deterministically with a stable CLI error instead of an argparse traceback.
- Unexpected built-in exceptions such as `TypeError` or `ValueError` are no longer automatically treated as user-facing CLI configuration failures unless translated into an explicit CLI error.
