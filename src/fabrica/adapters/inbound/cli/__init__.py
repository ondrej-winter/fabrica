"""Feature-neutral command-line shell for Fabrica workflows."""

from fabrica.adapters.inbound.cli.contracts import (
    CliCommandHandler,
    CliCommandRegistrar,
    CliCommandRegistry,
    CliConfigurationError,
    CliError,
    CliExecutionContext,
    CliGlobalOptions,
    CliInvocation,
)
from fabrica.adapters.inbound.cli.parser import (
    build_parser,
    parse_cli_invocation,
)

__all__ = [
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliCommandRegistry",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliInvocation",
    "build_parser",
    "parse_cli_invocation",
]
