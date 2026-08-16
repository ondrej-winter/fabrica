"""Feature-neutral command-line shell for Fabrica workflows."""

from fabrica.adapters.inbound.cli.contracts import (
    CliCommandRegistrar,
    CliCommandRegistry,
    CliExecutionContext,
    CliGlobalOptions,
    CliRegistrationError,
    CliUsageError,
)

__all__ = [
    "CliCommandRegistrar",
    "CliCommandRegistry",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliRegistrationError",
    "CliUsageError",
]
