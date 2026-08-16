"""Public contracts shared by feature CLI registrations and the product CLI shell."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import argparse
    from typing import TextIO

CLI_COMMAND_NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")


class CliCommandRegistry(Protocol):
    """Public behavior needed to register feature-owned CLI commands."""

    def register_command[TCommand](  # noqa: PLR0913
        self,
        *,
        name: str,
        summary: str,
        configure_parser: Callable[[argparse.ArgumentParser], None],
        decode: Callable[[argparse.Namespace], TCommand],
        handler: Callable[[TCommand, CliExecutionContext], int],
        description: str | None = None,
    ) -> None:
        """Add one named subcommand parser with typed decoding and execution."""


@dataclass(frozen=True, slots=True)
class CliGlobalOptions:
    """Parsed CLI options shared by all subcommands."""

    print_usage: bool = False
    print_prices: bool = False
    verbose_diagnostics: bool = False


@dataclass(frozen=True, slots=True)
class CliExecutionContext:
    """Shared execution context passed from the product CLI shell to one command."""

    global_options: CliGlobalOptions
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


type CliCommandRegistrar = Callable[[CliCommandRegistry], None]


class CliRegistrationError(Exception):
    """Raised when CLI registration or composition is invalid."""


class CliUsageError(Exception):
    """Raised by command decoders for invalid user-supplied CLI values."""


def _validate_registration_name(value: str) -> None:
    _validate_registration_text("name", value)
    if CLI_COMMAND_NAME_PATTERN.fullmatch(value) is None:
        msg = "CLI command registration name must be lowercase kebab-case"
        raise CliRegistrationError(msg)


def _validate_registration_text(field_name: str, value: str) -> None:
    if not value or value.strip() != value:
        msg = f"CLI command registration {field_name} must be a non-empty trimmed value"
        raise CliRegistrationError(msg)


def _validate_registration_callable(name: str, value: object) -> None:
    if not callable(value):
        msg = f"CLI command registration {name} must be callable"
        raise CliRegistrationError(msg)


__all__ = [
    "CliCommandRegistrar",
    "CliCommandRegistry",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliRegistrationError",
    "CliUsageError",
]
