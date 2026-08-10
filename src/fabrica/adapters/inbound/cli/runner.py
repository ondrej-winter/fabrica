"""Runner for local agent runtime CLI commands."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.output import (
    write_model_evidence_report,
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
)
from fabrica.adapters.inbound.cli.parser import (
    CliCommand,
    CliInvocation,
)
from fabrica.features.agent_runtime.adapters.inbound.cli import (
    AgentRuntimeCliDependencies,
    AgentRuntimeCliStreams,
    AgentRuntimeCliWriters,
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
    CommandAugmenter,
    LocalAgentRuntime,
    ScriptExecutor,
    ScriptPolicyEvaluator,
    run_agent_runtime_cli_command,
)
from fabrica.features.developer_workflow.adapters.inbound.cli import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CommitMessageWorkflowRunner,
    ConfirmedCommitWorkflowRunner,
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliStreams,
    DeveloperWorkflowCliWriters,
    run_developer_workflow_cli_command,
)

if TYPE_CHECKING:
    from pathlib import Path

    from fabrica.features.agent_runtime.application.dtos import (
        LocalAgentRunCommand,
        ModelCostEvidence,
        ModelUsageEvidence,
        SelectedSkill,
        SelectedSkillResource,
        SkillScriptApprovalBinding,
        SkillScriptApprovalDecision,
    )
    from fabrica.features.developer_workflow.adapters.inbound.cli import DeveloperWorkflowCliCommandOptions


class ModelEvidenceResult(Protocol):
    """Result shape that can expose model evidence to the product CLI."""

    @property
    def usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        """Return usage evidence emitted by the command."""

    @property
    def cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
        """Return cost evidence emitted by the command."""


@dataclass(frozen=True, slots=True)
class _CliStreams:
    """Normalized CLI input/output streams for command helpers."""

    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


@dataclass(frozen=True, slots=True)
class CliCommandDependencies:
    """Injected CLI command dependencies for deterministic tests and composition."""

    runtime: LocalAgentRuntime | None = None
    command_augmenter: CommandAugmenter | None = None
    commit_message_workflow: CommitMessageWorkflowRunner | None = None
    confirmed_commit_workflow: ConfirmedCommitWorkflowRunner | None = None
    script_policy_evaluator: ScriptPolicyEvaluator | None = None
    script_executor: ScriptExecutor | None = None


def run_cli_command(
    invocation: CliCommand | CliInvocation,
    *,
    dependencies: CliCommandDependencies | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one parsed CLI command and return a process exit code."""
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    active_dependencies = dependencies or CliCommandDependencies()
    command, global_options = _normalize_invocation(invocation)

    if isinstance(command, CliScriptPolicyCommand):
        return _run_agent_runtime_command(
            command=command,
            global_options=global_options,
            stdout=output_stream,
            stderr=error_stream,
            dependencies=active_dependencies,
        )

    if isinstance(command, CliScriptExecuteCommand):
        return _run_agent_runtime_command(
            command=command,
            global_options=global_options,
            stdout=output_stream,
            stderr=error_stream,
            dependencies=active_dependencies,
        )

    if isinstance(command, CliCommitMessageCommand):
        return _run_developer_workflow_command(
            command=command,
            global_options=global_options,
            streams=_CliStreams(stdin=input_stream, stdout=output_stream, stderr=error_stream),
            dependencies=active_dependencies,
        )

    if isinstance(command, CliCommitCommand):
        return _run_developer_workflow_command(
            command=command,
            global_options=global_options,
            streams=_CliStreams(stdin=input_stream, stdout=output_stream, stderr=error_stream),
            dependencies=active_dependencies,
        )

    return _run_agent_runtime_command(
        command=command,
        global_options=global_options,
        stdout=output_stream,
        stderr=error_stream,
        dependencies=active_dependencies,
    )


def _normalize_invocation(invocation: CliCommand | CliInvocation) -> tuple[CliCommand, CliGlobalOptions]:
    if isinstance(invocation, CliInvocation):
        return invocation.command, invocation.global_options
    return invocation, CliGlobalOptions()


def _run_agent_runtime_command(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
    stdout: TextIO,
    stderr: TextIO,
    dependencies: CliCommandDependencies,
) -> int:
    agent_runtime_dependencies = _agent_runtime_dependencies_for_command(
        command,
        global_options=global_options,
        dependencies=dependencies,
    )
    return run_agent_runtime_cli_command(
        command,
        global_options=global_options,
        dependencies=agent_runtime_dependencies,
        streams=AgentRuntimeCliStreams(stdout=stdout, stderr=stderr),
        writers=AgentRuntimeCliWriters(
            run_result=write_run_result,
            script_policy_result=write_script_policy_result,
            script_execution_result=write_script_execution_result,
        ),
    )


def _agent_runtime_dependencies_for_command(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
    dependencies: CliCommandDependencies,
) -> AgentRuntimeCliDependencies:
    return AgentRuntimeCliDependencies(
        runtime=dependencies.runtime or _create_default_runtime(),
        command_augmenter=dependencies.command_augmenter or _default_augment_command,
        script_policy_evaluator=dependencies.script_policy_evaluator
        or _create_default_script_policy_evaluator(command, global_options=global_options),
        script_executor=dependencies.script_executor
        or _create_default_script_executor(command, global_options=global_options),
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
    global_options: CliGlobalOptions,
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
            verbose_diagnostics=global_options.verbose_diagnostics,
        ),
    )


def _create_default_script_executor(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
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
            verbose_diagnostics=global_options.verbose_diagnostics,
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


def _run_developer_workflow_command(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
    streams: _CliStreams,
    dependencies: CliCommandDependencies,
) -> int:
    developer_workflow_dependencies = _developer_workflow_dependencies_for_command(
        command,
        global_options=global_options,
        dependencies=dependencies,
    )
    return run_developer_workflow_cli_command(
        command,
        global_options=global_options,
        dependencies=developer_workflow_dependencies,
        streams=DeveloperWorkflowCliStreams(
            stdin=streams.stdin,
            stdout=streams.stdout,
            stderr=streams.stderr,
        ),
        writers=DeveloperWorkflowCliWriters(
            evidence=_write_requested_model_evidence,
            runtime_result=write_run_result,
        ),
    )


def _developer_workflow_dependencies_for_command(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
    dependencies: CliCommandDependencies,
) -> DeveloperWorkflowCliDependencies:
    return DeveloperWorkflowCliDependencies(
        commit_message_workflow=dependencies.commit_message_workflow
        or _create_default_commit_message_workflow(command, global_options=global_options),
        confirmed_commit_workflow=dependencies.confirmed_commit_workflow
        or _create_default_confirmed_commit_workflow(command, global_options=global_options),
    )


def _create_default_commit_message_workflow(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
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
            verbose_diagnostics=global_options.verbose_diagnostics,
        ),
    )


def _create_default_confirmed_commit_workflow(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
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
            verbose_diagnostics=global_options.verbose_diagnostics,
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
