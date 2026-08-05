"""Runner for local agent runtime CLI commands."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.features.agent_runtime.adapters.inbound.cli.output import (
    write_model_evidence_report,
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.parser import (
    CliCommand,
    CliCommitMessageCommand,
    CliGlobalOptions,
    CliInvocation,
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    SelectedSkill,
    SelectedSkillResource,
    SelectedSkillScript,
    SkillScriptApprovalBinding,
    SkillScriptApprovalDecision,
    SkillScriptApprovalStatus,
    SkillScriptExecutionCommand,
    SkillScriptExecutionResult,
    SkillScriptPolicyEvaluationCommand,
    SkillScriptPolicyEvaluationResult,
)

if TYPE_CHECKING:
    from pathlib import Path


class LocalAgentRuntime(Protocol):
    """Protocol for the runtime use case consumed by the CLI adapter."""

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command."""


class CommandAugmenter(Protocol):
    """Protocol for selected skill/resource command augmentation."""

    def __call__(
        self,
        command: LocalAgentRunCommand,
        skill_selections: tuple[SelectedSkill, ...],
        resource_selections: tuple[SelectedSkillResource, ...],
        *,
        skill_roots: tuple[Path, ...],
        verbose_diagnostics: bool,
    ) -> LocalAgentRunCommand:
        """Return a command augmented with explicitly selected context."""


class CommitMessageWorkflowRunner(Protocol):
    """Protocol for commit-message workflow execution consumed by the CLI adapter."""

    def run(self, command: CliCommitMessageCommand) -> LocalAgentRunResult:
        """Run selected-skill commit-message generation."""


class ScriptPolicyEvaluator(Protocol):
    """Protocol for selected skill script policy evaluation consumed by the CLI adapter."""

    def evaluate(self, command: SkillScriptPolicyEvaluationCommand) -> SkillScriptPolicyEvaluationResult:
        """Evaluate selected script policy without executing the script."""


class ScriptExecutor(Protocol):
    """Protocol for selected skill script execution consumed by the CLI adapter."""

    def execute(self, command: SkillScriptExecutionCommand) -> SkillScriptExecutionResult:
        """Execute one selected skill script through policy-gated application boundaries."""


@dataclass(frozen=True, slots=True)
class CliCommandDependencies:
    """Injected CLI command dependencies for deterministic tests and composition."""

    runtime: LocalAgentRuntime | None = None
    command_augmenter: CommandAugmenter | None = None
    commit_message_workflow: CommitMessageWorkflowRunner | None = None
    script_policy_evaluator: ScriptPolicyEvaluator | None = None
    script_executor: ScriptExecutor | None = None


def run_cli_command(
    invocation: CliCommand | CliInvocation,
    *,
    dependencies: CliCommandDependencies | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one parsed CLI command and return a process exit code."""
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    active_dependencies = dependencies or CliCommandDependencies()
    command, global_options = _normalize_invocation(invocation)

    if isinstance(command, CliScriptPolicyCommand):
        return _run_script_policy_command(
            command,
            global_options=global_options,
            script_policy_evaluator=active_dependencies.script_policy_evaluator,
            stdout=output_stream,
            stderr=error_stream,
        )

    if isinstance(command, CliScriptExecuteCommand):
        return _run_script_execute_command(
            command,
            global_options=global_options,
            script_executor=active_dependencies.script_executor,
            stdout=output_stream,
            stderr=error_stream,
        )

    if isinstance(command, CliCommitMessageCommand):
        return _run_commit_message_command(
            command,
            global_options=global_options,
            commit_message_workflow=active_dependencies.commit_message_workflow,
            stdout=output_stream,
            stderr=error_stream,
        )

    runtime_command = LocalAgentRunCommand(prompt=command.prompt, model_hint=command.model_hint)
    if command.skill_ids or command.resources:
        runtime_command = _augment_command(
            runtime_command,
            command,
            global_options=global_options,
            command_augmenter=active_dependencies.command_augmenter,
        )

    active_runtime = active_dependencies.runtime or _create_default_runtime()
    result = active_runtime.run(runtime_command)
    return _write_runtime_result(result, global_options=global_options, stdout=output_stream, stderr=error_stream)


def _normalize_invocation(invocation: CliCommand | CliInvocation) -> tuple[CliCommand, CliGlobalOptions]:
    if isinstance(invocation, CliInvocation):
        return invocation.command, invocation.global_options
    return invocation, CliGlobalOptions()


def _run_script_policy_command(
    command: CliScriptPolicyCommand,
    *,
    global_options: CliGlobalOptions,
    script_policy_evaluator: ScriptPolicyEvaluator | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    evaluator = script_policy_evaluator or _create_default_script_policy_evaluator(
        command, global_options=global_options
    )
    result = evaluator.evaluate(SkillScriptPolicyEvaluationCommand(selection=selection))
    return write_script_policy_result(result, stdout=stdout, stderr=stderr)


def _run_script_execute_command(
    command: CliScriptExecuteCommand,
    *,
    global_options: CliGlobalOptions,
    script_executor: ScriptExecutor | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    executor = script_executor or _create_default_script_executor(command, global_options=global_options)
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))
    return write_script_execution_result(result, stdout=stdout, stderr=stderr)


def _run_commit_message_command(
    command: CliCommitMessageCommand,
    *,
    global_options: CliGlobalOptions,
    commit_message_workflow: CommitMessageWorkflowRunner | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    workflow = commit_message_workflow or _create_default_commit_message_workflow(
        command, global_options=global_options
    )
    result = workflow.run(command)
    return _write_runtime_result(result, global_options=global_options, stdout=stdout, stderr=stderr)


def _write_runtime_result(
    result: LocalAgentRunResult,
    *,
    global_options: CliGlobalOptions,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    exit_code = write_run_result(result, stdout=stdout, stderr=stderr)
    if global_options.print_usage or global_options.print_prices:
        write_model_evidence_report(
            usage_evidence=result.usage_evidence,
            cost_evidence=result.cost_evidence,
            stdout=stdout,
            include_usage=global_options.print_usage,
            include_prices=global_options.print_prices,
        )
    return exit_code


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
    from fabrica.bootstrap.local_agent_runtime import (  # noqa: PLC0415
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
    from fabrica.bootstrap.local_agent_runtime import create_codex_local_agent_runtime  # noqa: PLC0415

    return create_codex_local_agent_runtime()


def _create_default_commit_message_workflow(
    command: CliCommitMessageCommand,
    *,
    global_options: CliGlobalOptions,
) -> CommitMessageWorkflowRunner:
    from fabrica.bootstrap.local_agent_runtime import (  # noqa: PLC0415
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


def _create_default_script_policy_evaluator(
    command: CliScriptPolicyCommand,
    *,
    global_options: CliGlobalOptions,
) -> ScriptPolicyEvaluator:
    from fabrica.bootstrap.local_agent_runtime import (  # noqa: PLC0415
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
    from fabrica.bootstrap.local_agent_runtime import (  # noqa: PLC0415
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
