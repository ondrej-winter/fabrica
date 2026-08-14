"""Feature-neutral command-line shell for Fabrica workflows."""

from fabrica.adapters.inbound.cli.contracts import (
    CLI_HANDLER_NAMESPACE_ATTRIBUTE,
    CliCommandHandler,
    CliCommandRegistrar,
    CliConfigurationError,
    CliError,
    CliExecutionContext,
    CliGlobalOptions,
    CliSubparsers,
)
from fabrica.adapters.inbound.cli.parser import (
    build_parser,
    cli_global_options_from_namespace,
    cli_handler_from_namespace,
    parse_args,
)

__all__ = [
    "CLI_HANDLER_NAMESPACE_ATTRIBUTE",
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliSubparsers",
    "build_parser",
    "cli_global_options_from_namespace",
    "cli_handler_from_namespace",
    "parse_args",
]
