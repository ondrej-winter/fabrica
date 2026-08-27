---
name: python-build-extensible-cli
description: Build or refactor an extensible product CLI for a Python hexagonal vertical-slice project, with a feature-neutral shell, feature-owned command contributions, bootstrap-owned composition, stable exit semantics, and tests. Use when multiple feature slices need to contribute commands without leaking parser or process concerns into application or domain code.
metadata:
  version: "1.1.0"
  dependencies:
    tools:
      - name: uv
        purpose: Run the project's configured formatting, type-checking, test, and entrypoint checks.
        required: false
      - name: import-linter
        purpose: Verify CLI-shell and feature-boundary import contracts when configured.
        required: false
    skills:
      - name: python-add-adapter
        purpose: Add individual feature-owned inbound CLI adapters that call application ports.
        required: false
      - name: python-add-port
        purpose: Define missing application inbound ports before exposing a use case through the CLI.
        required: false
      - name: api-and-interface-design
        purpose: Design stable command names, flags, outputs, errors, and extension contracts.
        required: false
      - name: write-pytest-tests
        purpose: Add focused unit, integration, and process-entrypoint tests for CLI behavior.
        required: false
      - name: write-adr
        purpose: Document intentional adapter-to-adapter extension-surface exceptions or other architecture decisions.
        required: false
      - name: run-python-quality-gate
        purpose: Run formatting, linting, type checking, and tests before handoff.
        required: false
---

# Build an Extensible Python CLI

Build or refactor a product CLI for a Python hexagonal vertical-slice project so
multiple feature slices can contribute commands while parser lifecycle, process
streams, global options, and dependency wiring stay outside the application and
domain core.

Use this skill when a project needs a shared command surface, not when a single
small script can remain a simple one-feature inbound adapter.

For deeper implementation details and examples, see
`references/product-cli-shell-pattern.md`.

## When to use this skill

Use this skill when you need to:

- create a product CLI that exposes use cases from multiple feature slices
- add a reusable command contribution contract for feature-owned CLI adapters
- refactor CLI parsing out of feature, application, or domain code
- standardize global options, stream handling, usage diagnostics, and exit codes
- add architecture tests or import-boundary checks for CLI extension surfaces

Do not use this skill to put business orchestration in a generic CLI shell. The
shell should dispatch to feature-owned adapters and application ports; it should
not know feature behavior.

## Target ownership model

- Product CLI shell: owns parser construction, one parse lifecycle, global
  options, help and usage diagnostics, stream routing, registration validation,
  selected-command dispatch, and process-style exit-code conversion.
- Feature inbound CLI adapters: own command names, command-specific parser
  configuration, argument decoding, external-to-application DTO mapping, output
  mapping, and calls to application inbound ports.
- Application layer: owns use-case ports, DTOs, orchestration, and business error
  contracts. It does not import parser, terminal, or process types.
- Domain layer: owns pure business concepts and invariants. It does not import CLI
  or application orchestration code.
- Bootstrap or composition root: owns concrete dependency construction,
  environment/configuration access, registrar assembly, entrypoints, and optional
  test overrides.

Keep the shell's public extension API intentionally small. Export command
contracts such as `Command`, `CommandRegistry`, `CommandContext`, `UsageError`,
and the shell runner, but keep parser construction, registry implementations,
namespace splitting, and runtime invocation types private to the shell package.

## Steps

### 1. Confirm the CLI boundary

Identify the user-facing command surface and its consumers:

- command names and whether they are stable public behavior
- global flags versus command-specific flags
- expected stdout, stderr, stdin, and interactive behavior
- success, usage-error, configuration-error, and unexpected-failure semantics
- whether output is human-readable, structured, or both
- whether commands span one feature slice or many

Use `api-and-interface-design` when command names, flags, output, or errors are a
durable contract.

### 2. Audit the existing architecture

Before editing, inspect:

- current package layout and feature-slice roots
- existing CLI modules, entrypoints, and `pyproject.toml` scripts
- application inbound ports and DTOs for each command's use case
- parser library and project conventions for help and exit codes
- logging, configuration, and stream-handling conventions
- architecture enforcement such as import-linter or boundary tests

If an application inbound port does not exist for the use case, define it first
with `python-add-port` or implement the whole slice with `add-hexagonal-feature`.

### 3. Decide where the extension contract belongs

Choose the narrowest stable place for command contribution types.

Good options:

- a feature-neutral inbound CLI shell package when the contract is parser-specific
  and intentionally part of CLI composition
- a public application or integration package when multiple non-CLI callers need
  the same extension model

Document any intentional exception to normal dependency rules. If feature CLI
adapters import a product CLI adapter package, keep the allowed surface tiny and
consider an ADR with `write-adr`. Feature packages must not import shell parser,
registry, runtime, or bootstrap implementation modules merely for convenience.

The contract should usually include:

- a `Command` value with name, summary, optional description, parser configurer,
  decoder, and runner hooks
- a `CommandRegistry` protocol implemented by the shell
- immutable global options and command context values
- a registration error for programmer or bootstrap mistakes
- a usage error for invalid user-supplied values detected during decoding

### 4. Implement a feature-neutral shell

Keep the shell independent of feature slices and bootstrap composition.

The shell should:

- **Must** expose a root `--version` option that prints the installed distribution version to stdout, exits successfully, and does not require a subcommand
- **Must** source `--version` from canonical package metadata rather than duplicating a version literal in CLI code
- build the root parser and add global options once
- create subparsers and pass a registry to feature registrars
- validate command names, help text, duplicate registrations, and reserved parser
  destinations before runtime, including destinations set through
  `ArgumentParser.set_defaults()` or nested subparsers
- parse argv exactly once
- extract shell-owned values such as selected command and global options
- remove shell-owned parser destinations before invoking feature decoders
- translate decoder-raised usage errors through the parser's normal usage path
- convert parser `SystemExit` for help and usage into integer return codes
- pass explicit stdin, stdout, and stderr streams to command runners
- let unexpected runner failures propagate unless the process boundary explicitly
  owns translation

Avoid importing feature modules, application services, environment variables, or
concrete adapters from the generic shell.

### 5. Implement feature-owned command contributions

For each command, add an inbound CLI adapter under the owning feature slice, for
example:

```text
src/<app_name>/features/<feature_name>/adapters/inbound/cli/
    __init__.py
    command_models.py
    registration.py
    runner.py
    output.py
```

Feature CLI adapters should:

- register commands through the shell's `CommandRegistry` contract
- configure only command-specific arguments and defaults that do not mutate
  shell-reserved destinations
- decode parsed values into frozen adapter-local command objects. When bootstrap
  needs CLI-derived composition settings, return an immutable parsed wrapper that
  keeps the use-case command separate from adapter-local composition options.
- convert repeated arguments to immutable containers such as tuples or frozensets
- validate CLI-only values at the adapter boundary
- call application inbound ports or application services through explicit
  contracts
- map application results and exceptions to CLI output and exit codes
- keep business decisions in the application or domain layer

Do not expose parser namespaces, parser actions, terminal streams, or process
globals in application port signatures.

### 6. Wire the CLI in bootstrap

Keep dependency construction and process entrypoints in bootstrap or a composition
root.

Bootstrap should:

- resolve process argv and streams
- assemble feature command registrars
- provide concrete application services, outbound adapters, configuration, and
  secrets to feature command handlers
- support explicit test overrides when useful
- lazily construct expensive or command-specific dependencies only for the
  selected command
- translate registration/configuration failures at the process boundary into a
  clear stderr diagnostic and documented exit code

Expose the command through the project's normal script entrypoint, for example a
`[project.scripts]` entry in `pyproject.toml`. When the package supports
`python -m <app_name>`, make its `__main__.py` delegate to the same bootstrap
`main()` function rather than duplicate CLI composition.

### 7. Test from the right boundaries

Add tests that prove behavior without coupling to implementation details:

- shell unit tests for help and mandatory version routing, usage errors, duplicate
  registration, reserved destinations, namespace isolation, explicit streams, and
  exit-code conversion
- feature CLI adapter tests for command registration, decoding, immutable command
  values, output mapping, and application-port calls with fakes
- bootstrap or integration tests for registrar assembly, dependency overrides,
  process entrypoint behavior, selected-command lazy construction, and both the
  installed console script and `python -m <app_name>` when both are supported
- architecture tests or import-linter contracts proving the shell does not import
  features or bootstrap and feature slices import only the documented extension
  surface
- process-level smoke tests for the installed script when the project supports
  them

Use `write-pytest-tests` for focused pytest mechanics.

### 8. Update documentation

Document user-visible CLI behavior in the README or command reference:

- invocation examples, including the mandatory root `--version` option
- global option placement rules
- command-specific flags
- stdin/stdout/stderr expectations
- exit-code semantics
- configuration or environment variables used by bootstrap

Document architecture decisions when the CLI introduces a shared extension
surface, a dependency-rule exception, or a new public command contract.

### 9. Validate before handoff

Run focused checks first, then the project quality gate when available.

Useful checks include:

- targeted CLI unit and integration tests
- architecture/import-boundary checks
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run ty check .`
- `uv run pytest`

When available, use `run-python-quality-gate` for the full validation pass.

## Review checklist

- The generic shell has no feature or bootstrap imports.
- Feature CLI adapters call application ports or services instead of domain
  services, repositories, or outbound adapters directly.
- Parser/framework/process types stay out of application and domain contracts.
- Global options and command-specific options are separated.
- Feature decoders receive only feature-owned parsed values.
- Decoded command values, repeated arguments, and composition options are
  immutable snapshots of one invocation.
- Registration errors and user usage errors have distinct exception paths.
- Parser `SystemExit` is converted only around parser construction, parsing, and
  decoding; runner-owned exits and unexpected failures are not silently hidden.
- Help, mandatory root `--version`, usage, stdout, stderr, and exit-code behavior are tested.
- Composition root owns environment/configuration lookup and concrete wiring.
- Any intentional extension-surface dependency exception is documented and, when
  possible, enforced by import-boundary tooling.

## Red flags

- The product CLI shell imports feature packages or concrete application services.
- Application ports accept `argparse.Namespace`, parser objects, terminal streams,
  or framework request/response objects.
- Feature adapters mutate or retain parser namespaces instead of decoding to
  immutable boundary values.
- Feature parser configuration reuses shell-reserved destinations, including
  through `set_defaults()` or nested subparsers.
- Each feature parses argv independently, creating inconsistent global flags or
  help behavior.
- Registration validation failures are reported like user input mistakes without
  distinguishing programmer/configuration errors.
- Global options can collide with feature parser destinations.
- Tests only call runner functions and never verify parser, help, stderr, or
  process-entrypoint behavior.
