"""Runtime helpers for parsed product CLI invocations."""

from __future__ import annotations

import argparse
from collections.abc import Sequence  # noqa: TC003 - public annotations must resolve at runtime.
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

from fabrica.adapters.inbound.cli.command import (
    CommandContext,
    CommandRegistrar,
    GlobalOptions,
    RegistrationError,
    UsageError,
)
from fabrica.adapters.inbound.cli.destinations import COMMAND_DEST, RESERVED_DESTS
from fabrica.adapters.inbound.cli.options import global_options_from_namespace
from fabrica.adapters.inbound.cli.parser import build_parser

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class Invocation:
    """Parsed CLI invocation ready to execute.

    The invocation stores shell-level options, the feature command object
    produced by the selected decoder, and the matching runner. It is built only
    after argparse parsing and decoder validation have succeeded.
    """

    global_options: GlobalOptions
    command: object
    run: Callable[[object, CommandContext], int]

    def execute(self, *, stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
        """Run the selected CLI command with explicit process streams."""
        return self.run(
            self.command,
            CommandContext(
                global_options=self.global_options,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
            ),
        )


def parse_invocation(
    argv: Sequence[str],
    *,
    command_registrars: Sequence[CommandRegistrar],
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> Invocation:
    """Parse command-line arguments into an executable invocation.

    Global shell fields remain available for ``GlobalOptions`` extraction, but
    they are removed before the selected feature decoder receives its namespace.
    """
    parser, command_registry = build_parser(command_registrars, stdout=stdout, stderr=stderr)
    namespace = parser.parse_args(argv)
    command_name = command_name_from_namespace(namespace)
    global_options = global_options_from_namespace(namespace)
    feature_namespace = feature_namespace_from(namespace)
    registration = command_registry.registration_for(command_name)
    return Invocation(
        global_options=global_options,
        command=decode_command(parser, registration.decode, feature_namespace),
        run=registration.run,
    )


def command_name_from_namespace(namespace: argparse.Namespace) -> str:
    """Return the selected command name from a parsed argparse namespace."""
    command_name = getattr(namespace, COMMAND_DEST, None)
    if not isinstance(command_name, str) or not command_name:
        msg = "CLI parser did not capture the selected command name"
        raise RegistrationError(msg)
    return command_name


def decode_command(
    parser: argparse.ArgumentParser,
    decoder: Callable[[argparse.Namespace], object],
    feature_namespace: argparse.Namespace,
) -> object:
    """Decode feature command arguments while translating user errors.

    Feature decoders raise ``UsageError`` or ``argparse.ArgumentTypeError`` for
    invalid user input. The shell maps those failures back into argparse's
    standard usage path and intentionally lets other exceptions propagate as
    programmer errors.
    """
    try:
        return decoder(feature_namespace)
    except argparse.ArgumentTypeError as err:
        parser.error(str(err))
    except UsageError as err:
        parser.error(str(err))


def feature_namespace_from(namespace: argparse.Namespace) -> argparse.Namespace:
    """Remove shell-owned fields before feature command decoding."""
    values = vars(namespace).copy()
    for reserved_dest in RESERVED_DESTS:
        values.pop(reserved_dest, None)
    return argparse.Namespace(**values)
