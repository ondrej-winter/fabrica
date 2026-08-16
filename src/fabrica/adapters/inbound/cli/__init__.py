"""Feature-neutral command-line API for Fabrica workflows."""

from fabrica.adapters.inbound.cli.command import (
    Command,
    CommandContext,
    CommandRegistry,
    GlobalOptions,
    RegistrationError,
    UsageError,
)
from fabrica.adapters.inbound.cli.runtime import run_cli

__all__ = [
    "Command",
    "CommandContext",
    "CommandRegistry",
    "GlobalOptions",
    "RegistrationError",
    "UsageError",
    "run_cli",
]
