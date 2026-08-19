"""Public entry point for the feature-neutral product CLI shell."""

from collections.abc import Sequence
from typing import TextIO

from fabrica.adapters.inbound.cli.command import CommandRegistrar
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
    """Parse and execute one product CLI invocation.

    Parser construction and command decoding happen inside the argparse exit
    conversion boundary, so help requests and usage errors return process-style
    exit codes instead of raising ``SystemExit``. Command runners execute after
    parsing has succeeded, which keeps runner-owned ``SystemExit`` and
    unexpected failures visible to the caller.

    Args:
        argv: Command-line arguments excluding the executable name.
        command_registrars: Feature-owned callbacks that register subcommands.
        stdin: Input stream passed to the selected command runner.
        stdout: Output stream for help text and command output.
        stderr: Error stream for usage diagnostics.

    Returns:
        The process exit code for help, usage failures, or the selected command.

    Raises:
        RegistrationError: If contributed command definitions are invalid.

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
