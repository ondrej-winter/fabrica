"""Bootstrap wiring for the agent-runtime product CLI contribution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contributions import CliContribution
from fabrica.bootstrap.composition import (
    SkillContextAugmentationOptions,
    SkillScriptExecutionOptions,
    SkillScriptPolicyEvaluationOptions,
    create_codex_runtime,
    create_skill_context_augmented_local_agent_command,
    create_skill_script_executor,
    create_skill_script_policy_evaluator,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliDependencies,
    AgentRuntimeCliStreams,
    AgentRuntimeCliWriters,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contribution import (
    AGENT_RUNTIME_CLI_COMMAND_TYPES,
    register_agent_runtime_cli_commands,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.output import (
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import run_agent_runtime_cli_command

if TYPE_CHECKING:
    from pathlib import Path

    from fabrica.adapters.inbound.cli.contributions import CliExecutionContext
    from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import EvidenceWriter
    from fabrica.features.agent_runtime.application.dtos import (
        LocalAgentRunCommand,
        SelectedSkill,
        SelectedSkillResource,
        SkillScriptApprovalBinding,
        SkillScriptApprovalDecision,
    )
    from fabrica.features.agent_runtime.application.ports import (
        LocalAgentRuntime,
        SkillScriptPolicyEvaluator,
        SkillScriptRunner,
    )


def create_agent_runtime_cli_contribution(
    *,
    dependencies: AgentRuntimeCliDependencies | None = None,
    evidence_writer: EvidenceWriter,
) -> CliContribution:
    """Create the agent-runtime CLI contribution with bootstrap-owned defaults."""
    return CliContribution(
        name="agent_runtime",
        command_types=AGENT_RUNTIME_CLI_COMMAND_TYPES,
        register_commands=register_agent_runtime_cli_commands,
        run_command=_run_agent_runtime_contribution(dependencies, evidence_writer=evidence_writer),
    )


def _run_agent_runtime_contribution(
    overrides: AgentRuntimeCliDependencies | None,
    *,
    evidence_writer: EvidenceWriter,
):
    def run(command: object, context: CliExecutionContext) -> int:
        if not isinstance(command, CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand):
            msg = f"agent-runtime CLI contribution cannot handle command: {type(command).__name__}"
            raise TypeError(msg)
        return run_agent_runtime_cli_command(
            command,
            global_options=context.global_options,
            dependencies=_agent_runtime_dependencies_for_command(command, context=context, overrides=overrides),
            streams=AgentRuntimeCliStreams(stdout=context.stdout, stderr=context.stderr),
            writers=AgentRuntimeCliWriters(
                run_result=write_run_result,
                evidence=evidence_writer,
                script_policy_result=write_script_policy_result,
                script_execution_result=write_script_execution_result,
            ),
        )

    return run


def _agent_runtime_dependencies_for_command(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    context: CliExecutionContext,
    overrides: AgentRuntimeCliDependencies | None,
) -> AgentRuntimeCliDependencies:
    dependencies = overrides or AgentRuntimeCliDependencies()
    return AgentRuntimeCliDependencies(
        runtime=dependencies.runtime or _create_default_runtime(),
        command_augmenter=dependencies.command_augmenter or _default_augment_command,
        script_policy_evaluator=dependencies.script_policy_evaluator
        or _create_default_script_policy_evaluator(command, context=context),
        script_executor=dependencies.script_executor or _create_default_script_executor(command, context=context),
    )


def _default_augment_command(
    command: LocalAgentRunCommand,
    skill_selections: tuple[SelectedSkill, ...],
    resource_selections: tuple[SelectedSkillResource, ...],
    *,
    skill_roots: tuple[Path, ...],
    verbose_diagnostics: bool,
) -> LocalAgentRunCommand:
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
    return create_codex_runtime()


def _create_default_script_policy_evaluator(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    context: CliExecutionContext,
) -> SkillScriptPolicyEvaluator | None:
    if not isinstance(command, CliScriptPolicyCommand):
        return None

    return create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=command.skill_roots,
            verbose_diagnostics=context.global_options.verbose_diagnostics,
        ),
    )


def _create_default_script_executor(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    context: CliExecutionContext,
) -> SkillScriptRunner | None:
    if not isinstance(command, CliScriptExecuteCommand):
        return None

    return create_skill_script_executor(
        SkillScriptExecutionOptions(
            skill_roots=command.skill_roots,
            verbose_diagnostics=context.global_options.verbose_diagnostics,
            approval_lookup=_MetadataBoundCliApprovalLookup(command),
        ),
    )


@dataclass(frozen=True, slots=True)
class _MetadataBoundCliApprovalLookup:
    """CLI approval lookup that approves only an exact supplied metadata binding."""

    command: CliScriptExecuteCommand

    def get_approval(self, binding: SkillScriptApprovalBinding) -> SkillScriptApprovalDecision:
        from fabrica.features.agent_runtime.application.dtos import (  # noqa: PLC0415
            SkillScriptApprovalBinding,
            SkillScriptApprovalDecision,
            SkillScriptApprovalStatus,
        )

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
