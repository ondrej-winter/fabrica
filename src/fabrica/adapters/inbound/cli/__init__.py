"""Feature-neutral command-line shell for Fabrica workflows."""

from fabrica.adapters.inbound.cli.contracts import (
    CliArgumentConfigurer,
    CliCommandDecoder,
    CliCommandHandler,
    CliCommandRegistrar,
    CliCommandRegistration,
    CliCommandRegistry,
    CliConfigurationError,
    CliError,
    CliExecutionContext,
    CliGlobalOptions,
    CliUsageError,
)

__all__ = [
    "CliArgumentConfigurer",
    "CliCommandDecoder",
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliCommandRegistration",
    "CliCommandRegistry",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliUsageError",
]
