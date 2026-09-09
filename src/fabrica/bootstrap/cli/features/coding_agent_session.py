"""Bootstrap-owned handler for the interactive coding-agent session command."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
        del composition_options
        if runtime_override is None:
            msg = "coding-agent session runtime is not configured"
            raise RuntimeError(msg)
        return run_coding_agent_session_cli_command(
            command,
            streams=CodingAgentSessionCliStreams(stdout=context.stdout, stderr=context.stderr),
            runtime=runtime_override,
        )

    return run


__all__ = ["run_coding_agent_session_command"]
