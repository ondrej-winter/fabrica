# 0001. Compose Product CLI in Bootstrap

Date: 2026-08-11
Status: Accepted

## Context

The product CLI spans multiple vertical feature slices. The generic CLI shell owns
process-level concerns such as parsing shared options, dispatching parsed
commands, standard streams, and product-edge output rendering. Individual feature
slices own their command models, command registration, local CLI runner logic,
and application boundary contracts.

Earlier CLI composition mixed these responsibilities by keeping concrete
feature wiring and broad dependency surfaces inside the product CLI adapter. That
made the generic shell aware of concrete slices, encouraged a global dependency
bag that listed every feature dependency, and weakened the vertical-slice
boundary expected by the hexagonal architecture rules.

The remediation introduced a contribution-driven parser and dispatcher, moved
default feature dependency selection to bootstrap, and strengthened import-linter
contracts so feature slices cannot import product CLI or bootstrap modules and
generic CLI shell modules cannot import feature or bootstrap code.

## Decision

We will compose the product CLI in `fabrica.bootstrap.cli`, while keeping the
generic product CLI shell contribution-driven and feature-agnostic. Feature
slices publish CLI contributions through their inbound adapters, and bootstrap
aggregates those contributions, selects default concrete dependencies lazily,
and passes them into the shell explicitly.

## Consequences

- `fabrica.adapters.inbound.cli` remains the product shell boundary for generic
  parser, contribution, option, runner, and output mechanics.
- `fabrica.bootstrap.cli` owns default CLI contribution aggregation and concrete
  adapter/use-case selection for the executable entrypoint.
- Feature slices keep command registration, command models, runner logic, and
  local CLI dependency contracts inside their own inbound adapter packages.
- The console script points at `fabrica.bootstrap.cli:main`, and the module
  entrypoint delegates to that bootstrap entrypoint.
- CLI help remains offline because contributions register command shapes without
  constructing live backends, reading credentials, inspecting skill roots,
  executing scripts, or prompting for approval.
- Contributions close over narrow dependency providers rather than receiving a
  global shell-owned dependency bag for all features.
- The product output layer may render multiple published result families at the
  product edge, but feature slices must not expose another slice's DTOs as their
  own boundary contract.
- Architecture boundaries are enforced by import-linter contracts in
  `pyproject.toml` in addition to code review.

## Alternatives considered

| Option | Reason rejected |
| ------ | --------------- |
| Keep concrete CLI wiring in `fabrica.adapters.inbound.cli` | This keeps the generic shell coupled to feature slices and makes it harder to enforce a feature-agnostic parser and dispatcher. |
| Keep a global CLI dependency bag | A shell-owned bag for every feature dependency obscures ownership and grows whenever unrelated slices add CLI behavior. |
| Let feature slices import bootstrap helpers | This reverses dependency direction and allows feature code to depend on composition-root details. |
| Move all CLI code under bootstrap | This would hide legitimate inbound adapter responsibilities, such as feature-owned command registration and adapter-local mapping. |
