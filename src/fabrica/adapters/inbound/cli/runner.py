"""Runner for local agent runtime CLI commands."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.options import CliGlobalOptions
from fabrica.adapters.inbound.cli.output import (
    write_model_evidence_report,
)
from fabrica.adapters.inbound.cli.parser import (
    CliCommand,
    CliInvocation,
)
from fabrica.features.agent_runtime.adapters.inbound.cli import (
    AgentRuntimeCliDependencies,
    AgentRuntimeCliStreams,
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
    run_developer_workflow_cli_command,
)

if TYPE_CHECKING:
    from fabrica.features.agent_runtime.application.dtos import ModelCostEvidence, ModelUsageEvidence


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
    return run_agent_runtime_cli_command(
        command,
        global_options=global_options,
        dependencies=AgentRuntimeCliDependencies(
            runtime=dependencies.runtime,
            command_augmenter=dependencies.command_augmenter,
            script_policy_evaluator=dependencies.script_policy_evaluator,
            script_executor=dependencies.script_executor,
        ),
        streams=AgentRuntimeCliStreams(stdout=stdout, stderr=stderr),
    )


def _run_developer_workflow_command(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
    streams: _CliStreams,
    dependencies: CliCommandDependencies,
) -> int:
    return run_developer_workflow_cli_command(
        command,
        global_options=global_options,
        dependencies=DeveloperWorkflowCliDependencies(
            commit_message_workflow=dependencies.commit_message_workflow,
            confirmed_commit_workflow=dependencies.confirmed_commit_workflow,
        ),
        streams=DeveloperWorkflowCliStreams(
            stdin=streams.stdin,
            stdout=streams.stdout,
            stderr=streams.stderr,
        ),
        evidence_writer=_write_requested_model_evidence,
    )


def _write_requested_model_evidence(
    result: ModelEvidenceResult,
    *,
    global_options: CliGlobalOptions,
    stdout: TextIO,
) -> None:
    write_model_evidence_report(
        usage_evidence=result.usage_evidence,
        cost_evidence=result.cost_evidence,
        stdout=stdout,
        include_usage=global_options.print_usage,
        include_prices=global_options.print_prices,
    )
