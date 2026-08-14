"""Bootstrap-owned composition for the Fabrica product CLI."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

from fabrica.adapters.inbound.cli.contracts import CliError, CliExecutionContext, cli_handler_from_namespace
from fabrica.adapters.inbound.cli.output import write_line, write_model_evidence_report
from fabrica.adapters.inbound.cli.parser import (
    cli_global_options_from_namespace,
    parse_args,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliOptions,
    AgentRuntimeCliStreams,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.registration import register_agent_runtime_cli_commands
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import (
    run_local_agent_cli_command,
    run_script_execute_cli_command,
    run_script_policy_cli_command,
    run_selected_context_agent_cli_command,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CliDeveloperWorkflowCompositionOptions,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliOptions,
    DeveloperWorkflowCliStreams,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.registration import (
    register_developer_workflow_cli_commands,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import (
    run_commit_message_cli_command,
    run_confirmed_commit_cli_command,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fabrica.adapters.inbound.cli.contracts import CliCommandRegistrar
    from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
        AgentRuntimeCliCompositionOptions,
        CliRunCommand,
        CliScriptExecuteCommand,
        CliScriptPolicyCommand,
    )
    from fabrica.features.agent_runtime.adapters.inbound.cli.registration import AgentRuntimeCliHandler
    from fabrica.features.agent_runtime.application.ports import (
        LocalAgentRuntime,
        SelectedContextLocalAgentRuntime,
        SkillScriptPolicyEvaluator,
        SkillScriptRunner,
    )
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
    from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence

CLI_CONFIGURATION_ERROR_EXIT_CODE = 2


class ModelEvidenceResult(Protocol):
    """Result shape that can expose model evidence to the product CLI."""

    @property
    def usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        """Return usage evidence emitted by the command."""

    @property
    def cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
        """Return cost evidence emitted by the command."""


@dataclass(frozen=True, slots=True)
class CliDependencyOverrides:
    """Optional test/composition overrides for product CLI command handlers."""

    runtime: LocalAgentRuntime | None = None
    selected_context_runtime: SelectedContextLocalAgentRuntime | None = None
    script_policy_evaluator: SkillScriptPolicyEvaluator | None = None
    script_executor: SkillScriptRunner | None = None
    commit_message_workflow: CommitMessageWorkflowRunner | None = None
    confirmed_commit_workflow: ConfirmedCommitWorkflowRunner | None = None


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Fabrica CLI through bootstrap-owned default composition."""
    return run_cli(argv)


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    overrides: CliDependencyOverrides | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the Fabrica CLI with optional dependency and stream overrides."""
    try:
        namespace = parse_args(
            tuple(argv) if argv is not None else None,
            command_registrars=create_cli_command_registrars(overrides=overrides),
        )
        context = CliExecutionContext(
            global_options=cli_global_options_from_namespace(namespace),
            stdin=stdin or sys.stdin,
            stdout=stdout or sys.stdout,
            stderr=stderr or sys.stderr,
        )
        return cli_handler_from_namespace(namespace)(namespace, context)
    except CliError as err:
        write_line(stderr or sys.stderr, f"error: {err}")
        return CLI_CONFIGURATION_ERROR_EXIT_CODE


def create_cli_command_registrars(
    *,
    overrides: CliDependencyOverrides | None = None,
) -> tuple[CliCommandRegistrar, ...]:
    """Create feature-owned command registrars with bootstrap-owned handlers."""
    dependency_overrides = overrides or CliDependencyOverrides()
    return (
        lambda subparsers: register_agent_runtime_cli_commands(
            subparsers,
            run_command=_run_agent_runtime_command(
                dependency_overrides.runtime,
                selected_context_runtime=dependency_overrides.selected_context_runtime,
            ),
            script_policy_command=_run_script_policy_command(dependency_overrides.script_policy_evaluator),
            script_execute_command=_run_script_execute_command(dependency_overrides.script_executor),
        ),
        lambda subparsers: register_developer_workflow_cli_commands(
            subparsers,
            commit_message_command=_run_commit_message_command(dependency_overrides.commit_message_workflow),
            commit_command=_run_confirmed_commit_command(dependency_overrides.confirmed_commit_workflow),
        ),
    )


def _run_agent_runtime_command(
    runtime_override: LocalAgentRuntime | None,
    *,
    selected_context_runtime: SelectedContextLocalAgentRuntime | None,
) -> AgentRuntimeCliHandler[CliRunCommand]:
    def run(
        command: CliRunCommand,
        composition_options: AgentRuntimeCliCompositionOptions,
        context: CliExecutionContext,
    ) -> int:
        options = AgentRuntimeCliOptions(
            print_usage=context.global_options.print_usage,
            print_prices=context.global_options.print_prices,
        )
        streams = AgentRuntimeCliStreams(stdout=context.stdout, stderr=context.stderr)
        if command.skill_ids or command.resources:
            return run_selected_context_agent_cli_command(
                command,
                options=options,
                streams=streams,
                runtime=selected_context_runtime
                or _create_default_selected_context_runtime(
                    runtime_override or _create_default_runtime(),
                    composition_options=composition_options,
                    verbose_diagnostics=context.global_options.verbose_diagnostics,
                ),
                evidence_writer=_write_requested_model_evidence,
            )

        return run_local_agent_cli_command(
            command,
            options=options,
            streams=streams,
            runtime=runtime_override or _create_default_runtime(),
            evidence_writer=_write_requested_model_evidence,
        )

    return run


def _run_script_policy_command(
    evaluator_override: SkillScriptPolicyEvaluator | None,
) -> AgentRuntimeCliHandler[CliScriptPolicyCommand]:
    def run(
        command: CliScriptPolicyCommand,
        composition_options: AgentRuntimeCliCompositionOptions,
        context: CliExecutionContext,
    ) -> int:
        return run_script_policy_cli_command(
            command,
            streams=AgentRuntimeCliStreams(stdout=context.stdout, stderr=context.stderr),
            evaluator=evaluator_override
            or _create_default_script_policy_evaluator(
                composition_options=composition_options,
                verbose_diagnostics=context.global_options.verbose_diagnostics,
            ),
        )

    return run


def _run_script_execute_command(
    executor_override: SkillScriptRunner | None,
) -> AgentRuntimeCliHandler[CliScriptExecuteCommand]:
    def run(
        command: CliScriptExecuteCommand,
        composition_options: AgentRuntimeCliCompositionOptions,
        context: CliExecutionContext,
    ) -> int:
        return run_script_execute_cli_command(
            command,
            streams=AgentRuntimeCliStreams(stdout=context.stdout, stderr=context.stderr),
            executor=executor_override
            or _create_default_script_executor(
                command,
                composition_options=composition_options,
                verbose_diagnostics=context.global_options.verbose_diagnostics,
            ),
        )

    return run


def _run_commit_message_command(
    workflow_override: CommitMessageWorkflowRunner | None,
) -> DeveloperWorkflowCliHandler[CliCommitMessageCommand]:
    def run(
        command: CliCommitMessageCommand,
        composition_options: CliDeveloperWorkflowCompositionOptions,
        context: CliExecutionContext,
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
            evidence_writer=_write_requested_model_evidence,
        )

    return run


def _run_confirmed_commit_command(
    workflow_override: ConfirmedCommitWorkflowRunner | None,
) -> DeveloperWorkflowCliHandler[CliCommitCommand]:
    def run(
        command: CliCommitCommand,
        composition_options: CliDeveloperWorkflowCompositionOptions,
        context: CliExecutionContext,
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
            evidence_writer=_write_requested_model_evidence,
        )

    return run


def _write_requested_model_evidence(
    result: ModelEvidenceResult,
    *,
    include_usage: bool,
    include_prices: bool,
    stdout: TextIO,
) -> None:
    write_model_evidence_report(
        usage_evidence=result.usage_evidence,
        cost_evidence=result.cost_evidence,
        stdout=stdout,
        include_usage=include_usage,
        include_prices=include_prices,
    )


def _create_default_selected_context_runtime(
    runtime: LocalAgentRuntime,
    *,
    composition_options: AgentRuntimeCliCompositionOptions,
    verbose_diagnostics: bool,
) -> SelectedContextLocalAgentRuntime:
    from fabrica.bootstrap.composition.skill_context import (  # noqa: PLC0415
        SkillContextAugmentationOptions,
        create_selected_context_local_agent_runtime,
    )

    return create_selected_context_local_agent_runtime(
        runtime=runtime,
        options=SkillContextAugmentationOptions(
            skill_roots=composition_options.skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
    )


def _create_default_runtime() -> LocalAgentRuntime:
    from fabrica.bootstrap.composition.codex_runtime import create_codex_runtime  # noqa: PLC0415

    return create_codex_runtime()


def _create_default_script_policy_evaluator(
    *,
    composition_options: AgentRuntimeCliCompositionOptions,
    verbose_diagnostics: bool,
) -> SkillScriptPolicyEvaluator:
    from fabrica.bootstrap.composition.skill_scripts import (  # noqa: PLC0415
        SkillScriptPolicyEvaluationOptions,
        create_skill_script_policy_evaluator,
    )

    return create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=composition_options.skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
    )


def _create_default_script_executor(
    command: CliScriptExecuteCommand,
    *,
    composition_options: AgentRuntimeCliCompositionOptions,
    verbose_diagnostics: bool,
) -> SkillScriptRunner:
    from fabrica.bootstrap.composition.skill_scripts import (  # noqa: PLC0415
        SkillScriptExecutionOptions,
        create_skill_script_executor,
    )
    from fabrica.features.agent_runtime.adapters.outbound.script_approval import (  # noqa: PLC0415
        MetadataBoundApprovalLookup,
    )

    return create_skill_script_executor(
        SkillScriptExecutionOptions(
            skill_roots=composition_options.skill_roots,
            verbose_diagnostics=verbose_diagnostics,
            approval_lookup=MetadataBoundApprovalLookup(command.approval_binding),
        ),
    )


def _create_default_commit_message_workflow(
    *,
    context: CliExecutionContext,
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
    context: CliExecutionContext,
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
