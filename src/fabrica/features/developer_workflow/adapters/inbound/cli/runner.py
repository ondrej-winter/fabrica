"""Execution helpers for developer-workflow CLI commands."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.dtos import GenerateCommitMessageCommand

if TYPE_CHECKING:
    from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
        DeveloperWorkflowCliCommandOptions,
        DeveloperWorkflowCliDependencies,
        DeveloperWorkflowCliStreams,
        DeveloperWorkflowCliWriters,
    )
    from fabrica.features.developer_workflow.application.use_cases import ConfirmedCommitWorkflowResult


def run_developer_workflow_cli_command(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    global_options: DeveloperWorkflowCliCommandOptions,
    dependencies: DeveloperWorkflowCliDependencies,
    streams: DeveloperWorkflowCliStreams,
    writers: DeveloperWorkflowCliWriters,
) -> int:
    """Run one developer-workflow owned CLI command."""
    if isinstance(command, CliCommitMessageCommand):
        workflow = _require_dependency(
            dependencies.commit_message_workflow,
            dependency_name="commit_message_workflow",
        )
        result = workflow.run(_generate_commit_message_command(command))
        return _write_runtime_result(
            result,
            global_options=global_options,
            streams=streams,
            writers=writers,
        )
    workflow = _require_dependency(
        dependencies.confirmed_commit_workflow,
        dependency_name="confirmed_commit_workflow",
    )
    generation_result = workflow.generate(_generate_commit_message_command(command))
    if not generation_result.succeeded or generation_result.recommendation is None:
        return _write_confirmed_commit_result(
            generation_result,
            global_options=global_options,
            streams=streams,
            writers=writers,
        )

    if generation_result.output_text:
        streams.stdout.write(generation_result.output_text)
        if not generation_result.output_text.endswith("\n"):
            streams.stdout.write("\n")
    streams.stdout.write("Commit with this message? [y/N] ")
    streams.stdout.flush()

    try:
        answer = streams.stdin.readline()
    except KeyboardInterrupt:
        interrupted_result = LocalAgentRunResult(
            status=LocalAgentRunStatus.SAFETY_DENIED,
            observations=(
                RuntimeObservation(
                    message="commit confirmation interrupted",
                    metadata={"category": "commit_confirmation_interrupted"},
                ),
            ),
            usage_evidence=generation_result.usage_evidence,
            cost_evidence=generation_result.cost_evidence,
        )
        return _write_runtime_result(
            interrupted_result,
            global_options=global_options,
            streams=streams,
            writers=writers,
        )

    if answer.strip().casefold() not in {"y", "yes"}:
        streams.stdout.write("Commit cancelled; no commit created.\n")
        writers.evidence(generation_result, global_options=global_options, stdout=streams.stdout)
        return 0

    commit_result = workflow.commit(generation_result.recommendation)
    if commit_result.succeeded and commit_result.commit_result is not None:
        if commit_result.commit_result.short_hash is not None:
            streams.stdout.write(f"Committed as {commit_result.commit_result.short_hash}.\n")
        else:
            streams.stdout.write("Committed.\n")
    return _write_confirmed_commit_result(
        commit_result,
        global_options=global_options,
        streams=streams,
        output_already_written=True,
        writers=writers,
    )


def _write_runtime_result(
    result: LocalAgentRunResult,
    *,
    global_options: DeveloperWorkflowCliCommandOptions,
    streams: DeveloperWorkflowCliStreams,
    writers: DeveloperWorkflowCliWriters,
) -> int:
    exit_code = writers.runtime_result(result, stdout=streams.stdout, stderr=streams.stderr)
    if global_options.print_usage or global_options.print_prices:
        writers.evidence(result, global_options=global_options, stdout=streams.stdout)
    return exit_code


def _write_confirmed_commit_result(
    result: ConfirmedCommitWorkflowResult,
    *,
    global_options: DeveloperWorkflowCliCommandOptions,
    streams: DeveloperWorkflowCliStreams,
    writers: DeveloperWorkflowCliWriters,
    output_already_written: bool = False,
) -> int:
    if output_already_written:
        result = replace(result, output_text=None)
    exit_code = writers.confirmed_commit_result(result, stdout=streams.stdout, stderr=streams.stderr)
    if global_options.print_usage or global_options.print_prices:
        writers.evidence(result, global_options=global_options, stdout=streams.stdout)
    return exit_code


def _require_dependency(dependency: object | None, *, dependency_name: str):
    if dependency is None:
        msg = f"developer-workflow CLI dependency is not configured: {dependency_name}"
        raise RuntimeError(msg)
    return dependency


def _generate_commit_message_command(
    command: CliCommitMessageCommand | CliCommitCommand,
) -> GenerateCommitMessageCommand:
    return GenerateCommitMessageCommand(skill_id=command.skill_id)
