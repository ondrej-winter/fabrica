"""Public contracts shared by feature CLI registrations and the product CLI shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import argparse
    from typing import TextIO

CLI_HANDLER_NAMESPACE_ATTRIBUTE = "cli_handler"


class CliSubparsers(Protocol):
    """Public behavior needed to register feature-owned CLI commands."""

    def add_parser(self, name: str, **kwargs: object) -> argparse.ArgumentParser:
        """Add one named subcommand parser to the product CLI."""


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


class CliCommandHandler(Protocol):
    """Callable attached to a parsed argparse subcommand by feature registrations."""

    def __call__(self, namespace: argparse.Namespace, context: CliExecutionContext) -> int:
        """Run the selected command and return a process exit code."""


type CliCommandRegistrar = Callable[[CliSubparsers], None]


class CliError(Exception):
    """Base class for expected product CLI boundary failures."""


class CliConfigurationError(CliError):
    """Raised when CLI registration or composition is invalid."""


__all__ = [
    "CLI_HANDLER_NAMESPACE_ATTRIBUTE",
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliSubparsers",
]
