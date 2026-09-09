"""Execution helpers for coding-agent-session CLI commands."""

import asyncio

from fabrica.features.agent_runtime.application.dtos import SelectedSkill, SelectedSkillResource
from fabrica.features.coding_agent_session.adapters.inbound.cli.command_models import CliCodingAgentSessionCommand
from fabrica.features.coding_agent_session.adapters.inbound.cli.contracts import CodingAgentSessionCliStreams
from fabrica.features.coding_agent_session.adapters.inbound.cli.output import write_session_result
from fabrica.features.coding_agent_session.application.dtos import CodingAgentSessionCommand
from fabrica.features.coding_agent_session.application.ports import CodingAgentSessionRuntime
from fabrica.features.coding_agent_session.application.use_cases import RunCodingAgentSession


def run_coding_agent_session_cli_command(
    command: CliCodingAgentSessionCommand,
    *,
    streams: CodingAgentSessionCliStreams,
    runtime: CodingAgentSessionRuntime,
) -> int:
    """Run one validated workspace-scoped coding-agent session."""
    session_command = CodingAgentSessionCommand(
        workspace_root=command.workspace_root,
        prompt=command.prompt,
        selected_skills=tuple(SelectedSkill(skill_id=skill_id) for skill_id in command.skill_ids),
        selected_resources=tuple(
            SelectedSkillResource(skill_id=resource.skill_id, resource_id=resource.resource_id)
            for resource in command.resources
        ),
    )
    result = asyncio.run(RunCodingAgentSession(runtime).run(session_command))
    return write_session_result(result, stdout=streams.stdout, stderr=streams.stderr)
