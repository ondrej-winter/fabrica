"""Command-line inbound adapter for local agent runtime workflows."""

from fabrica.adapters.inbound.cli.contributions import CliCommandDependencies
from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.parser import (
    CliCommand,
    CliInvocation,
    build_parser,
    parse_args,
)
from fabrica.adapters.inbound.cli.runner import (
    run_cli_command,
)

__all__ = [
    "CliCommand",
    "CliCommandDependencies",
    "CliGlobalOptions",
    "CliInvocation",
    "build_parser",
    "parse_args",
    "run_cli_command",
]
