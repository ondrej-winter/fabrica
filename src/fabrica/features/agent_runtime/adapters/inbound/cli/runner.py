"""Execution helpers for agent-runtime CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.output import (
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
)
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
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptExecutionCommand,
    SkillScriptPolicyEvaluationCommand,
)

if TYPE_CHECKING:
    from pathlib import Path

    from fabrica.adapters.inbound.cli.options import CliGlobalOptions
    from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
        AgentRuntimeCliDependencies,
        AgentRuntimeCliStreams,
        CommandAugmenter,
        LocalAgentRuntime,
        ScriptExecutor,
        ScriptPolicyEvaluator,
    )


def run_agent_runtime_cli_command(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
    dependencies: AgentRuntimeCliDependencies,
    streams: AgentRuntimeCliStreams,
) -> int:
    """Run one agent-runtime owned CLI command."""
    if isinstance(command, CliScriptPolicyCommand):
        return _run_script_policy_command(
            command,
            global_options=global_options,
            script_policy_evaluator=dependencies.script_policy_evaluator,
            streams=streams,
        )
    if isinstance(command, CliScriptExecuteCommand):
        return _run_script_execute_command(
            command,
            global_options=global_options,
            script_executor=dependencies.script_executor,
            streams=streams,
        )
    runtime_command = LocalAgentRunCommand(prompt=command.prompt, model_hint=command.model_hint)
    if command.skill_ids or command.resources:
        runtime_command = _augment_command(
            runtime_command,
            command,
            global_options=global_options,
            command_augmenter=dependencies.command_augmenter,
        )
    active_runtime = dependencies.runtime or _create_default_runtime()
    result = active_runtime.run(runtime_command)
    return write_run_result(result, stdout=streams.stdout, stderr=streams.stderr)


def _run_script_policy_command(
    command: CliScriptPolicyCommand,
    *,
    global_options: CliGlobalOptions,
    script_policy_evaluator: ScriptPolicyEvaluator | None,
    streams: AgentRuntimeCliStreams,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    evaluator = script_policy_evaluator or _create_default_script_policy_evaluator(
        command, global_options=global_options
    )
    result = evaluator.evaluate(SkillScriptPolicyEvaluationCommand(selection=selection))
    return write_script_policy_result(result, stdout=streams.stdout, stderr=streams.stderr)


def _run_script_execute_command(
    command: CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
    script_executor: ScriptExecutor | None,
    streams: AgentRuntimeCliStreams,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    executor = script_executor or _create_default_script_executor(command, global_options=global_options)
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))
    return write_script_execution_result(result, stdout=streams.stdout, stderr=streams.stderr)


def _augment_command(
    runtime_command: LocalAgentRunCommand,
    command: CliRunCommand,
    *,
    global_options: CliGlobalOptions,
    command_augmenter: CommandAugmenter | None,
) -> LocalAgentRunCommand:
    skill_selections = tuple(SelectedSkill(skill_id=skill_id) for skill_id in command.skill_ids)
    resource_selections = tuple(
        SelectedSkillResource(skill_id=resource.skill_id, resource_id=resource.resource_id)
        for resource in command.resources
    )
    augmenter = command_augmenter or _default_augment_command
    return augmenter(
        runtime_command,
        skill_selections,
        resource_selections,
        skill_roots=command.skill_roots,
        verbose_diagnostics=global_options.verbose_diagnostics,
    )


def _default_augment_command(
    command: LocalAgentRunCommand,
    skill_selections: tuple[SelectedSkill, ...],
    resource_selections: tuple[SelectedSkillResource, ...],
    *,
    skill_roots: tuple[Path, ...],
    verbose_diagnostics: bool,
) -> LocalAgentRunCommand:
    from fabrica.bootstrap import (  # noqa: PLC0415
        SkillContextAugmentationOptions,
        create_skill_context_augmented_local_agent_command,
    )

    return create_skill_context_augmented_local_agent_command(
        command,
        SkillContextAugmentationOptions(
            skill_selections=skill_selections,
            resource_selections=resource_selections,
            skill_roots=skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
    )


def _create_default_runtime() -> LocalAgentRuntime:
    from fabrica.bootstrap import create_codex_runtime  # noqa: PLC0415

    return create_codex_runtime()


def _create_default_script_policy_evaluator(
    command: CliScriptPolicyCommand,
    *,
    global_options: CliGlobalOptions,
) -> ScriptPolicyEvaluator:
    from fabrica.bootstrap import (  # noqa: PLC0415
        SkillScriptPolicyEvaluationOptions,
        create_skill_script_policy_evaluator,
    )

    return create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=command.skill_roots,
            verbose_diagnostics=global_options.verbose_diagnostics,
        ),
    )


def _create_default_script_executor(
    command: CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
) -> ScriptExecutor:
    from fabrica.bootstrap import (  # noqa: PLC0415
        SkillScriptExecutionOptions,
        create_skill_script_executor,
    )

    return create_skill_script_executor(
        SkillScriptExecutionOptions(
            skill_roots=command.skill_roots,
            verbose_diagnostics=global_options.verbose_diagnostics,
            approval_lookup=_MetadataBoundCliApprovalLookup(command),
        ),
    )


@dataclass(frozen=True, slots=True)
class _MetadataBoundCliApprovalLookup:
    """CLI approval lookup that approves only an exact supplied metadata binding."""

    command: CliScriptExecuteCommand

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        expected = SkillScriptApprovalBinding(
            skill_id=self.command.skill_id,
            script_id=self.command.script_id,
            script_type=self.command.approval_script_type,
            suffix=self.command.approval_suffix,
            byte_size=self.command.approval_byte_size,
            content_digest=self.command.approval_content_digest,
        )
        if binding == expected:
            return SkillScriptApprovalDecision(status=SkillScriptApprovalStatus.APPROVED, binding=binding)
        return SkillScriptApprovalDecision(
            status=SkillScriptApprovalStatus.DENIED,
            binding=binding,
            reason="CLI approval metadata did not match selected script metadata",
        )
