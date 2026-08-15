"""Product CLI parser and command registration shell."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Never, cast

from fabrica.adapters.inbound.cli.contracts import (
    CliCommandHandler,
    CliCommandRegistration,
    CliConfigurationError,
    CliExecutionContext,
    CliGlobalOptions,
    CliUsageError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO

    from fabrica.adapters.inbound.cli.contracts import CliCommandDecoder, CliCommandRegistrar


class _ArgparseCliCommandRegistry:
    """Argparse-backed implementation of the atomic CLI command registry."""

    def __init__(self, subparsers: argparse._SubParsersAction[Any]) -> None:
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


class _StreamBoundArgumentParser(argparse.ArgumentParser):
    """Argument parser that writes help and usage errors to explicit streams."""

    def bind_streams(self, *, stdout: TextIO | None, stderr: TextIO | None) -> None:
        """Bind parser diagnostics to explicit streams."""
        self._stdout = stdout if stdout is not None else sys.stdout
        self._stderr = stderr if stderr is not None else sys.stderr

    def print_help(self, file: Any = None) -> None:
        """Print help to explicit stdout by default."""
        super().print_help(file or getattr(self, "_stdout", sys.stdout))

    def print_usage(self, file: Any = None) -> None:
        """Print usage to explicit stdout by default."""
        super().print_usage(file or getattr(self, "_stdout", sys.stdout))

    def error(self, message: str) -> Never:
        """Print argparse usage errors to explicit stderr."""
        self.print_usage(self._stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")

    def exit(self, status: int = 0, message: str | None = None) -> Never:
        """Exit after routing parser messages to explicit stderr."""
        if message:
            getattr(self, "_stderr", sys.stderr).write(message)
        raise SystemExit(status)


def _stream_bound_parser_class(
    *,
    stdout: TextIO | None,
    stderr: TextIO | None,
) -> type[_StreamBoundArgumentParser]:
    class _StreamBoundSubparser(_StreamBoundArgumentParser):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.bind_streams(stdout=stdout, stderr=stderr)

    return _StreamBoundSubparser


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
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> tuple[argparse.ArgumentParser, _ArgparseCliCommandRegistry]:
    parser = _StreamBoundArgumentParser(
        prog="fabrica",
        description="Run local Fabrica workflows.",
    )
    parser.bind_streams(stdout=stdout, stderr=stderr)
    _add_global_options(parser)
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=_stream_bound_parser_class(stdout=stdout, stderr=stderr),
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
) -> _ArgparseCliInvocation:
    """Parse command-line arguments into an executable CLI invocation."""
    return _parse_cli_invocation(args, command_registrars=command_registrars)


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
        invocation = _parse_cli_invocation(
            args,
            command_registrars=command_registrars,
            stdout=stdout,
            stderr=stderr,
        )
    except SystemExit as err:
        return int(err.code or 0)
    return invocation.execute(stdin=stdin, stdout=stdout, stderr=stderr)


def _parse_cli_invocation(
    args: Sequence[str] | None,
    *,
    command_registrars: Sequence[CliCommandRegistrar],
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> _ArgparseCliInvocation:
    parser, command_registry = _build_parser_with_registry(command_registrars, stdout=stdout, stderr=stderr)
    namespace = parser.parse_args(args)
    registration = command_registry.registration_for(_command_name_from_namespace(namespace))
    return _ArgparseCliInvocation(
        global_options=cli_global_options_from_namespace(namespace),
        command=_decode_cli_command(parser, registration.decode, namespace),
        handler=registration.handler,
    )


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
    except CliUsageError as err:
        parser.error(str(err))
