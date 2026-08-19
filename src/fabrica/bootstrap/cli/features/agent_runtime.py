"""Bootstrap-owned handlers for agent-runtime CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.bootstrap.cli.model_evidence import write_requested_model_evidence
from fabrica.bootstrap.composition.codex_runtime import create_codex_runtime
from fabrica.bootstrap.composition.skill_context import (
    SkillContextAugmentationOptions,
    create_selected_context_local_agent_runtime,
)
from fabrica.bootstrap.composition.skill_scripts import (
    SkillScriptExecutionOptions,
    SkillScriptPolicyEvaluationOptions,
    create_skill_script_executor,
    create_skill_script_policy_evaluator,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliOptions,
    AgentRuntimeCliStreams,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import (
    run_local_agent_cli_command,
    run_script_execute_cli_command,
    run_script_policy_cli_command,
    run_selected_context_agent_cli_command,
)
from fabrica.features.agent_runtime.adapters.outbound.script_approval import MetadataBoundApprovalLookup

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli import CommandContext
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


def run_agent_runtime_command(
    runtime_override: LocalAgentRuntime | None,
    *,
    selected_context_runtime: SelectedContextLocalAgentRuntime | None,
) -> AgentRuntimeCliHandler[CliRunCommand]:
    """Create a product CLI handler for local agent runtime execution."""

    def run(
        command: CliRunCommand,
        composition_options: AgentRuntimeCliCompositionOptions,
        context: CommandContext,
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
                evidence_writer=write_requested_model_evidence,
            )

        return run_local_agent_cli_command(
            command,
            options=options,
            streams=streams,
            runtime=runtime_override or _create_default_runtime(),
            evidence_writer=write_requested_model_evidence,
        )

    return run


def run_script_policy_command(
    evaluator_override: SkillScriptPolicyEvaluator | None,
) -> AgentRuntimeCliHandler[CliScriptPolicyCommand]:
    """Create a product CLI handler for skill script policy inspection."""

    def run(
        command: CliScriptPolicyCommand,
        composition_options: AgentRuntimeCliCompositionOptions,
        context: CommandContext,
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


def run_script_execute_command(
    executor_override: SkillScriptRunner | None,
) -> AgentRuntimeCliHandler[CliScriptExecuteCommand]:
    """Create a product CLI handler for metadata-approved skill script execution."""

    def run(
        command: CliScriptExecuteCommand,
        composition_options: AgentRuntimeCliCompositionOptions,
        context: CommandContext,
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


def _create_default_selected_context_runtime(
    runtime: LocalAgentRuntime,
    *,
    composition_options: AgentRuntimeCliCompositionOptions,
    verbose_diagnostics: bool,
) -> SelectedContextLocalAgentRuntime:
    return create_selected_context_local_agent_runtime(
        runtime=runtime,
        options=SkillContextAugmentationOptions(
            skill_roots=composition_options.skill_roots,
            verbose_diagnostics=verbose_diagnostics,
        ),
    )


def _create_default_runtime() -> LocalAgentRuntime:
    return create_codex_runtime()


def _create_default_script_policy_evaluator(
    *,
    composition_options: AgentRuntimeCliCompositionOptions,
    verbose_diagnostics: bool,
) -> SkillScriptPolicyEvaluator:
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
    return create_skill_script_executor(
        SkillScriptExecutionOptions(
            skill_roots=composition_options.skill_roots,
            verbose_diagnostics=verbose_diagnostics,
            approval_lookup=MetadataBoundApprovalLookup(command.approval_binding),
        ),
    )
