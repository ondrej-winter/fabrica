"""Product CLI command runner."""

from __future__ import annotations

import sys
from typing import TextIO

from fabrica.adapters.inbound.cli.contributions import (
    CliCommandDependencies,
    CliExecutionContext,
)
from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.parser import (
    CliCommand,
    CliInvocation,
)
from fabrica.adapters.inbound.cli.registry import default_cli_contributions


def run_cli_command(
    invocation: CliCommand | CliInvocation,
    *,
    dependencies: CliCommandDependencies | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one parsed CLI command and return a process exit code."""
    command, global_options = _normalize_invocation(invocation)
    context = CliExecutionContext(
        global_options=global_options,
        dependencies=dependencies or CliCommandDependencies(),
        stdin=stdin or sys.stdin,
        stdout=stdout or sys.stdout,
        stderr=stderr or sys.stderr,
    )
    for contribution in default_cli_contributions():
        if contribution.can_handle(command):
            return contribution.run_command(command, context)

    msg = f"no CLI contribution registered for command: {type(command).__name__}"
    raise RuntimeError(msg)


def _normalize_invocation(invocation: CliCommand | CliInvocation) -> tuple[CliCommand, CliGlobalOptions]:
    if isinstance(invocation, CliInvocation):
        return invocation.command, invocation.global_options
    return invocation, CliGlobalOptions()
