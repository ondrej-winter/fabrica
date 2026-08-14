"""Product CLI parser and command registration shell."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contracts import (
    CliConfigurationError,
    CliGlobalOptions,
    CliInvocation,
    cli_handler_from_namespace,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fabrica.adapters.inbound.cli.contracts import CliCommandRegistrar


def build_parser(command_registrars: Sequence[CliCommandRegistrar]) -> argparse.ArgumentParser:
    """Build the side-effect-free CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="fabrica",
        description="Run local Fabrica workflows.",
    )
    _add_global_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for register_commands in command_registrars:
        try:
            register_commands(subparsers)
        except argparse.ArgumentError as err:
            msg = f"CLI command registration failed: {err}"
            raise CliConfigurationError(msg) from err

    return parser


def _add_global_options(parser: argparse.ArgumentParser) -> None:
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


def parse_cli_invocation(
    args: Sequence[str] | None,
    *,
    command_registrars: Sequence[CliCommandRegistrar],
) -> CliInvocation:
    """Parse command-line arguments into an executable CLI invocation."""
    namespace = build_parser(command_registrars).parse_args(args)
    return CliInvocation(
        namespace=namespace,
        global_options=cli_global_options_from_namespace(namespace),
        handler=cli_handler_from_namespace(namespace),
    )


def cli_global_options_from_namespace(namespace: argparse.Namespace) -> CliGlobalOptions:
    """Return feature-neutral global CLI options from one parsed namespace."""
    return CliGlobalOptions(
        print_usage=getattr(namespace, "print_usage", False),
        print_prices=getattr(namespace, "print_prices", False),
        verbose_diagnostics=getattr(namespace, "verbose_diagnostics", False),
    )
