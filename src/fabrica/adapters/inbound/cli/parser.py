"""Product CLI parser and command registration shell."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from fabrica.adapters.inbound.cli.contracts import (
    CliCommandHandler,
    CliCommandRegistration,
    CliConfigurationError,
    CliExecutionContext,
    CliGlobalOptions,
    CliInvocation,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO

    from fabrica.adapters.inbound.cli.contracts import CliCommandDecoder, CliCommandRegistrar


class _ArgparseCliCommandRegistry:
    """Argparse-backed implementation of the atomic CLI command registry."""

    def __init__(self, subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        self._subparsers = subparsers
        self._registrations: dict[str, CliCommandRegistration[object]] = {}

    def register_command[TCommand](
        self,
        registration: CliCommandRegistration[TCommand],
    ) -> None:
        """Add one named subcommand parser with typed decoding and execution."""
        if registration.name in self._registrations:
            msg = f"CLI command {registration.name!r} is already registered"
            raise CliConfigurationError(msg)
        parser = self._subparsers.add_parser(
            registration.name,
            help=registration.summary,
            description=registration.description,
        )
        _add_global_options(parser, default=argparse.SUPPRESS)
        registration.configure_parser(parser)
        self._registrations[registration.name] = cast("CliCommandRegistration[object]", registration)

    def registration_for(self, command_name: str) -> CliCommandRegistration[object]:
        """Return the registration bound to one parsed command name."""
        try:
            return self._registrations[command_name]
        except KeyError as err:
            msg = f"CLI command {command_name!r} is not registered"
            raise CliConfigurationError(msg) from err


@dataclass(frozen=True, slots=True)
class _ArgparseCliInvocation:
    """Argparse-backed parsed invocation implementation."""

    global_options: CliGlobalOptions
    command: object
    handler: CliCommandHandler[object]

    def execute(self, *, stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
        """Run the selected CLI command with explicit process streams."""
        return self.handler(
            self.command,
            CliExecutionContext(
                global_options=self.global_options,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
            ),
        )


def build_parser(command_registrars: Sequence[CliCommandRegistrar]) -> argparse.ArgumentParser:
    """Build the side-effect-free CLI argument parser."""
    parser, _ = _build_parser_with_registry(command_registrars)
    return parser


def _build_parser_with_registry(
    command_registrars: Sequence[CliCommandRegistrar],
) -> tuple[argparse.ArgumentParser, _ArgparseCliCommandRegistry]:
    parser = argparse.ArgumentParser(
        prog="fabrica",
        description="Run local Fabrica workflows.",
    )
    _add_global_options(parser)
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )
    command_registry = _ArgparseCliCommandRegistry(subparsers)
    for register_commands in command_registrars:
        try:
            register_commands(command_registry)
        except argparse.ArgumentError as err:
            msg = f"CLI command registration failed: {err}"
            raise CliConfigurationError(msg) from err

    return parser, command_registry


def _add_global_options(parser: argparse.ArgumentParser, *, default: bool | object = False) -> None:
    parser.add_argument(
        "--print-usage",
        action="store_true",
        default=default,
        help="Print model usage evidence after command output when available.",
    )
    parser.add_argument(
        "--print-prices",
        action="store_true",
        default=default,
        help="Print model pricing/cost evidence after command output when available.",
    )
    parser.add_argument(
        "--verbose-diagnostics",
        action="store_true",
        default=default,
        help="Include additional diagnostics without exposing secrets or executing scripts.",
    )


def parse_cli_invocation(
    args: Sequence[str] | None,
    *,
    command_registrars: Sequence[CliCommandRegistrar],
) -> CliInvocation:
    """Parse command-line arguments into an executable CLI invocation."""
    parser, command_registry = _build_parser_with_registry(command_registrars)
    namespace = parser.parse_args(args)
    registration = command_registry.registration_for(_command_name_from_namespace(namespace))
    return _ArgparseCliInvocation(
        global_options=cli_global_options_from_namespace(namespace),
        command=_decode_cli_command(parser, registration.decode, namespace),
        handler=registration.handler,
    )


def execute_cli_invocation(
    args: Sequence[str] | None,
    *,
    command_registrars: Sequence[CliCommandRegistrar],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Parse and execute a CLI invocation while honoring explicit process streams."""
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            parser, command_registry = _build_parser_with_registry(command_registrars)
            namespace = parser.parse_args(args)
            registration = command_registry.registration_for(_command_name_from_namespace(namespace))
            invocation = _ArgparseCliInvocation(
                global_options=cli_global_options_from_namespace(namespace),
                command=_decode_cli_command(parser, registration.decode, namespace),
                handler=registration.handler,
            )
        return invocation.execute(stdin=stdin, stdout=stdout, stderr=stderr)
    except SystemExit as err:
        return int(err.code or 0)


def cli_global_options_from_namespace(namespace: argparse.Namespace) -> CliGlobalOptions:
    """Return feature-neutral global CLI options from one parsed namespace."""
    return CliGlobalOptions(
        print_usage=getattr(namespace, "print_usage", False),
        print_prices=getattr(namespace, "print_prices", False),
        verbose_diagnostics=getattr(namespace, "verbose_diagnostics", False),
    )


def _command_name_from_namespace(namespace: argparse.Namespace) -> str:
    command_name = getattr(namespace, "command", None)
    if not isinstance(command_name, str) or not command_name:
        msg = "CLI parser did not capture the selected command name"
        raise CliConfigurationError(msg)
    return command_name


def _decode_cli_command(
    parser: argparse.ArgumentParser,
    decoder: CliCommandDecoder[object],
    namespace: argparse.Namespace,
) -> object:
    try:
        return decoder(namespace)
    except argparse.ArgumentTypeError as err:
        parser.error(str(err))
    except ValueError as err:
        parser.error(str(err))
