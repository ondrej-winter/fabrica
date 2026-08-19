"""Argparse parser construction for the product CLI shell."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Never, Protocol, TextIO

from fabrica.adapters.inbound.cli.command import CommandRegistrar, RegistrationError
from fabrica.adapters.inbound.cli.destinations import COMMAND_DEST
from fabrica.adapters.inbound.cli.options import add_global_options
from fabrica.adapters.inbound.cli.registry import ArgparseCommandRegistry

if TYPE_CHECKING:
    from collections.abc import Sequence


class TextWriter(Protocol):
    """Minimal stream protocol accepted by argparse help writers."""

    def write(self, value: str, /) -> object:
        """Write text and return the stream-specific result."""
        ...


class StreamArgumentParser(argparse.ArgumentParser):
    """Argument parser that writes help and usage errors to explicit streams.

    ``argparse`` defaults to process-global ``sys.stdout`` and ``sys.stderr``.
    This subclass lets bootstrap and tests inject streams while preserving
    argparse's normal help, usage, and exit behavior.
    """

    stdout: TextIO = sys.stdout
    stderr: TextIO = sys.stderr

    def bind_streams(self, *, stdout: TextIO | None, stderr: TextIO | None) -> None:
        """Bind parser diagnostics to explicit streams or process defaults."""
        self.stdout = stdout if stdout is not None else sys.stdout
        self.stderr = stderr if stderr is not None else sys.stderr

    def print_help(self, file: TextWriter | None = None) -> None:
        """Print help to the bound stdout when no file is supplied."""
        super().print_help(file or getattr(self, "stdout", sys.stdout))

    def print_usage(self, file: TextWriter | None = None) -> None:
        """Print usage to the bound stdout when no file is supplied."""
        super().print_usage(file or getattr(self, "stdout", sys.stdout))

    def error(self, message: str) -> Never:
        """Print argparse usage errors to the bound stderr."""
        self.print_usage(self.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")

    def exit(self, status: int = 0, message: str | None = None) -> Never:
        """Raise ``SystemExit`` after routing exit messages to bound stderr."""
        if message:
            getattr(self, "stderr", sys.stderr).write(message)
        raise SystemExit(status)


def stream_parser_class(*, stdout: TextIO | None, stderr: TextIO | None) -> type[StreamArgumentParser]:
    """Create a stream-bound parser class for argparse subcommands."""
    bound_stdout = stdout if stdout is not None else sys.stdout
    bound_stderr = stderr if stderr is not None else sys.stderr

    class StreamSubparser(StreamArgumentParser):
        stdout = bound_stdout
        stderr = bound_stderr

    return StreamSubparser


def build_parser(
    command_registrars: Sequence[CommandRegistrar],
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> tuple[argparse.ArgumentParser, ArgparseCommandRegistry]:
    """Build the product CLI parser and register feature-owned commands.

    Args:
        command_registrars: Feature-owned callbacks that add subcommands.
        stdout: Optional stream for help output.
        stderr: Optional stream for usage and registration diagnostics.

    Returns:
        The root parser and the registry containing command definitions.

    Raises:
        RegistrationError: If argparse rejects contributed arguments while
            building a subcommand parser.

    """
    parser = StreamArgumentParser(
        prog="fabrica",
        description="Run local Fabrica workflows.",
    )
    parser.bind_streams(stdout=stdout, stderr=stderr)
    add_global_options(parser)
    subparsers = parser.add_subparsers(
        dest=COMMAND_DEST,
        required=True,
        parser_class=stream_parser_class(stdout=stdout, stderr=stderr),
    )
    command_registry = ArgparseCommandRegistry(subparsers.add_parser)
    for register_commands in command_registrars:
        try:
            register_commands(command_registry)
        except argparse.ArgumentError as err:
            msg = f"CLI command registration failed: {err}"
            raise RegistrationError(msg) from err

    return parser, command_registry
