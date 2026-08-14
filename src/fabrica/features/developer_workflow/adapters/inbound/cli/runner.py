"""Execution helpers for developer-workflow CLI commands."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from fabrica.features.developer_workflow.adapters.inbound.cli.output import (
    format_commit_message_recommendation,
    write_confirmed_commit_result,
    write_developer_workflow_result,
)
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageWorkflowResult,
    DeveloperWorkflowObservation,
    DeveloperWorkflowStatus,
    GenerateCommitMessageCommand,
)

if TYPE_CHECKING:
    from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
        CliCommitCommand,
        CliCommitMessageCommand,
    )
    from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
        DeveloperWorkflowCliOptions,
        DeveloperWorkflowCliStreams,
        EvidenceWriter,
    )
    from fabrica.features.developer_workflow.application.dtos import ConfirmedCommitWorkflowResult
    from fabrica.features.developer_workflow.application.ports import (
        CommitMessageWorkflowRunner,
        ConfirmedCommitWorkflowRunner,
    )


def run_commit_message_cli_command(
    command: CliCommitMessageCommand,
    *,
    options: DeveloperWorkflowCliOptions,
    streams: DeveloperWorkflowCliStreams,
    workflow: CommitMessageWorkflowRunner,
    evidence_writer: EvidenceWriter,
) -> int:
    """Run a read-only commit-message preview command."""
    result = workflow.run(_generate_commit_message_command(command))
    return _write_runtime_result(
        result,
        options=options,
        streams=streams,
        evidence_writer=evidence_writer,
    )


def run_confirmed_commit_cli_command(
    command: CliCommitCommand,
    *,
    options: DeveloperWorkflowCliOptions,
    streams: DeveloperWorkflowCliStreams,
    workflow: ConfirmedCommitWorkflowRunner,
    evidence_writer: EvidenceWriter,
) -> int:
    """Run an interactive confirmed commit command."""
    generation_result = workflow.generate(_generate_commit_message_command(command))
    if not generation_result.succeeded or generation_result.recommendation is None:
        return _write_confirmed_commit_result(
            generation_result,
            options=options,
            streams=streams,
            evidence_writer=evidence_writer,
        )

    confirmation = _prompt_for_commit_confirmation(generation_result, streams=streams)
    if confirmation is None:
        return _write_interrupted_confirmation_result(
            generation_result,
            options=options,
            streams=streams,
            evidence_writer=evidence_writer,
        )
    if not confirmation:
        return _write_cancelled_confirmation_result(
            generation_result,
            options=options,
            streams=streams,
            evidence_writer=evidence_writer,
        )

    commit_result = workflow.commit(generation_result.recommendation)
    if commit_result.succeeded and commit_result.commit_result is not None:
        if commit_result.commit_result.short_hash is not None:
            streams.stdout.write(f"Committed as {commit_result.commit_result.short_hash}.\n")
        else:
            streams.stdout.write("Committed.\n")
    return _write_confirmed_commit_result(
        commit_result,
        options=options,
        streams=streams,
        output_already_written=True,
        evidence_writer=evidence_writer,
    )


def _prompt_for_commit_confirmation(
    generation_result: ConfirmedCommitWorkflowResult,
    *,
    streams: DeveloperWorkflowCliStreams,
) -> bool | None:
    output_text = generation_result.output_text
    if output_text is None and generation_result.recommendation is not None:
        output_text = format_commit_message_recommendation(generation_result.recommendation)
    if output_text:
        streams.stdout.write(output_text)
        if not output_text.endswith("\n"):
            streams.stdout.write("\n")
    streams.stdout.write("Commit with this message? [y/N] ")
    streams.stdout.flush()

    try:
        answer = streams.stdin.readline()
    except KeyboardInterrupt:
        return None
    return answer.strip().casefold() in {"y", "yes"}


def _write_interrupted_confirmation_result(
    generation_result: ConfirmedCommitWorkflowResult,
    *,
    options: DeveloperWorkflowCliOptions,
    streams: DeveloperWorkflowCliStreams,
    evidence_writer: EvidenceWriter,
) -> int:
    interrupted_result = CommitMessageWorkflowResult(
        status=DeveloperWorkflowStatus.SAFETY_DENIED,
        observations=(
            DeveloperWorkflowObservation(
                message="commit confirmation interrupted",
                metadata={"category": "commit_confirmation_interrupted"},
            ),
        ),
        usage_evidence=generation_result.usage_evidence,
        cost_evidence=generation_result.cost_evidence,
    )
    return _write_runtime_result(
        interrupted_result,
        options=options,
        streams=streams,
        evidence_writer=evidence_writer,
    )


def _write_cancelled_confirmation_result(
    generation_result: ConfirmedCommitWorkflowResult,
    *,
    options: DeveloperWorkflowCliOptions,
    streams: DeveloperWorkflowCliStreams,
    evidence_writer: EvidenceWriter,
) -> int:
    streams.stdout.write("Commit cancelled; no commit created.\n")
    evidence_writer(
        generation_result,
        include_usage=options.print_usage,
        include_prices=options.print_prices,
        stdout=streams.stdout,
    )
    return 0


def _write_runtime_result(
    result: CommitMessageWorkflowResult,
    *,
    options: DeveloperWorkflowCliOptions,
    streams: DeveloperWorkflowCliStreams,
    evidence_writer: EvidenceWriter,
) -> int:
    exit_code = write_developer_workflow_result(result, stdout=streams.stdout, stderr=streams.stderr)
    if options.print_usage or options.print_prices:
        evidence_writer(
            result,
            include_usage=options.print_usage,
            include_prices=options.print_prices,
            stdout=streams.stdout,
        )
    return exit_code


def _write_confirmed_commit_result(
    result: ConfirmedCommitWorkflowResult,
    *,
    options: DeveloperWorkflowCliOptions,
    streams: DeveloperWorkflowCliStreams,
    evidence_writer: EvidenceWriter,
    output_already_written: bool = False,
) -> int:
    if output_already_written:
        result = replace(result, recommendation=None, output_text=None)
    exit_code = write_confirmed_commit_result(result, stdout=streams.stdout, stderr=streams.stderr)
    if options.print_usage or options.print_prices:
        evidence_writer(
            result,
            include_usage=options.print_usage,
            include_prices=options.print_prices,
            stdout=streams.stdout,
        )
    return exit_code


def _generate_commit_message_command(
    command: CliCommitMessageCommand | CliCommitCommand,
) -> GenerateCommitMessageCommand:
    return GenerateCommitMessageCommand(skill_id=command.skill_id)
