"""Product CLI parser and command registration shell."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import TYPE_CHECKING

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

    from fabrica.adapters.inbound.cli.contracts import CliCommandRegistrar

_CLI_HANDLER_NAMESPACE_ATTRIBUTE = "cli_handler"


class _ArgparseCliCommandRegistry:
    """Argparse-backed implementation of the atomic CLI command registry."""

    def __init__(self, subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        self._subparsers = subparsers

    def register_command(
        self,
        registration: CliCommandRegistration,
    ) -> argparse.ArgumentParser:
        """Add one named subcommand parser and bind its execution handler."""
        _validate_command_registration(registration)
        parser = self._subparsers.add_parser(
            registration.name,
            help=registration.summary,
            description=registration.description,
        )
        _add_global_options(parser, default=argparse.SUPPRESS)
        parser.set_defaults(**{_CLI_HANDLER_NAMESPACE_ATTRIBUTE: registration.handler})
        return parser


@dataclass(frozen=True, slots=True)
class _ArgparseCliInvocation:
    """Argparse-backed parsed invocation implementation."""

    namespace: argparse.Namespace
    global_options: CliGlobalOptions
    handler: CliCommandHandler

    def execute(self, *, stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
        """Run the selected CLI command with explicit process streams."""
        return self.handler(
            self.namespace,
            CliExecutionContext(
                global_options=self.global_options,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
            ),
        )


def build_parser(command_registrars: Sequence[CliCommandRegistrar]) -> argparse.ArgumentParser:
    """Build the side-effect-free CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="fabrica",
        description="Run local Fabrica workflows.",
    )
    _add_global_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    command_registry = _ArgparseCliCommandRegistry(subparsers)
    for register_commands in command_registrars:
        try:
            register_commands(command_registry)
        except argparse.ArgumentError as err:
            msg = f"CLI command registration failed: {err}"
            raise CliConfigurationError(msg) from err

    return parser


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
    namespace = build_parser(command_registrars).parse_args(args)
    return _ArgparseCliInvocation(
        namespace=namespace,
        global_options=cli_global_options_from_namespace(namespace),
        handler=_cli_handler_from_namespace(namespace),
    )


def cli_global_options_from_namespace(namespace: argparse.Namespace) -> CliGlobalOptions:
    """Return feature-neutral global CLI options from one parsed namespace."""
    return CliGlobalOptions(
        print_usage=getattr(namespace, "print_usage", False),
        print_prices=getattr(namespace, "print_prices", False),
        verbose_diagnostics=getattr(namespace, "verbose_diagnostics", False),
    )


def _cli_handler_from_namespace(namespace: argparse.Namespace) -> CliCommandHandler:
    handler = getattr(namespace, _CLI_HANDLER_NAMESPACE_ATTRIBUTE, None)
    if not callable(handler):
        msg = "CLI command registration did not configure a handler for the selected command"
        raise CliConfigurationError(msg)
    return handler


def _validate_command_registration(registration: CliCommandRegistration) -> None:
    if not registration.name or registration.name.strip() != registration.name:
        msg = "CLI command registration name must be a non-empty trimmed value"
        raise CliConfigurationError(msg)
    if not registration.summary or registration.summary.strip() != registration.summary:
        msg = "CLI command registration summary must be a non-empty trimmed value"
        raise CliConfigurationError(msg)
    if not callable(registration.handler):
        msg = "CLI command registration handler must be callable"
        raise CliConfigurationError(msg)
