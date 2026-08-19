"""Bootstrap-owned handlers for developer-workflow CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.bootstrap.cli.model_evidence import write_requested_model_evidence
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliOptions,
    DeveloperWorkflowCliStreams,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import (
    run_commit_message_cli_command,
    run_confirmed_commit_cli_command,
)

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli import CommandContext
    from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
        CliCommitCommand,
        CliCommitMessageCommand,
        CliDeveloperWorkflowCompositionOptions,
    )
    from fabrica.features.developer_workflow.adapters.inbound.cli.registration import DeveloperWorkflowCliHandler
    from fabrica.features.developer_workflow.application.ports import (
        CommitMessageWorkflowRunner,
        ConfirmedCommitWorkflowRunner,
    )


def run_commit_message_command(
    workflow_override: CommitMessageWorkflowRunner | None,
) -> DeveloperWorkflowCliHandler[CliCommitMessageCommand]:
    """Create a product CLI handler for commit message generation."""

    def run(
        command: CliCommitMessageCommand,
        composition_options: CliDeveloperWorkflowCompositionOptions,
        context: CommandContext,
    ) -> int:
        return run_commit_message_cli_command(
            command,
            options=DeveloperWorkflowCliOptions(
                print_usage=context.global_options.print_usage,
                print_prices=context.global_options.print_prices,
            ),
            streams=DeveloperWorkflowCliStreams(stdin=context.stdin, stdout=context.stdout, stderr=context.stderr),
            workflow=workflow_override
            or _create_default_commit_message_workflow(
                context=context,
                composition_options=composition_options,
            ),
            evidence_writer=write_requested_model_evidence,
        )

    return run


def run_confirmed_commit_command(
    workflow_override: ConfirmedCommitWorkflowRunner | None,
) -> DeveloperWorkflowCliHandler[CliCommitCommand]:
    """Create a product CLI handler for confirmed commit creation."""

    def run(
        command: CliCommitCommand,
        composition_options: CliDeveloperWorkflowCompositionOptions,
        context: CommandContext,
    ) -> int:
        return run_confirmed_commit_cli_command(
            command,
            options=DeveloperWorkflowCliOptions(
                print_usage=context.global_options.print_usage,
                print_prices=context.global_options.print_prices,
            ),
            streams=DeveloperWorkflowCliStreams(stdin=context.stdin, stdout=context.stdout, stderr=context.stderr),
            workflow=workflow_override
            or _create_default_confirmed_commit_workflow(
                context=context,
                composition_options=composition_options,
            ),
            evidence_writer=write_requested_model_evidence,
        )

    return run


def _create_default_commit_message_workflow(
    *,
    context: CommandContext,
    composition_options: CliDeveloperWorkflowCompositionOptions,
) -> CommitMessageWorkflowRunner:
    from fabrica.bootstrap.composition.developer_workflow import (  # noqa: PLC0415
        CommitMessageWorkflowOptions,
        create_codex_commit_message_workflow,
    )

    return create_codex_commit_message_workflow(
        CommitMessageWorkflowOptions(
            codex_model=composition_options.model,
            codex_reasoning_effort=composition_options.reasoning_effort,
            skill_roots=composition_options.skill_roots,
            verbose_diagnostics=context.global_options.verbose_diagnostics,
        ),
    )


def _create_default_confirmed_commit_workflow(
    *,
    context: CommandContext,
    composition_options: CliDeveloperWorkflowCompositionOptions,
) -> ConfirmedCommitWorkflowRunner:
    from fabrica.bootstrap.composition.developer_workflow import (  # noqa: PLC0415
        CommitMessageWorkflowOptions,
        create_codex_confirmed_commit_workflow,
    )

    return create_codex_confirmed_commit_workflow(
        CommitMessageWorkflowOptions(
            codex_model=composition_options.model,
            codex_reasoning_effort=composition_options.reasoning_effort,
            skill_roots=composition_options.skill_roots,
            verbose_diagnostics=context.global_options.verbose_diagnostics,
        ),
    )
