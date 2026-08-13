"""Bootstrap wiring for the agent-runtime product CLI contribution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabrica.adapters.inbound.cli.contributions import CliConfigurationError, CliContribution, CliDispatchError
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    AgentRuntimeCliCompositionOptions,
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliDependencies,
    AgentRuntimeCliOptions,
    AgentRuntimeCliStreams,
    AgentRuntimeCliWriters,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contribution import (
    AGENT_RUNTIME_CLI_COMMAND_TYPES,
    register_agent_runtime_cli_commands,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.output import (
    write_run_result,
    write_script_execution_result,
    write_script_policy_result,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import run_agent_runtime_cli_command

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.contributions import CliExecutionContext
    from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import EvidenceWriter
    from fabrica.features.agent_runtime.application.ports import (
        LocalAgentRuntime,
        SelectedContextLocalAgentRuntime,
        SkillScriptPolicyEvaluator,
        SkillScriptRunner,
    )


def create_agent_runtime_cli_contribution(
    *,
    dependencies: AgentRuntimeCliDependencies | None = None,
    evidence_writer: EvidenceWriter,
) -> CliContribution:
    """Create the agent-runtime CLI contribution with bootstrap-owned defaults."""
    return CliContribution(
        name="agent_runtime",
        command_names=("run", "script-policy", "script-execute"),
        command_types=AGENT_RUNTIME_CLI_COMMAND_TYPES,
        register_commands=register_agent_runtime_cli_commands,
        run_command=_run_agent_runtime_contribution(dependencies, evidence_writer=evidence_writer),
    )


def _run_agent_runtime_contribution(
    overrides: AgentRuntimeCliDependencies | None,
    *,
    evidence_writer: EvidenceWriter,
):
    def run(command: object, context: CliExecutionContext) -> int:
        if not isinstance(command, CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand):
            msg = f"agent-runtime CLI contribution cannot handle command: {type(command).__name__}"
            raise CliDispatchError(msg)
        return run_agent_runtime_cli_command(
            command,
            options=AgentRuntimeCliOptions(
                print_usage=context.global_options.print_usage,
                print_prices=context.global_options.print_prices,
            ),
            dependencies=_agent_runtime_dependencies_for_command(command, context=context, overrides=overrides),
            streams=AgentRuntimeCliStreams(stdout=context.stdout, stderr=context.stderr),
            writers=AgentRuntimeCliWriters(
                run_result=write_run_result,
                evidence=evidence_writer,
                script_policy_result=write_script_policy_result,
                script_execution_result=write_script_execution_result,
            ),
        )

    return run


def _agent_runtime_dependencies_for_command(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    context: CliExecutionContext,
    overrides: AgentRuntimeCliDependencies | None,
) -> AgentRuntimeCliDependencies:
    dependencies = overrides or AgentRuntimeCliDependencies()
    composition_options = _agent_runtime_composition_options_from_context(context)
    if isinstance(command, CliRunCommand):
        if command.skill_ids or command.resources:
            return AgentRuntimeCliDependencies(
                selected_context_runtime=dependencies.selected_context_runtime
                or _create_default_selected_context_runtime(
                    dependencies.runtime or _create_default_runtime(),
                    composition_options=composition_options,
                    verbose_diagnostics=context.global_options.verbose_diagnostics,
                ),
            )
        return AgentRuntimeCliDependencies(
            runtime=dependencies.runtime or _create_default_runtime(),
        )
    if isinstance(command, CliScriptPolicyCommand):
        return AgentRuntimeCliDependencies(
            script_policy_evaluator=dependencies.script_policy_evaluator
            or _create_default_script_policy_evaluator(
                command, context=context, composition_options=composition_options
            ),
        )
    return AgentRuntimeCliDependencies(
        script_executor=dependencies.script_executor
        or _create_default_script_executor(command, context=context, composition_options=composition_options),
    )


def _agent_runtime_composition_options_from_context(context: CliExecutionContext) -> AgentRuntimeCliCompositionOptions:
    if context.composition_options is None:
        return AgentRuntimeCliCompositionOptions()
    if not isinstance(context.composition_options, AgentRuntimeCliCompositionOptions):
        msg = (
            "agent-runtime CLI contribution received incompatible composition options: "
            f"{type(context.composition_options).__name__}"
        )
        raise CliConfigurationError(msg)
    return context.composition_options


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
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    context: CliExecutionContext,
    composition_options: AgentRuntimeCliCompositionOptions,
) -> SkillScriptPolicyEvaluator | None:
    if not isinstance(command, CliScriptPolicyCommand):
        return None

    from fabrica.bootstrap.composition.skill_scripts import (  # noqa: PLC0415
        SkillScriptPolicyEvaluationOptions,
        create_skill_script_policy_evaluator,
    )

    return create_skill_script_policy_evaluator(
        SkillScriptPolicyEvaluationOptions(
            skill_roots=composition_options.skill_roots,
            verbose_diagnostics=context.global_options.verbose_diagnostics,
        ),
    )


def _create_default_script_executor(
    command: CliRunCommand | CliScriptPolicyCommand | CliScriptExecuteCommand,
    *,
    context: CliExecutionContext,
    composition_options: AgentRuntimeCliCompositionOptions,
) -> SkillScriptRunner | None:
    if not isinstance(command, CliScriptExecuteCommand):
        return None

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
            verbose_diagnostics=context.global_options.verbose_diagnostics,
            approval_lookup=MetadataBoundApprovalLookup(command.approval_binding),
        ),
    )
