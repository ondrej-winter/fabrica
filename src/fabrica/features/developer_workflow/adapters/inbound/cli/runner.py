"""Execution helpers for developer-workflow CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

from fabrica.adapters.inbound.cli.output import write_run_result
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.options import CliGlobalOptions
    from fabrica.bootstrap import ConfirmedCommitWorkflowResult
    from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
        CommitMessageWorkflowRunner,
        ConfirmedCommitWorkflowRunner,
        DeveloperWorkflowCliDependencies,
        DeveloperWorkflowCliStreams,
        EvidenceWriter,
    )


def run_developer_workflow_cli_command(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
    dependencies: DeveloperWorkflowCliDependencies,
    streams: DeveloperWorkflowCliStreams,
    evidence_writer: EvidenceWriter,
) -> int:
    """Run one developer-workflow owned CLI command."""
    if isinstance(command, CliCommitMessageCommand):
        workflow = dependencies.commit_message_workflow or _create_default_commit_message_workflow(
            command, global_options=global_options
        )
        result = workflow.run(command)
        return _write_runtime_result(
            result,
            global_options=global_options,
            stdout=streams.stdout,
            stderr=streams.stderr,
            evidence_writer=evidence_writer,
        )
    workflow = dependencies.confirmed_commit_workflow or _create_default_confirmed_commit_workflow(
        command, global_options=global_options
    )
    generation_result = workflow.generate(command)
    if not generation_result.succeeded or generation_result.recommendation is None:
        return _write_confirmed_commit_result(
            generation_result,
            global_options=global_options,
            streams=streams,
            evidence_writer=evidence_writer,
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
            stdout=streams.stdout,
            stderr=streams.stderr,
            evidence_writer=evidence_writer,
        )

    if answer.strip().casefold() not in {"y", "yes"}:
        streams.stdout.write("Commit cancelled; no commit created.\n")
        evidence_writer(generation_result, global_options=global_options, stdout=streams.stdout)
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
        evidence_writer=evidence_writer,
    )


def _write_runtime_result(
    result: LocalAgentRunResult,
    *,
    global_options: CliGlobalOptions,
    stdout: TextIO,
    stderr: TextIO,
    evidence_writer: EvidenceWriter,
) -> int:
    exit_code = write_run_result(result, stdout=stdout, stderr=stderr)
    if global_options.print_usage or global_options.print_prices:
        evidence_writer(result, global_options=global_options, stdout=stdout)
    return exit_code


def _write_confirmed_commit_result(
    result: ConfirmedCommitWorkflowResult,
    *,
    global_options: CliGlobalOptions,
    streams: DeveloperWorkflowCliStreams,
    evidence_writer: EvidenceWriter,
    output_already_written: bool = False,
) -> int:
    runtime_result = LocalAgentRunResult(
        status=result.status,
        output_text=None if output_already_written else result.output_text,
        observations=result.observations,
        usage_evidence=result.usage_evidence,
        cost_evidence=result.cost_evidence,
    )
    return _write_runtime_result(
        runtime_result,
        global_options=global_options,
        stdout=streams.stdout,
        stderr=streams.stderr,
        evidence_writer=evidence_writer,
    )


def _create_default_commit_message_workflow(
    command: CliCommitMessageCommand,
    *,
    global_options: CliGlobalOptions,
) -> CommitMessageWorkflowRunner:
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
    command: CliCommitCommand,
    *,
    global_options: CliGlobalOptions,
) -> ConfirmedCommitWorkflowRunner:
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
