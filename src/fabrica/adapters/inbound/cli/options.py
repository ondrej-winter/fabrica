"""Global argparse options for the product CLI adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.command import GlobalOptions

if TYPE_CHECKING:
    import argparse


def add_global_options(parser: argparse.ArgumentParser, *, default: bool | object = False) -> None:
    """Add feature-neutral options accepted before or after a command name."""
    parser.add_argument(
        "--print-usage",
        action="store_true",
        dest="_fabrica_cli_print_usage",
        default=default,
        help="Print model usage evidence after command output when available.",
    )
    parser.add_argument(
        "--print-prices",
        action="store_true",
        dest="_fabrica_cli_print_prices",
        default=default,
        help="Print model pricing/cost evidence after command output when available.",
    )
    parser.add_argument(
        "--verbose-diagnostics",
        action="store_true",
        dest="_fabrica_cli_verbose_diagnostics",
        default=default,
        help="Include additional diagnostics without exposing secrets or executing scripts.",
    )


def global_options_from_namespace(namespace: argparse.Namespace) -> GlobalOptions:
    """Return feature-neutral global CLI options from one parsed namespace."""
    return GlobalOptions(
        print_usage=getattr(namespace, "_fabrica_cli_print_usage", False),
        print_prices=getattr(namespace, "_fabrica_cli_print_prices", False),
        verbose_diagnostics=getattr(namespace, "_fabrica_cli_verbose_diagnostics", False),
    )
