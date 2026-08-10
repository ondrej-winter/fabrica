"""Product CLI composition adapters for feature command contributions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.output import (
    write_model_evidence_report,
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
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
    LocalAgentRuntime,
    ScriptExecutor,
    ScriptPolicyEvaluator,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import run_agent_runtime_cli_command
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    CommitMessageWorkflowRunner,
    ConfirmedCommitWorkflowRunner,
    DeveloperWorkflowCliCommandOptions,
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliStreams,
    DeveloperWorkflowCliWriters,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import run_developer_workflow_cli_command

if TYPE_CHECKING:
    from pathlib import Path

    from fabrica.adapters.inbound.cli.contributions import CliExecutionContext
    from fabrica.features.agent_runtime.application.dtos import (
        LocalAgentRunCommand,
        ModelCostEvidence,
        ModelUsageEvidence,
        SelectedSkill,
        SelectedSkillResource,
        SkillScriptApprovalBinding,
        SkillScriptApprovalDecision,
    )


class ModelEvidenceResult(Protocol):
    """Result shape that can expose model evidence to the product CLI."""

    @property
    def usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        """Return usage evidence emitted by the command."""

    @property
    def cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
        """Return cost evidence emitted by the command."""


def run_agent_runtime_contribution_command(command: object, context: CliExecutionContext) -> int:
    """Run one agent-runtime CLI command through product-level defaults."""
    if not isinstance(command, CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand):
        msg = f"agent-runtime CLI contribution cannot handle command: {type(command).__name__}"
        raise TypeError(msg)
    return run_agent_runtime_cli_command(
        command,
        global_options=context.global_options,
        dependencies=_agent_runtime_dependencies_for_command(command, context=context),
        streams=AgentRuntimeCliStreams(stdout=context.stdout, stderr=context.stderr),
        writers=AgentRuntimeCliWriters(
            run_result=write_run_result,
            script_policy_result=write_script_policy_result,
            script_execution_result=write_script_execution_result,
        ),
    )


def _agent_runtime_dependencies_for_command(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    context: CliExecutionContext,
) -> AgentRuntimeCliDependencies:
    dependencies = context.dependencies
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
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    context: CliExecutionContext,
) -> ScriptPolicyEvaluator | None:
    if not isinstance(command, CliScriptPolicyCommand):
        return None

    from fabrica.bootstrap import (  # noqa: PLC0415
        SkillScriptPolicyEvaluationOptions,
        create_skill_script_policy_evaluator,
    )

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
) -> ScriptExecutor | None:
    if not isinstance(command, CliScriptExecuteCommand):
        return None

    from fabrica.bootstrap import (  # noqa: PLC0415
        SkillScriptExecutionOptions,
        create_skill_script_executor,
    )

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


def run_developer_workflow_contribution_command(command: object, context: CliExecutionContext) -> int:
    """Run one developer-workflow CLI command through product-level defaults."""
    if not isinstance(command, CliCommitMessageCommand | CliCommitCommand):
        msg = f"developer-workflow CLI contribution cannot handle command: {type(command).__name__}"
        raise TypeError(msg)
    return run_developer_workflow_cli_command(
        command,
        global_options=context.global_options,
        dependencies=_developer_workflow_dependencies_for_command(command, context=context),
        streams=DeveloperWorkflowCliStreams(
            stdin=context.stdin,
            stdout=context.stdout,
            stderr=context.stderr,
        ),
        writers=DeveloperWorkflowCliWriters(
            evidence=_write_requested_model_evidence,
            runtime_result=write_run_result,
        ),
    )


def _developer_workflow_dependencies_for_command(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    context: CliExecutionContext,
) -> DeveloperWorkflowCliDependencies:
    dependencies = context.dependencies
    return DeveloperWorkflowCliDependencies(
        commit_message_workflow=dependencies.commit_message_workflow
        or _create_default_commit_message_workflow(command, context=context),
        confirmed_commit_workflow=dependencies.confirmed_commit_workflow
        or _create_default_confirmed_commit_workflow(command, context=context),
    )


def _create_default_commit_message_workflow(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    context: CliExecutionContext,
) -> CommitMessageWorkflowRunner | None:
    if not isinstance(command, CliCommitMessageCommand):
        return None

    from fabrica.bootstrap import (  # noqa: PLC0415
        CommitMessageWorkflowOptions,
        create_codex_commit_message_workflow,
    )

    return create_codex_commit_message_workflow(
        CommitMessageWorkflowOptions(
            codex_model=command.model,
            codex_reasoning_effort=command.reasoning_effort,
            skill_roots=command.skill_roots,
            verbose_diagnostics=context.global_options.verbose_diagnostics,
        ),
    )


def _create_default_confirmed_commit_workflow(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    context: CliExecutionContext,
) -> ConfirmedCommitWorkflowRunner | None:
    if not isinstance(command, CliCommitCommand):
        return None

    from fabrica.bootstrap import (  # noqa: PLC0415
        CommitMessageWorkflowOptions,
        create_codex_confirmed_commit_workflow,
    )

    return create_codex_confirmed_commit_workflow(
        CommitMessageWorkflowOptions(
            codex_model=command.model,
            codex_reasoning_effort=command.reasoning_effort,
            skill_roots=command.skill_roots,
            verbose_diagnostics=context.global_options.verbose_diagnostics,
        ),
    )


def _write_requested_model_evidence(
    result: ModelEvidenceResult,
    *,
    global_options: DeveloperWorkflowCliCommandOptions,
    stdout: TextIO,
) -> None:
    write_model_evidence_report(
        usage_evidence=result.usage_evidence,
        cost_evidence=result.cost_evidence,
        stdout=stdout,
        include_usage=global_options.print_usage,
        include_prices=global_options.print_prices,
    )
