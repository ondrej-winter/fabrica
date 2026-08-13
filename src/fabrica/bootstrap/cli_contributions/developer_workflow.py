"""Bootstrap wiring for the developer-workflow product CLI contribution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contributions import CliConfigurationError, CliContribution, CliDispatchError
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CliDeveloperWorkflowCompositionOptions,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliOptions,
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
        command_names=("commit-message", "commit"),
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
            raise CliDispatchError(msg)
        return run_developer_workflow_cli_command(
            command,
            options=DeveloperWorkflowCliOptions(
                print_usage=context.global_options.print_usage,
                print_prices=context.global_options.print_prices,
            ),
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
    composition_options = _developer_workflow_composition_options_from_context(context)
    return DeveloperWorkflowCliDependencies(
        commit_message_workflow=dependencies.commit_message_workflow
        or _create_default_commit_message_workflow(command, context=context, composition_options=composition_options),
        confirmed_commit_workflow=dependencies.confirmed_commit_workflow
        or _create_default_confirmed_commit_workflow(command, context=context, composition_options=composition_options),
    )


def _developer_workflow_composition_options_from_context(
    context: CliExecutionContext,
) -> CliDeveloperWorkflowCompositionOptions:
    if context.composition_options is None:
        return CliDeveloperWorkflowCompositionOptions()
    if not isinstance(context.composition_options, CliDeveloperWorkflowCompositionOptions):
        msg = (
            "developer-workflow CLI contribution received incompatible composition options: "
            f"{type(context.composition_options).__name__}"
        )
        raise CliConfigurationError(msg)
    return context.composition_options


def _create_default_commit_message_workflow(
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    context: CliExecutionContext,
    composition_options: CliDeveloperWorkflowCompositionOptions,
) -> CommitMessageWorkflowRunner | None:
    if not isinstance(command, CliCommitMessageCommand):
        return None

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
    command: CliCommitMessageCommand | CliCommitCommand,
    *,
    context: CliExecutionContext,
    composition_options: CliDeveloperWorkflowCompositionOptions,
) -> ConfirmedCommitWorkflowRunner | None:
    if not isinstance(command, CliCommitCommand):
        return None

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
