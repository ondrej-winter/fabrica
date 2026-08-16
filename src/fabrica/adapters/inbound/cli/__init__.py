"""Feature-neutral command-line shell for Fabrica workflows."""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003 - public annotations must resolve at runtime.
from importlib import import_module
from typing import Protocol, TextIO, cast

from fabrica.adapters.inbound.cli.contracts import (
    CliCommandDecoder,
    CliCommandHandler,
    CliCommandRegistrar,
    CliCommandRegistry,
    CliCommandSpec,
    CliExecutionContext,
    CliGlobalOptions,
    CliParserConfigurer,
    CliRegistrationError,
    CliUsageError,
)


class _CliShellModule(Protocol):
    """Typed view of the lazily imported product CLI shell module."""

    def run_cli_shell(
        self,
        argv: Sequence[str],
        *,
        command_registrars: Sequence[CliCommandRegistrar],
        stdin: TextIO,
        stdout: TextIO,
        stderr: TextIO,
    ) -> int:
        """Run the product CLI shell."""


def run_cli_shell(
    argv: Sequence[str],
    *,
    command_registrars: Sequence[CliCommandRegistrar],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run the product CLI shell without making shell imports eager for contract consumers."""
    module = cast("_CliShellModule", import_module("fabrica.adapters.inbound.cli.shell"))
    return module.run_cli_shell(
        argv,
        command_registrars=command_registrars,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )


__all__ = [
    "CliCommandDecoder",
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliCommandRegistry",
    "CliCommandSpec",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliParserConfigurer",
    "CliRegistrationError",
    "CliUsageError",
    "run_cli_shell",
]
