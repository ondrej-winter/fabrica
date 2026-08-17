"""Feature-neutral command-line API for Fabrica workflows."""

from fabrica.adapters.inbound.cli.adapter import run_cli
from fabrica.adapters.inbound.cli.command import (
    Command,
    CommandContext,
    CommandDecoder,
    CommandRegistrar,
    CommandRegistry,
    CommandRunner,
    GlobalOptions,
    ParserConfigurer,
    RegistrationError,
    UsageError,
)

__all__ = [
    "Command",
    "CommandContext",
    "CommandDecoder",
    "CommandRegistrar",
    "CommandRegistry",
    "CommandRunner",
    "GlobalOptions",
    "ParserConfigurer",
    "RegistrationError",
    "UsageError",
    "run_cli",
]
