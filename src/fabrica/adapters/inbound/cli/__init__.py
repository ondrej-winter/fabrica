"""Feature-neutral command-line shell for Fabrica workflows."""

from fabrica.adapters.inbound.cli.contributions import CliConfigurationError, CliDispatchError, CliError
from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.parser import (
    CliCommand,
    CliInvocation,
    build_parser,
    parse_args,
)
from fabrica.adapters.inbound.cli.runner import (
    CliCommandExecutionOptions,
    run_cli_command,
)

__all__ = [
    "CliCommand",
    "CliCommandExecutionOptions",
    "CliConfigurationError",
    "CliDispatchError",
    "CliError",
    "CliGlobalOptions",
    "CliInvocation",
    "build_parser",
    "parse_args",
    "run_cli_command",
]
