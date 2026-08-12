"""Product CLI command runner."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

from fabrica.adapters.inbound.cli.contributions import (
    CliExecutionContext,
    validate_cli_contributions,
)
from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.parser import (
    CliCommand,
    CliInvocation,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fabrica.adapters.inbound.cli.contributions import CliContribution


@dataclass(frozen=True, slots=True)
class CliCommandExecutionOptions:
    """Runtime options supplied by the product CLI shell."""

    contributions: Sequence[CliContribution]
    stdin: TextIO | None = None
    stdout: TextIO | None = None
    stderr: TextIO | None = None


def run_cli_command(
    invocation: CliCommand | CliInvocation,
    *,
    options: CliCommandExecutionOptions,
) -> int:
    """Run one parsed CLI command and return a process exit code."""
    validate_cli_contributions(options.contributions)
    command, global_options = _normalize_invocation(invocation)
    context = CliExecutionContext(
        global_options=global_options,
        stdin=options.stdin or sys.stdin,
        stdout=options.stdout or sys.stdout,
        stderr=options.stderr or sys.stderr,
    )
    for contribution in options.contributions:
        if contribution.can_handle(command):
            return contribution.run_command(command, context)

    msg = f"no CLI contribution registered for command: {type(command).__name__}"
    raise RuntimeError(msg)


def _normalize_invocation(invocation: CliCommand | CliInvocation) -> tuple[CliCommand, CliGlobalOptions]:
    if isinstance(invocation, CliInvocation):
        return invocation.command, invocation.global_options
    return invocation, CliGlobalOptions()
