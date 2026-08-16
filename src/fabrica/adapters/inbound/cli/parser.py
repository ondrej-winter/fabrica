"""Argparse parser construction for the product CLI adapter."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any, Never, TextIO

from fabrica.adapters.inbound.cli.command import CommandRegistrar, RegistrationError
from fabrica.adapters.inbound.cli.destinations import COMMAND_DEST
from fabrica.adapters.inbound.cli.options import add_global_options
from fabrica.adapters.inbound.cli.registry import ArgparseCommandRegistry

if TYPE_CHECKING:
    from collections.abc import Sequence


class StreamArgumentParser(argparse.ArgumentParser):
    """Argument parser that writes help and usage errors to explicit streams."""

    def bind_streams(self, *, stdout: TextIO | None, stderr: TextIO | None) -> None:
        """Bind parser diagnostics to explicit streams."""
        self.stdout = stdout if stdout is not None else sys.stdout
        self.stderr = stderr if stderr is not None else sys.stderr

    def print_help(self, file: Any = None) -> None:
        """Print help to explicit stdout by default."""
        super().print_help(file or getattr(self, "stdout", sys.stdout))

    def print_usage(self, file: Any = None) -> None:
        """Print usage to explicit stdout by default."""
        super().print_usage(file or getattr(self, "stdout", sys.stdout))

    def error(self, message: str) -> Never:
        """Print argparse usage errors to explicit stderr."""
        self.print_usage(self.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")

    def exit(self, status: int = 0, message: str | None = None) -> Never:
        """Exit after routing parser messages to explicit stderr."""
        if message:
            getattr(self, "stderr", sys.stderr).write(message)
        raise SystemExit(status)


def stream_parser_class(*, stdout: TextIO | None, stderr: TextIO | None) -> type[StreamArgumentParser]:
    """Create a stream-bound subparser class for argparse."""

    class StreamSubparser(StreamArgumentParser):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.bind_streams(stdout=stdout, stderr=stderr)

    return StreamSubparser


def build_parser(
    command_registrars: Sequence[CommandRegistrar],
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> tuple[argparse.ArgumentParser, ArgparseCommandRegistry]:
    """Build the product CLI parser and register feature-owned commands."""
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
    command_registry = ArgparseCommandRegistry(subparsers)
    for register_commands in command_registrars:
        try:
            register_commands(command_registry)
        except argparse.ArgumentError as err:
            msg = f"CLI command registration failed: {err}"
            raise RegistrationError(msg) from err

    return parser, command_registry
