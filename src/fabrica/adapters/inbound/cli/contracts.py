"""Public contracts shared by feature CLI registrations and the product CLI shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import argparse
    from typing import TextIO

_CLI_HANDLER_NAMESPACE_ATTRIBUTE = "cli_handler"


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


type CliCommandHandler = Callable[[argparse.Namespace, CliExecutionContext], int]


@dataclass(frozen=True, slots=True)
class CliInvocation:
    """Parsed CLI invocation ready to execute through a bound command handler."""

    namespace: argparse.Namespace
    global_options: CliGlobalOptions
    handler: CliCommandHandler

    def execute(self, *, stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
        """Run the selected CLI command with explicit process streams."""
        return self.handler(
            self.namespace,
            CliExecutionContext(
                global_options=self.global_options,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
            ),
        )


class CliHandlerBindingTarget(Protocol):
    """Parser behavior needed to bind a command handler during CLI registration."""

    def set_defaults(self, **kwargs: object) -> None:
        """Attach parser defaults used after argument parsing."""


def bind_cli_handler(parser: CliHandlerBindingTarget, handler: CliCommandHandler) -> None:
    """Bind a command handler to one CLI subcommand parser."""
    parser.set_defaults(**{_CLI_HANDLER_NAMESPACE_ATTRIBUTE: handler})


def cli_handler_from_namespace(namespace: argparse.Namespace) -> CliCommandHandler:
    """Return the command handler bound to a parsed subcommand namespace."""
    handler = getattr(namespace, _CLI_HANDLER_NAMESPACE_ATTRIBUTE, None)
    if not callable(handler):
        msg = "CLI command registration did not configure a handler for the selected command"
        raise CliConfigurationError(msg)
    return handler


type CliCommandRegistrar = Callable[[CliSubparsers], None]


class CliError(Exception):
    """Base class for expected product CLI boundary failures."""


class CliConfigurationError(CliError):
    """Raised when CLI registration or composition is invalid."""


__all__ = [
    "CliCommandHandler",
    "CliCommandRegistrar",
    "CliConfigurationError",
    "CliError",
    "CliExecutionContext",
    "CliGlobalOptions",
    "CliHandlerBindingTarget",
    "CliInvocation",
    "CliSubparsers",
    "bind_cli_handler",
    "cli_handler_from_namespace",
]
