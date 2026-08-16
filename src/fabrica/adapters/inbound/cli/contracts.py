"""Public contracts shared by feature CLI registrations and the product CLI shell."""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TextIO

CLI_COMMAND_NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
type CliParserConfigurer = Callable[[argparse.ArgumentParser], None]
type CliCommandDecoder[TCommand] = Callable[[argparse.Namespace], TCommand]
type CliCommandHandler[TCommand] = Callable[[TCommand, CliExecutionContext], int]


class CliCommandRegistry(Protocol):
    """Public behavior needed to register feature-owned CLI commands."""

    def register[TCommand](
        self,
        command: CliCommandSpec[TCommand],
    ) -> None:
        """Add one named subcommand parser with typed decoding and execution."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CliCommandSpec[TCommand]:
    """Feature-owned command definition for the product CLI shell."""

    name: str
    summary: str
    configure_parser: CliParserConfigurer
    decode: CliCommandDecoder[TCommand]
    handler: CliCommandHandler[TCommand]
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate the feature-owned definition before parser construction."""
        _validate_registration_name(self.name)
        _validate_registration_text("summary", self.summary)
        if self.description is not None:
            _validate_registration_text("description", self.description)
        _validate_registration_callable("parser configurer", self.configure_parser)
        _validate_registration_callable("decoder", self.decode)
        _validate_registration_callable("handler", self.handler)


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
]
