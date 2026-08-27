# Product CLI Shell Pattern

Use this reference when implementing the reusable product CLI pattern described
by `python-build-extensible-cli`.

## Concept

The pattern has three collaborators:

```text
process entrypoint
  -> bootstrap/composition root
    -> feature-neutral product CLI shell
      -> feature-owned command registrations
        -> feature inbound CLI runners
          -> application inbound ports/use cases
            -> domain
```

The product CLI shell is intentionally feature-neutral. It owns parser mechanics
and process-facing concerns. Feature slices own the command meanings and
translation into application behavior. Bootstrap owns concrete dependency wiring.

Treat the CLI shell API as a deliberately curated extension surface. Feature
adapters may depend on its public command contracts and shared rendering helpers
when documented, but not on parser construction, registry implementations,
runtime helpers, or bootstrap modules.

## Typical package layout

```text
src/<app_name>/
  __main__.py
  adapters/
    inbound/
      cli/
        __init__.py
        adapter.py
        command.py
        destinations.py
        options.py
        parser.py
        registry.py
        rendering.py
        runtime.py
  bootstrap/
    cli/
      __init__.py
      contracts.py
      entrypoint.py
      registration.py
      features/
        <feature_name>.py
    composition/
      <feature_name>.py
  features/
    <feature_name>/
      application/
        dtos/
        ports/
        use_cases/
      adapters/
        inbound/
          cli/
            __init__.py
            command_models.py
            registration.py
            runner.py
            output.py
```

Small projects can collapse files when responsibilities remain clear. Keep the
same dependency direction even if the file tree is smaller.

## Command lifecycle

Each feature contribution should follow this lifecycle:

```text
configure(parser) -> decode(feature_namespace) -> run(decoded_command, context)
```

- `configure` adds command-specific arguments to a parser supplied by the shell.
- `decode` converts parsed external values into immutable adapter-local command
  objects. When CLI-derived composition settings are needed, it may return an
  immutable wrapper containing both the use-case command and adapter-local
  composition options.
- `run` calls the feature's application boundary and maps results to CLI output
  and exit codes.

This lifecycle keeps parsing separate from execution and makes invalid user input
testable before any business workflow runs.

## Contract sketch

The exact implementation should follow local Python version and parser-library
conventions. A typical `argparse` contract is:

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TextIO
import argparse

type ParserConfigurer = Callable[[argparse.ArgumentParser], None]
type CommandDecoder[TCommand] = Callable[[argparse.Namespace], TCommand]
type CommandRunner[TCommand] = Callable[[TCommand, "CommandContext"], int]


class CommandRegistry(Protocol):
    def register[TCommand](self, command: "Command[TCommand]") -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class Command[TCommand]:
    name: str
    summary: str
    configure: ParserConfigurer
    decode: CommandDecoder[TCommand]
    run: CommandRunner[TCommand]
    description: str | None = None


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    verbose: bool = False


@dataclass(frozen=True, slots=True)
class CommandContext:
    global_options: GlobalOptions
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


type CommandRegistrar = Callable[[CommandRegistry], None]


class RegistrationError(Exception):
    """Programmer or bootstrap error in CLI registration."""


class UsageError(Exception):
    """Invalid user-supplied CLI value detected during decoding."""
```

Use project-specific global options and command fields. Avoid copying fields that
are not part of the target product's CLI contract.

Use keyword-only frozen command definitions and frozen parsed command values.
Normalize `append`, `nargs`, and other mutable `argparse` results to tuples or
frozensets before they leave decoding. This prevents a runner or deferred
composition factory from observing parser-owned mutable state.

## Mandatory version option

Every product CLI built with this pattern **must** provide a root `--version`
option. It must print the executable name and installed distribution version to
stdout, exit with status 0, and work without a selected subcommand. Source the
value from canonical package metadata, such as `importlib.metadata.version`, so
release tooling and CLI output cannot drift through duplicated literals.

For `argparse`, prefer its built-in `version` action on the root parser. Cover the
shell behavior and each installed process entrypoint with tests.

## Namespace isolation

The shell should reserve parser destinations for shell-owned concerns such as the
selected command and global flags. After parsing, it should remove those
destinations before calling feature decoders.

Why this matters:

- feature decoders cannot depend on hidden shell internals
- command-specific values cannot accidentally override global options
- decoded command values become stable snapshots of feature input
- tests can assert the boundary between shell and feature-owned state

When using `argparse`, reserved destination validation may require localized
access to parser internals. Keep that access inside the shell registry and cover
it with tests. Validate both newly added parser actions and explicit defaults,
including feature-owned nested subparsers, so `set_defaults()` cannot override
shell state.

## Error and exit-code matrix

Define the target project's exact matrix. A common shape is:

| Case | Owner | Behavior |
| --- | --- | --- |
| Help requested | Shell/parser | Write help to stdout and return 0 |
| Version requested | Shell/parser | Write installed distribution version to stdout and return 0 without requiring a subcommand |
| Invalid CLI syntax | Shell/parser | Write usage diagnostic to stderr and return 2 |
| Invalid decoded user value | Feature decoder plus shell | Raise usage error and route through parser usage path |
| Invalid registration | Shell/bootstrap | Raise registration error; process boundary writes stderr and returns configuration error code |
| Application-domain expected failure | Feature runner | Map to documented stderr/stdout and exit code |
| Unexpected runner failure | Process boundary or caller | Propagate or translate according to project policy |

Keep programmer/configuration failures distinct from invalid user input. This
makes tests clearer and prevents bootstrap mistakes from looking like normal
usage errors.

In an `argparse` implementation, narrow the `SystemExit` conversion boundary to
parser construction, parsing, and decoder-driven usage handling. Execute the
selected runner only after parsing succeeds, so runner-owned exits and unexpected
failures retain their documented caller semantics.

## Composition-root pattern

Bootstrap should assemble registrars without making the shell depend on feature
modules. One common shape is:

```text
bootstrap.cli.registration
  imports feature CLI registration functions
  imports bootstrap-owned command handler factories
  returns tuple[CommandRegistrar, ...]

bootstrap.cli.features.<feature_name>
  adapts shell CommandContext to feature CLI streams/options
  lazily creates default application workflows through bootstrap.composition
  accepts test overrides for focused integration tests
```

Lazy construction avoids creating expensive clients, loading credentials, or
opening resources for commands that were not selected.

For package applications, expose one bootstrap `main(argv: Sequence[str] | None)
-> int` through the console-script entry and make `__main__.py` call that same
function. This keeps installed-script and `python -m <app_name>` behavior in
lockstep.

## Architecture enforcement examples

When the project uses import-linter or a similar tool, consider contracts such
as:

- generic CLI shell modules must not import feature slices or bootstrap
- feature slices may import only the documented CLI extension contract, not the
  shell parser, registry, runtime, or bootstrap internals
- feature layers still follow adapters -> application -> domain dependency
  direction
- feature inbound adapters must not import outbound adapters directly

If feature adapters import an adapter-owned shell contract, record the exception
and the approved modules in project documentation or an ADR.

## Test matrix

Useful tests include:

- root help uses stdout and exits successfully
- root `--version` reports canonical installed package metadata on stdout and exits successfully without a subcommand
- missing subcommand and invalid flags use stderr and return the usage exit code
- global flags are accepted only where documented
- duplicate command names fail registration
- blank, untrimmed, or invalid command names fail registration
- feature parser actions cannot use reserved destinations
- feature parser defaults cannot override reserved destinations
- feature decoders do not receive shell-owned namespace values
- decoder usage errors map to parser usage diagnostics
- decoded command values are immutable and normalize repeated values
- runner receives explicit streams and immutable global options
- bootstrap can inject fake application ports or workflow runners
- default dependencies are created lazily only for the selected command
- console-script and module entrypoints have equivalent offline help and version
  behavior when both are supported
- process entrypoint returns integer codes and does not leak parser `SystemExit`
- architecture checks enforce the documented dependency surface

## Red flags

- Copying the reference package layout without preserving the dependency model.
- Moving command contribution contracts into the application layer while they
  still expose parser-specific types.
- Putting concrete dependency construction in feature CLI registration modules.
- Letting global options appear in feature decoder namespaces.
- Treating CLI output text as incidental when users or scripts may depend on it.
- Hiding application failures behind generic exit codes without documented
  semantics.
