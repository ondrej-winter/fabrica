"""Runner for local agent runtime CLI commands."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.features.agent_runtime.adapters.inbound.cli.output import (
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.parser import (
    CliCommand,
    CliCommitMessageCommand,
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
    command: CliCommand,
    *,
    dependencies: CliCommandDependencies | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one parsed CLI command and return a process exit code."""
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    active_dependencies = dependencies or CliCommandDependencies()

    if isinstance(command, CliScriptPolicyCommand):
        return _run_script_policy_command(
            command,
            script_policy_evaluator=active_dependencies.script_policy_evaluator,
            stdout=output_stream,
            stderr=error_stream,
        )

    if isinstance(command, CliScriptExecuteCommand):
        return _run_script_execute_command(
            command,
            script_executor=active_dependencies.script_executor,
            stdout=output_stream,
            stderr=error_stream,
        )

    if isinstance(command, CliCommitMessageCommand):
        return _run_commit_message_command(
            command,
            commit_message_workflow=active_dependencies.commit_message_workflow,
            stdout=output_stream,
            stderr=error_stream,
        )

    runtime_command = LocalAgentRunCommand(prompt=command.prompt, model_hint=command.model_hint)
    if command.skill_ids or command.resources:
        runtime_command = _augment_command(
            runtime_command,
            command,
            command_augmenter=active_dependencies.command_augmenter,
        )

    active_runtime = active_dependencies.runtime or _create_default_runtime()
    result = active_runtime.run(runtime_command)
    return write_run_result(result, stdout=output_stream, stderr=error_stream)


def _run_script_policy_command(
    command: CliScriptPolicyCommand,
    *,
    script_policy_evaluator: ScriptPolicyEvaluator | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    evaluator = script_policy_evaluator or _create_default_script_policy_evaluator(command)
    result = evaluator.evaluate(SkillScriptPolicyEvaluationCommand(selection=selection))
    return write_script_policy_result(result, stdout=stdout, stderr=stderr)


def _run_script_execute_command(
    command: CliScriptExecuteCommand,
    *,
    script_executor: ScriptExecutor | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    selection = SelectedSkillScript(skill_id=command.skill_id, script_id=command.script_id)
    executor = script_executor or _create_default_script_executor(command)
    result = executor.execute(SkillScriptExecutionCommand(selection=selection))
    return write_script_execution_result(result, stdout=stdout, stderr=stderr)


def _run_commit_message_command(
    command: CliCommitMessageCommand,
    *,
    commit_message_workflow: CommitMessageWorkflowRunner | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    workflow = commit_message_workflow or _create_default_commit_message_workflow(command)
    result = workflow.run(command)
    return write_run_result(result, stdout=stdout, stderr=stderr)


def _augment_command(
    runtime_command: LocalAgentRunCommand,
    command: CliRunCommand,
    *,
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
        verbose_diagnostics=command.verbose_diagnostics,
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


def _create_default_commit_message_workflow(command: CliCommitMessageCommand) -> CommitMessageWorkflowRunner:
    from fabrica.bootstrap.local_agent_runtime import (  # noqa: PLC0415
        CommitMessageWorkflowOptions,
        create_codex_commit_message_workflow,
    )

    return create_codex_commit_message_workflow(
        CommitMessageWorkflowOptions(
            codex_model=command.model,
            codex_reasoning_effort=command.reasoning_effort,
            skill_roots=command.skill_roots,
            verbose_diagnostics=command.verbose_diagnostics,
        ),
    )


def _create_default_script_policy_evaluator(command: CliScriptPolicyCommand) -> ScriptPolicyEvaluator:
    from fabrica.bootstrap.local_agent_runtime import (  # noqa: PLC0415
        SkillScriptPolicyEvaluationOptions,
        create_skill_script_policy_evaluator,
    )

    return create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=command.skill_roots,
            verbose_diagnostics=command.verbose_diagnostics,
        ),
    )


def _create_default_script_executor(command: CliScriptExecuteCommand) -> ScriptExecutor:
    from fabrica.bootstrap.local_agent_runtime import (  # noqa: PLC0415
        SkillScriptExecutionOptions,
        create_skill_script_executor,
    )

    return create_skill_script_executor(
        SkillScriptExecutionOptions(
            skill_roots=command.skill_roots,
            verbose_diagnostics=command.verbose_diagnostics,
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
