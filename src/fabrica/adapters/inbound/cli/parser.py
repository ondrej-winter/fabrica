"""Product CLI parser and command registration shell."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contributions import CliConfigurationError, validate_cli_contributions
from fabrica.adapters.inbound.cli.options import CliGlobalOptions

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from fabrica.adapters.inbound.cli.contributions import CliContribution

type CliCommand = object


@dataclass(frozen=True, slots=True)
class CliInvocation:
    """Parsed CLI invocation with shared options and one selected command."""

    command: CliCommand
    global_options: CliGlobalOptions = field(default_factory=CliGlobalOptions)
    composition_options: object | None = None


def build_parser(contributions: Sequence[CliContribution]) -> argparse.ArgumentParser:
    """Build the side-effect-free CLI argument parser."""
    validate_cli_contributions(contributions)
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
    for contribution in contributions:
        try:
            contribution.register_commands(subparsers)
        except argparse.ArgumentError as err:
            msg = f"CLI contribution {contribution.name!r} registered invalid subcommands: {err}"
            raise CliConfigurationError(msg) from err

    return parser


def parse_args(
    args: tuple[str, ...] | list[str] | None,
    *,
    contributions: Sequence[CliContribution],
) -> CliInvocation:
    """Parse command-line arguments into an adapter-local invocation object."""
    namespace = build_parser(contributions).parse_args(args)
    command_factory = _command_factory_from_namespace(namespace)
    return CliInvocation(
        command=command_factory(namespace),
        global_options=CliGlobalOptions(
            print_usage=namespace.print_usage,
            print_prices=namespace.print_prices,
            verbose_diagnostics=namespace.verbose_diagnostics,
        ),
        composition_options=_composition_options_from_namespace(namespace),
    )


def _command_factory_from_namespace(namespace: argparse.Namespace) -> Callable[[argparse.Namespace], CliCommand]:
    command_factory = getattr(namespace, "command_factory", None)
    if not callable(command_factory):
        msg = "CLI contribution did not configure a command factory for the selected command"
        raise CliConfigurationError(msg)
    return command_factory


def _composition_options_from_namespace(namespace: argparse.Namespace) -> object | None:
    composition_options_factory = getattr(namespace, "composition_options_factory", None)
    if composition_options_factory is None:
        return None
    if not callable(composition_options_factory):
        msg = "CLI contribution configured a non-callable composition options factory"
        raise CliConfigurationError(msg)
    return composition_options_factory(namespace)
