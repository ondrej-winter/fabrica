"""Bootstrap wiring for the developer-workflow product CLI contribution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contributions import CliContribution
from fabrica.bootstrap.composition import (
    CommitMessageWorkflowOptions,
    create_codex_commit_message_workflow,
    create_codex_confirmed_commit_workflow,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliStreams,
    DeveloperWorkflowCliWriters,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contribution import (
    DEVELOPER_WORKFLOW_CLI_COMMAND_TYPES,
    register_developer_workflow_cli_commands,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.output import (
    write_confirmed_commit_result,
    write_developer_workflow_result,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import run_developer_workflow_cli_command

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.contributions import CliExecutionContext
    from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import EvidenceWriter
    from fabrica.features.developer_workflow.application.ports import (
        CommitMessageWorkflowRunner,
        ConfirmedCommitWorkflowRunner,
    )


def create_developer_workflow_cli_contribution(
    *,
    dependencies: DeveloperWorkflowCliDependencies | None = None,
    evidence_writer: EvidenceWriter,
) -> CliContribution:
    """Create the developer-workflow CLI contribution with bootstrap-owned defaults.

    The feature runner maps only use-case input into application commands. Default
    Codex-backed workflow factories consume explicit adapter-local composition options.
    """
    return CliContribution(
        name="developer_workflow",
        command_types=DEVELOPER_WORKFLOW_CLI_COMMAND_TYPES,
        register_commands=register_developer_workflow_cli_commands,
        run_command=_run_developer_workflow_contribution(dependencies, evidence_writer=evidence_writer),
    )


def _run_developer_workflow_contribution(
    overrides: DeveloperWorkflowCliDependencies | None,
    *,
    evidence_writer: EvidenceWriter,
):
    def run(command: object, context: CliExecutionContext) -> int:
        if not isinstance(command, CliCommitMessageCommand | CliCommitCommand):
            msg = f"developer-workflow CLI contribution cannot handle command: {type(command).__name__}"
            raise TypeError(msg)
        return run_developer_workflow_cli_command(
            command,
            global_options=context.global_options,
            dependencies=_developer_workflow_dependencies_for_command(command, context=context, overrides=overrides),
            streams=DeveloperWorkflowCliStreams(
                stdin=context.stdin,
                stdout=context.stdout,
                stderr=context.stderr,
            ),
            writers=DeveloperWorkflowCliWriters(
                evidence=evidence_writer,
                runtime_result=write_developer_workflow_result,
                confirmed_commit_result=write_confirmed_commit_result,
            ),
        )

    return run


def _developer_workflow_dependencies_for_command(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    context: CliExecutionContext,
    overrides: DeveloperWorkflowCliDependencies | None,
) -> DeveloperWorkflowCliDependencies:
    dependencies = overrides or DeveloperWorkflowCliDependencies()
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
    options = command.composition_options

    return create_codex_commit_message_workflow(
        CommitMessageWorkflowOptions(
            codex_model=options.model,
            codex_reasoning_effort=options.reasoning_effort,
            skill_roots=options.skill_roots,
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
    options = command.composition_options

    return create_codex_confirmed_commit_workflow(
        CommitMessageWorkflowOptions(
            codex_model=options.model,
            codex_reasoning_effort=options.reasoning_effort,
            skill_roots=options.skill_roots,
            verbose_diagnostics=context.global_options.verbose_diagnostics,
        ),
    )
