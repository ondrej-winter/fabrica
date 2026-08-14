"""Public contracts shared by feature CLI registrations and the product CLI shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import argparse
    from typing import TextIO


class CliCommandRegistry(Protocol):
    """Public behavior needed to register feature-owned CLI commands."""

    def register_command(
        self,
        registration: CliCommandRegistration,
    ) -> argparse.ArgumentParser:
        """Add one named subcommand parser and bind its execution handler."""


@dataclass(frozen=True, slots=True)
class CliCommandRegistration:
    """Feature-owned command registration for the product CLI shell."""

    name: str
    handler: CliCommandHandler
    summary: str
    description: str | None = None


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


type CliCommandHandler = Callable[[argparse.Namespace, CliExecutionContext], int]


class CliInvocation(Protocol):
    """Parsed CLI invocation ready to execute through a bound command handler."""

    def execute(self, *, stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
        """Run the selected CLI command with explicit process streams."""


type CliCommandRegistrar = Callable[[CliCommandRegistry], None]


class CliError(Exception):
    """Base class for expected product CLI boundary failures."""


class CliConfigurationError(CliError):
    """Raised when CLI registration or composition is invalid."""


__all__ = [
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliCommandRegistration",
    "CliCommandRegistry",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliInvocation",
]
