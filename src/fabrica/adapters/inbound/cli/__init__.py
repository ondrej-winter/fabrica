"""Feature-neutral command-line shell for Fabrica workflows."""

from fabrica.adapters.inbound.cli.contracts import (
    CliCommandHandler,
    CliCommandRegistrar,
    CliConfigurationError,
    CliError,
    CliExecutionContext,
    CliGlobalOptions,
    CliHandlerBindingTarget,
    CliSubparsers,
    bind_cli_handler,
    cli_handler_from_namespace,
)
from fabrica.adapters.inbound.cli.parser import (
    build_parser,
    cli_global_options_from_namespace,
    parse_args,
)

__all__ = [
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliHandlerBindingTarget",
    "CliSubparsers",
    "bind_cli_handler",
    "build_parser",
    "cli_global_options_from_namespace",
    "cli_handler_from_namespace",
    "parse_args",
]
