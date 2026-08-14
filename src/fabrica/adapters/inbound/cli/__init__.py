"""Feature-neutral command-line shell for Fabrica workflows."""

from fabrica.adapters.inbound.cli.contracts import (
    CliCommandHandler,
    CliCommandRegistrar,
    CliConfigurationError,
    CliError,
    CliExecutionContext,
    CliGlobalOptions,
    CliHandlerBindingTarget,
    CliInvocation,
    CliSubparsers,
    bind_cli_handler,
)
from fabrica.adapters.inbound.cli.parser import (
    build_parser,
    parse_cli_invocation,
)

__all__ = [
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliHandlerBindingTarget",
    "CliInvocation",
    "CliSubparsers",
    "bind_cli_handler",
    "build_parser",
    "parse_cli_invocation",
]
