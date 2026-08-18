"""Global argparse options for the product CLI shell."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.command import GlobalOptions

if TYPE_CHECKING:
    import argparse


def add_global_options(parser: argparse.ArgumentParser) -> None:
    """Add feature-neutral options accepted before a command name.

    Args:
        parser: Root parser that should accept the shared options.

    """
    parser.add_argument(
        "--print-usage",
        action="store_true",
        dest="_fabrica_cli_print_usage",
        help="Print model usage evidence after command output when available.",
    )
    parser.add_argument(
        "--print-prices",
        action="store_true",
        dest="_fabrica_cli_print_prices",
        help="Print model pricing/cost evidence after command output when available.",
    )
    parser.add_argument(
        "--verbose-diagnostics",
        action="store_true",
        dest="_fabrica_cli_verbose_diagnostics",
        help="Include additional diagnostics without exposing secrets or executing scripts.",
    )


def global_options_from_namespace(namespace: argparse.Namespace) -> GlobalOptions:
    """Extract feature-neutral global CLI options from a parsed namespace."""
    return GlobalOptions(
        print_usage=getattr(namespace, "_fabrica_cli_print_usage", False),
        print_prices=getattr(namespace, "_fabrica_cli_print_prices", False),
        verbose_diagnostics=getattr(namespace, "_fabrica_cli_verbose_diagnostics", False),
    )
