"""Feature-neutral command-line shell for Fabrica workflows.

This package exposes the stable API that feature-owned inbound adapters use to
contribute subcommands to the product CLI. Feature modules register a
``Command`` that configures an ``argparse`` subparser, decodes the parsed
feature namespace into an immutable command object, and runs that object with a
``CommandContext`` containing feature-neutral options and process streams.

Bootstrap code owns dependency composition and passes command registrars to
``run_cli``. The CLI shell owns parser construction, shared options, command
registration validation, explicit stream routing, and translation of user-facing
argparse failures into process exit codes.
"""

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
