# 0001. Accept Product CLI Shell Extension Contract

Date: 2026-08-18
Status: Accepted

## Context

Fabrica uses vertical feature slices with hexagonal boundaries. Feature-owned CLI
adapters contribute product commands, while the feature-neutral product CLI shell
owns parser lifecycle, global options, stream routing, usage diagnostics, and
registration validation.

The normal architecture rule forbids adapter-to-adapter dependencies unless they
are intentionally documented. The product CLI shell is an adapter package, but it
also exposes a small extension contract used by feature inbound CLI adapters:
`Command`, `CommandRegistry`, `CommandContext`, and related registration types.
Keeping these contracts in the product shell keeps argparse-specific lifecycle
rules close to the parser implementation, but it creates an intentional exception
to the default adapter dependency rule.

## Decision

We will treat `fabrica.adapters.inbound.cli.command` and
`fabrica.adapters.inbound.cli.rendering` as the approved product CLI extension
surface for feature-owned inbound CLI adapters.

Feature slices may import only this documented surface from the product CLI. The
feature-neutral CLI shell must remain independent of feature slices and
bootstrap-owned composition.

After the shell performs one argparse parse, it splits the resulting namespace
into shell-owned state and feature-owned state before feature decoding. Shell
state becomes the selected command name plus immutable global options carried in
`CommandContext`. Feature decoders receive only feature-owned namespace values and
must return effectively immutable adapter-local boundary values, including
immutable containers for repeated arguments.

## Consequences

- Feature CLI registrations can stay small and declarative while the product
  shell owns shared parser behavior and diagnostics.
- Argparse details remain localized to CLI adapter boundaries rather than leaking
  into application ports or domain code.
- Feature decoders cannot observe or accidentally retain shell-owned parser
  destinations such as global options or selected-command internals.
- Decoded CLI command values are stable snapshots of one user invocation, which
  keeps runner behavior deterministic and testable.
- The exception must remain narrow: feature slices must not import product CLI
  runtime, parser, registry, model-evidence, or bootstrap modules.
- Import-linter policy names and forbidden-module lists must stay aligned with
  this documented exception.
- If the extension surface grows beyond CLI-specific concerns, it should move to
  a dedicated application/public integration boundary.

## Alternatives considered

| Option | Reason rejected |
| ------ | --------------- |
| Move command contribution contracts to an application-layer port immediately | The contracts are intentionally argparse-oriented and currently serve only CLI adapter composition. Moving them now would add abstraction without removing real coupling. |
| Forbid feature adapters from importing all product CLI modules | This would require duplicating parser contribution mechanics or pushing argparse concepts into each feature, weakening the shared shell invariants. |
