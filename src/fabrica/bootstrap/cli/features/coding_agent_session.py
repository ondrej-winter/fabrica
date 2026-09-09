"""Bootstrap-owned handler for the interactive coding-agent session command."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from fabrica.bootstrap.composition.coding_agent_session import create_terminal_workspace_coding_agent_session_runtime
from fabrica.features.coding_agent_session.adapters.inbound.cli.contracts import CodingAgentSessionCliStreams
from fabrica.features.coding_agent_session.adapters.inbound.cli.runner import run_coding_agent_session_cli_command

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli import CommandContext
    from fabrica.features.coding_agent_session.adapters.inbound.cli.command_models import (
        CliCodingAgentSessionCommand,
        CodingAgentSessionCliCompositionOptions,
    )
    from fabrica.features.coding_agent_session.adapters.inbound.cli.registration import CodingAgentSessionCliHandler
    from fabrica.features.coding_agent_session.application.ports import CodingAgentSessionRuntime


def run_coding_agent_session_command(
    runtime_override: CodingAgentSessionRuntime | None,
) -> CodingAgentSessionCliHandler:
    """Create the public CLI handler for a workspace-scoped coding-agent session."""

    def run(
        command: CliCodingAgentSessionCommand,
        composition_options: CodingAgentSessionCliCompositionOptions,
        context: CommandContext,
    ) -> int:
        return run_coding_agent_session_cli_command(
            command,
            streams=CodingAgentSessionCliStreams(stdout=context.stdout, stderr=context.stderr),
            runtime=runtime_override
            or _create_default_runtime(
                workspace_root=command.workspace_root,
                stdin=context.stdin,
                stdout=context.stdout,
                skill_roots=composition_options.skill_roots,
            ),
        )

    return run


def _create_default_runtime(
    *,
    workspace_root: Path,
    stdin: TextIO,
    stdout: TextIO,
    skill_roots: tuple[Path, ...],
) -> CodingAgentSessionRuntime:
    """Create the default terminal session runtime after CLI validation."""
    return asyncio.run(
        create_terminal_workspace_coding_agent_session_runtime(
            workspace_root=workspace_root,
            stdin=stdin,
            stdout=stdout,
            skill_roots=skill_roots,
        )
    )


__all__ = ["run_coding_agent_session_command"]
