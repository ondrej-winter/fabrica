"""Public command contracts for feature-owned CLI contributions."""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TextIO

COMMAND_NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
type ParserConfigurer = Callable[[argparse.ArgumentParser], None]
"""Callback that adds feature-owned arguments to one subcommand parser."""

type CommandDecoder[TCommand] = Callable[[argparse.Namespace], TCommand]
"""Callback that maps parsed feature arguments into an immutable command object."""

type CommandRunner[TCommand] = Callable[[TCommand, CommandContext], int]
"""Callback that executes a decoded command and returns a process exit code."""


class CommandRegistry(Protocol):
    """Registration boundary implemented by the product CLI shell.

    Feature-owned inbound adapters depend on this protocol rather than on the
    argparse-backed implementation. That keeps command contribution code focused
    on parser configuration, decoding, and use-case dispatch while the shell
    owns shared options and parser lifecycle details.
    """

    def register[TCommand](self, command: Command[TCommand]) -> None:
        """Add one named command to the product CLI.

        Args:
            command: Feature-owned command definition to expose as a subcommand.

        Raises:
            RegistrationError: If the command definition conflicts with shell
                invariants or an already registered command.

        """


@dataclass(frozen=True, slots=True, kw_only=True)
class Command[TCommand]:
    """Feature-owned command definition for one product CLI subcommand.

    The shell validates static registration data immediately, then calls
    ``configure`` during parser construction, ``decode`` after argparse parsing,
    and ``run`` only after decoding succeeds. The generic parameter represents
    the immutable feature command object returned by ``decode`` and consumed by
    ``run``. Decoders should produce effectively immutable boundary values: use
    frozen data classes or equivalent value objects, convert repeated arguments
    to tuples or frozensets, and avoid retaining mutable ``argparse`` containers.
    """

    name: str
    """Lowercase kebab-case subcommand name shown to CLI users."""
    summary: str
    """Short help text used in the root command list."""
    configure: ParserConfigurer
    """Callback that adds feature-owned arguments to the subcommand parser."""
    decode: CommandDecoder[TCommand]
    """Callback that maps the parsed feature namespace into an immutable command object."""
    run: CommandRunner[TCommand]
    """Callback that executes the decoded command with shell-provided context."""
    description: str | None = None
    """Optional longer help text for the subcommand help page."""

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
    """Parsed feature-neutral options shared by all product CLI commands.

    Global options must appear before the selected subcommand. The shell removes
    its internal argparse destinations before feature decoders see the namespace,
    then passes these values through ``CommandContext``.
    """

    print_usage: bool = False
    print_prices: bool = False
    verbose_diagnostics: bool = False


@dataclass(frozen=True, slots=True)
class CommandContext:
    """Execution context passed from the CLI shell to one command runner.

    The context carries only shell-owned concerns: parsed global options and the
    explicit process streams selected by bootstrap or tests. Feature runners use
    their own composition options and application ports for business behavior.
    """

    global_options: GlobalOptions
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


type CommandRegistrar = Callable[[CommandRegistry], None]


class RegistrationError(Exception):
    """Raised when CLI registration or shell composition is invalid.

    These failures indicate programmer or bootstrap configuration errors, not
    invalid user input. Bootstrap translates them at the process boundary.
    """


class UsageError(Exception):
    """Raised by command decoders for invalid user-supplied CLI values.

    The shell translates this exception into argparse's standard usage error
    path so callers receive exit code ``2`` and diagnostics on stderr.
    """


def validate_command_name(value: str) -> None:
    """Validate a feature-owned command name against shell naming rules."""
    validate_command_text("name", value)
    if COMMAND_NAME_PATTERN.fullmatch(value) is None:
        msg = "CLI command registration name must be lowercase kebab-case"
        raise RegistrationError(msg)


def validate_command_text(field_name: str, value: str) -> None:
    """Validate that command registration text is present and trimmed."""
    if not value or value.strip() != value:
        msg = f"CLI command registration {field_name} must be a non-empty trimmed value"
        raise RegistrationError(msg)


def validate_command_callable(name: str, value: object) -> None:
    """Validate that one command lifecycle hook is callable."""
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
