"""Bootstrap-owned entrypoint for the Fabrica product CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TextIO

from fabrica.adapters.inbound.cli import RegistrationError
from fabrica.adapters.inbound.cli import run_cli as run_product_cli
from fabrica.adapters.inbound.cli.rendering import write_line
from fabrica.bootstrap.cli.registration import create_cli_command_registrars

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fabrica.bootstrap.cli.contracts import CliDependencyOverrides

CLI_CONFIGURATION_ERROR_EXIT_CODE = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Fabrica CLI through bootstrap-owned default composition."""
    return run_cli(argv)


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    overrides: CliDependencyOverrides | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the Fabrica CLI with optional dependency and stream overrides."""
    resolved_stdin = stdin if stdin is not None else sys.stdin
    resolved_stdout = stdout if stdout is not None else sys.stdout
    resolved_stderr = stderr if stderr is not None else sys.stderr
    try:
        return run_product_cli(
            tuple(argv) if argv is not None else tuple(sys.argv[1:]),
            command_registrars=create_cli_command_registrars(overrides=overrides),
            stdin=resolved_stdin,
            stdout=resolved_stdout,
            stderr=resolved_stderr,
        )
    except RegistrationError as err:
        write_line(resolved_stderr, f"error: {err}")
        return CLI_CONFIGURATION_ERROR_EXIT_CODE
