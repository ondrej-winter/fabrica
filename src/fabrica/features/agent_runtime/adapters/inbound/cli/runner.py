"""Execution helpers for agent-runtime CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.features.agent_runtime.adapters.inbound.cli.output import (
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SelectedSkill,
    SelectedSkillResource,
    SelectedSkillScript,
    SkillScriptExecutionCommand,
    SkillScriptPolicyEvaluationCommand,
)

if TYPE_CHECKING:
    from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
        CliRunCommand,
        CliScriptExecuteCommand,
        CliScriptPolicyCommand,
    )
    from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
        AgentRuntimeCliOptions,
        AgentRuntimeCliStreams,
        EvidenceWriter,
    )
    from fabrica.features.agent_runtime.application.ports import (
        LocalAgentRuntime,
        SelectedContextLocalAgentRuntime,
        SkillScriptPolicyEvaluator,
        SkillScriptRunner,
    )


def run_local_agent_cli_command(
    command: CliRunCommand,
    *,
    options: AgentRuntimeCliOptions,
    streams: AgentRuntimeCliStreams,
    runtime: LocalAgentRuntime,
    evidence_writer: EvidenceWriter,
) -> int:
    """Run one local runtime prompt command without selected context."""
    runtime_command = LocalAgentRunCommand(prompt=command.prompt, model_hint=command.model_hint)
    result = runtime.run(runtime_command)
    exit_code = write_run_result(result, stdout=streams.stdout, stderr=streams.stderr)
    if options.print_usage or options.print_prices:
        evidence_writer(
            result,
            include_usage=options.print_usage,
            include_prices=options.print_prices,
            stdout=streams.stdout,
        )
    return exit_code


def run_selected_context_agent_cli_command(
    command: CliRunCommand,
    *,
    options: AgentRuntimeCliOptions,
    streams: AgentRuntimeCliStreams,
    runtime: SelectedContextLocalAgentRuntime,
    evidence_writer: EvidenceWriter,
) -> int:
    """Run one local runtime prompt command with explicitly selected context."""
    result = runtime.run(
        LocalAgentRunCommand(prompt=command.prompt, model_hint=command.model_hint),
        skill_selections=_skill_selections_from_command(command),
        resource_selections=_resource_selections_from_command(command),
    )
    exit_code = write_run_result(result, stdout=streams.stdout, stderr=streams.stderr)
    if options.print_usage or options.print_prices:
        evidence_writer(
            result,
            include_usage=options.print_usage,
            include_prices=options.print_prices,
            stdout=streams.stdout,
        )
    return exit_code


def run_script_policy_cli_command(
    command: CliScriptPolicyCommand,
    *,
    streams: AgentRuntimeCliStreams,
    evaluator: SkillScriptPolicyEvaluator,
) -> int:
    """Run one selected skill script policy command."""
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    result = evaluator.evaluate(SkillScriptPolicyEvaluationCommand(selection=selection))
    return write_script_policy_result(result, stdout=streams.stdout, stderr=streams.stderr)


def run_script_execute_cli_command(
    command: CliScriptExecuteCommand,
    *,
    streams: AgentRuntimeCliStreams,
    executor: SkillScriptRunner,
) -> int:
    """Run one metadata-approved selected skill script execution command."""
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))
    return write_script_execution_result(result, stdout=streams.stdout, stderr=streams.stderr)


def _skill_selections_from_command(command: CliRunCommand) -> tuple[SelectedSkill, ...]:
    return tuple(SelectedSkill(skill_id=skill_id) for skill_id in command.skill_ids)


def _resource_selections_from_command(command: CliRunCommand) -> tuple[SelectedSkillResource, ...]:
    return tuple(
        SelectedSkillResource(skill_id=resource.skill_id, resource_id=resource.resource_id)
        for resource in command.resources
    )
