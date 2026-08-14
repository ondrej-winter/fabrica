"""Product CLI command runner."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

from fabrica.adapters.inbound.cli.contracts import CliDispatchError
from fabrica.adapters.inbound.cli.contributions import CliExecutionContext

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fabrica.adapters.inbound.cli.contributions import CliContribution
    from fabrica.adapters.inbound.cli.parser import CliInvocation


@dataclass(frozen=True, slots=True)
class CliCommandExecutionOptions:
    """Runtime options supplied by the product CLI shell."""

    contributions: Sequence[CliContribution]
    stdin: TextIO | None = None
    stdout: TextIO | None = None
    stderr: TextIO | None = None


def run_cli_command(
    invocation: CliInvocation,
    *,
    options: CliCommandExecutionOptions,
) -> int:
    """Run one parsed CLI command and return a process exit code."""
    context = CliExecutionContext(
        global_options=invocation.global_options,
        composition_options=invocation.composition_options,
        stdin=options.stdin or sys.stdin,
        stdout=options.stdout or sys.stdout,
        stderr=options.stderr or sys.stderr,
    )
    for contribution in options.contributions:
        if contribution.can_handle(invocation.command):
            return contribution.run_command(invocation.command, context)

    msg = f"no CLI contribution registered for command: {type(invocation.command).__name__}"
    raise CliDispatchError(msg)
