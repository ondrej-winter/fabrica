"""Public entry point for the product CLI adapter."""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003 - public annotations must resolve at runtime.
from typing import TextIO

from fabrica.adapters.inbound.cli.command import (
    CommandRegistrar,  # noqa: TC001 - public annotations must resolve at runtime.
)
from fabrica.adapters.inbound.cli.runtime import parse_invocation

__all__ = ["run_cli"]


def run_cli(
    argv: Sequence[str],
    *,
    command_registrars: Sequence[CommandRegistrar],
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Parse and execute the product CLI with explicit process streams.

    Argparse help and usage exits are converted to process exit codes. Command
    runners execute outside that conversion boundary so runner-owned
    ``SystemExit`` and unexpected failures remain visible to the caller.
    """
    try:
        invocation = parse_invocation(
            argv,
            command_registrars=command_registrars,
            stdout=stdout,
            stderr=stderr,
        )
    except SystemExit as err:
        return int(err.code or 0)
    return invocation.execute(stdin=stdin, stdout=stdout, stderr=stderr)
