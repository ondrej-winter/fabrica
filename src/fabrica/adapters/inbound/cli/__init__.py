"""Feature-neutral command-line shell for Fabrica workflows."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contracts import (
    CliCommandRegistrar,
    CliCommandRegistry,
    CliCommandSpec,
    CliExecutionContext,
    CliGlobalOptions,
    CliRegistrationError,
    CliUsageError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO


def run_cli_shell(
    argv: Sequence[str],
    *,
    command_registrars: Sequence[CliCommandRegistrar],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run the product CLI shell without making shell imports eager for contract consumers."""
    module = import_module("fabrica.adapters.inbound.cli.shell")
    return module.run_cli_shell(
        argv,
        command_registrars=command_registrars,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )


__all__ = [
    "CliCommandRegistrar",
    "CliCommandRegistry",
    "CliCommandSpec",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliRegistrationError",
    "CliUsageError",
    "run_cli_shell",
]
