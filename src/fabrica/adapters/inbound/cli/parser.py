"""Product CLI parser and command registration shell."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contracts import (
    CLI_HANDLER_NAMESPACE_ATTRIBUTE,
    CliConfigurationError,
    CliGlobalOptions,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fabrica.adapters.inbound.cli.contracts import CliCommandHandler, CliCommandRegistrar


def build_parser(command_registrars: Sequence[CliCommandRegistrar]) -> argparse.ArgumentParser:
    """Build the side-effect-free CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="fabrica",
        description="Run local Fabrica workflows.",
    )
    parser.add_argument(
        "--print-usage",
        action="store_true",
        help="Print model usage evidence after command output when available.",
    )
    parser.add_argument(
        "--print-prices",
        action="store_true",
        help="Print model pricing/cost evidence after command output when available.",
    )
    parser.add_argument(
        "--verbose-diagnostics",
        action="store_true",
        help="Include additional diagnostics without exposing secrets or executing scripts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for register_commands in command_registrars:
        try:
            register_commands(subparsers)
        except argparse.ArgumentError as err:
            msg = f"CLI command registration failed: {err}"
            raise CliConfigurationError(msg) from err

    return parser


def parse_args(
    args: tuple[str, ...] | list[str] | None,
    *,
    command_registrars: Sequence[CliCommandRegistrar],
) -> argparse.Namespace:
    """Parse command-line arguments into an argparse namespace with a command handler."""
    return build_parser(command_registrars).parse_args(args)


def cli_global_options_from_namespace(namespace: argparse.Namespace) -> CliGlobalOptions:
    """Return feature-neutral global CLI options from one parsed namespace."""
    return CliGlobalOptions(
        print_usage=namespace.print_usage,
        print_prices=namespace.print_prices,
        verbose_diagnostics=namespace.verbose_diagnostics,
    )


def cli_handler_from_namespace(namespace: argparse.Namespace) -> CliCommandHandler:
    """Return the command handler attached by the selected subcommand registration."""
    handler = getattr(namespace, CLI_HANDLER_NAMESPACE_ATTRIBUTE, None)
    if not callable(handler):
        msg = "CLI command registration did not configure a handler for the selected command"
        raise CliConfigurationError(msg)
    return handler
