"""Execution helpers for agent-runtime CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
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
    from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
        AgentRuntimeCliCommandOptions,
        AgentRuntimeCliDependencies,
        AgentRuntimeCliStreams,
        AgentRuntimeCliWriters,
        CommandAugmenter,
        ScriptExecutor,
        ScriptPolicyEvaluator,
    )


def run_agent_runtime_cli_command(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    global_options: AgentRuntimeCliCommandOptions,
    dependencies: AgentRuntimeCliDependencies,
    streams: AgentRuntimeCliStreams,
    writers: AgentRuntimeCliWriters,
) -> int:
    """Run one agent-runtime owned CLI command."""
    if isinstance(command, CliScriptPolicyCommand):
        return _run_script_policy_command(
            command,
            script_policy_evaluator=dependencies.script_policy_evaluator,
            streams=streams,
            writers=writers,
        )
    if isinstance(command, CliScriptExecuteCommand):
        return _run_script_execute_command(
            command,
            script_executor=dependencies.script_executor,
            streams=streams,
            writers=writers,
        )
    runtime_command = LocalAgentRunCommand(prompt=command.prompt, model_hint=command.model_hint)
    if command.skill_ids or command.resources:
        runtime_command = _augment_command(
            runtime_command,
            command,
            global_options=global_options,
            command_augmenter=dependencies.command_augmenter,
        )
    active_runtime = _require_dependency(dependencies.runtime, dependency_name="runtime")
    result = active_runtime.run(runtime_command)
    return writers.run_result(result, stdout=streams.stdout, stderr=streams.stderr)


def _run_script_policy_command(
    command: CliScriptPolicyCommand,
    *,
    script_policy_evaluator: ScriptPolicyEvaluator | None,
    streams: AgentRuntimeCliStreams,
    writers: AgentRuntimeCliWriters,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    evaluator = _require_dependency(script_policy_evaluator, dependency_name="script_policy_evaluator")
    result = evaluator.evaluate(SkillScriptPolicyEvaluationCommand(selection=selection))
    return writers.script_policy_result(result, stdout=streams.stdout, stderr=streams.stderr)


def _run_script_execute_command(
    command: CliScriptExecuteCommand,
    *,
    script_executor: ScriptExecutor | None,
    streams: AgentRuntimeCliStreams,
    writers: AgentRuntimeCliWriters,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    executor = _require_dependency(script_executor, dependency_name="script_executor")
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))
    return writers.script_execution_result(result, stdout=streams.stdout, stderr=streams.stderr)


def _augment_command(
    runtime_command: LocalAgentRunCommand,
    command: CliRunCommand,
    *,
    global_options: AgentRuntimeCliCommandOptions,
    command_augmenter: CommandAugmenter | None,
) -> LocalAgentRunCommand:
    skill_selections = tuple(SelectedSkill(skill_id=skill_id) for skill_id in command.skill_ids)
    resource_selections = tuple(
        SelectedSkillResource(skill_id=resource.skill_id, resource_id=resource.resource_id)
        for resource in command.resources
    )
    augmenter = _require_dependency(command_augmenter, dependency_name="command_augmenter")
    return augmenter(
        runtime_command,
        skill_selections,
        resource_selections,
        skill_roots=command.skill_roots,
        verbose_diagnostics=global_options.verbose_diagnostics,
    )


def _require_dependency(dependency: object | None, *, dependency_name: str):
    if dependency is None:
        msg = f"agent-runtime CLI dependency is not configured: {dependency_name}"
        raise RuntimeError(msg)
    return dependency
