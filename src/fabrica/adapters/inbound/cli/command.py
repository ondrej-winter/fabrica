"""Public command contracts for the product CLI adapter."""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TextIO

COMMAND_NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
type ParserConfigurer = Callable[[argparse.ArgumentParser], None]
type CommandDecoder[TCommand] = Callable[[argparse.Namespace], TCommand]
type CommandRunner[TCommand] = Callable[[TCommand, CommandContext], int]


class CommandRegistry(Protocol):
    """Behavior needed by feature adapters that contribute CLI commands."""

    def register[TCommand](self, command: Command[TCommand]) -> None:
        """Add one named command to the product CLI."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Command[TCommand]:
    """Feature-owned command definition for the product CLI."""

    name: str
    summary: str
    configure: ParserConfigurer
    decode: CommandDecoder[TCommand]
    run: CommandRunner[TCommand]
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate the feature-owned definition before parser construction."""
        validate_command_name(self.name)
        validate_command_text("summary", self.summary)
        if self.description is not None:
            validate_command_text("description", self.description)
        validate_command_callable("parser configurer", self.configure)
        validate_command_callable("decoder", self.decode)
        validate_command_callable("runner", self.run)


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    """Parsed options shared by all product CLI commands."""

    print_usage: bool = False
    print_prices: bool = False
    verbose_diagnostics: bool = False


@dataclass(frozen=True, slots=True)
class CommandContext:
    """Execution context passed from the product CLI to one command."""

    global_options: GlobalOptions
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


type CommandRegistrar = Callable[[CommandRegistry], None]


class RegistrationError(Exception):
    """Raised when CLI registration or composition is invalid."""


class UsageError(Exception):
    """Raised by command decoders for invalid user-supplied CLI values."""


def validate_command_name(value: str) -> None:
    """Validate a feature-owned command name."""
    validate_command_text("name", value)
    if COMMAND_NAME_PATTERN.fullmatch(value) is None:
        msg = "CLI command registration name must be lowercase kebab-case"
        raise RegistrationError(msg)


def validate_command_text(field_name: str, value: str) -> None:
    """Validate command registration text fields."""
    if not value or value.strip() != value:
        msg = f"CLI command registration {field_name} must be a non-empty trimmed value"
        raise RegistrationError(msg)


def validate_command_callable(name: str, value: object) -> None:
    """Validate callable command registration fields."""
    if not callable(value):
        msg = f"CLI command registration {name} must be callable"
        raise RegistrationError(msg)


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
]
