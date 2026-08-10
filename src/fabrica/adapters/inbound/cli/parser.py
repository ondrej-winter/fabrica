"""Product CLI parser and command registration shell."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.registry import default_cli_contributions

type CliCommand = object


@dataclass(frozen=True, slots=True)
class CliInvocation:
    """Parsed CLI invocation with shared options and one selected command."""

    command: CliCommand
    global_options: CliGlobalOptions = field(default_factory=CliGlobalOptions)


def build_parser() -> argparse.ArgumentParser:
    """Build the side-effect-free CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="fabrica",
        description="Run local subscription-backed agent runtime experiments.",
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
    for contribution in default_cli_contributions():
        contribution.register_commands(subparsers)

    return parser


def parse_args(args: tuple[str, ...] | list[str] | None = None) -> CliInvocation:
    """Parse command-line arguments into an adapter-local invocation object."""
    namespace = build_parser().parse_args(args)
    command_factory = namespace.command_factory
    return CliInvocation(
        command=command_factory(namespace),
        global_options=CliGlobalOptions(
            print_usage=namespace.print_usage,
            print_prices=namespace.print_prices,
            verbose_diagnostics=namespace.verbose_diagnostics,
        ),
    )
