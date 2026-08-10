"""Product CLI composition for developer-workflow command contributions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.output import (
    write_confirmed_commit_result,
    write_model_evidence_report,
    write_run_result,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliCommandOptions,
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliStreams,
    DeveloperWorkflowCliWriters,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import run_developer_workflow_cli_command

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.contributions import CliExecutionContext
    from fabrica.features.agent_runtime.application.dtos import (
        ModelCostEvidence,
        ModelUsageEvidence,
    )
    from fabrica.features.developer_workflow.application.ports import (
        CommitMessageWorkflowRunner,
        ConfirmedCommitWorkflowRunner,
    )


class ModelEvidenceResult(Protocol):
    """Result shape that can expose model evidence to the product CLI."""

    @property
    def usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        """Return usage evidence emitted by the command."""

    @property
    def cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
        """Return cost evidence emitted by the command."""


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
            confirmed_commit_result=write_confirmed_commit_result,
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
