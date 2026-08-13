"""Tests for the local agent runtime CLI run command."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import TextIO

import pytest

import fabrica.bootstrap.cli_contributions.agent_runtime as agent_runtime_cli_contribution
from fabrica.adapters.inbound.cli import CliCommandExecutionOptions, CliGlobalOptions, CliInvocation, run_cli_command
from fabrica.adapters.inbound.cli.output import write_model_evidence_report
from fabrica.bootstrap.cli import create_cli_contributions
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    AgentRuntimeCliCompositionOptions,
    CliRunCommand,
    CliSelectedResource,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliDependencies,
    AgentRuntimeCliOptions,
    AgentRuntimeCliStreams,
    AgentRuntimeCliWriters,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.output import write_run_result
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import run_agent_runtime_cli_command
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    ModelCostEvidence,
    ModelPricingStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    ModelUsageObservation,
    RuntimeObservation,
    SelectedSkill,
    SelectedSkillResource,
)

EXPECTED_CONFIGURATION_ERROR_EXIT_CODE = 2
EXPECTED_MODEL_ERROR_EXIT_CODE = 3
EXPECTED_BOUNDED_OUTPUT_LINE_CHARS = 4_000


def run_feature_cli_command(
    invocation: CliRunCommand | CliInvocation,
    *,
    dependencies: AgentRuntimeCliDependencies | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    command, global_options, _composition_options = _normalize_invocation(invocation)
    return run_agent_runtime_cli_command(
        command,
        options=AgentRuntimeCliOptions(
            print_usage=global_options.print_usage,
            print_prices=global_options.print_prices,
        ),
        dependencies=dependencies or AgentRuntimeCliDependencies(),
        streams=AgentRuntimeCliStreams(stdout=stdout or StringIO(), stderr=stderr or StringIO()),
        writers=AgentRuntimeCliWriters(
            run_result=write_run_result,
            evidence=_write_evidence,
            script_policy_result=_unexpected_script_policy_result_writer,
            script_execution_result=_unexpected_script_execution_result_writer,
        ),
    )


def _normalize_invocation(
    invocation: CliRunCommand | CliInvocation,
) -> tuple[CliRunCommand, CliGlobalOptions, AgentRuntimeCliCompositionOptions]:
    if isinstance(invocation, CliInvocation):
        if not isinstance(invocation.command, CliRunCommand):
            msg = "run-command tests only support CliRunCommand invocations"
            raise TypeError(msg)
        composition_options = invocation.composition_options or AgentRuntimeCliCompositionOptions()
        if not isinstance(composition_options, AgentRuntimeCliCompositionOptions):
            msg = "run-command tests require agent-runtime composition options"
            raise TypeError(msg)
        return invocation.command, invocation.global_options, composition_options
    return invocation, CliGlobalOptions(), AgentRuntimeCliCompositionOptions()


def _write_evidence(
    result: LocalAgentRunResult,
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


def _unexpected_script_policy_result_writer(*args: object, **kwargs: object) -> int:
    _ = args, kwargs
    msg = "run-command tests must not execute script-policy writer"
    raise AssertionError(msg)


def _unexpected_script_execution_result_writer(*args: object, **kwargs: object) -> int:
    _ = args, kwargs
    msg = "run-command tests must not execute script-execution writer"
    raise AssertionError(msg)


@dataclass
class FakeRuntime:
    """Test double for the local runtime use case."""

    result: LocalAgentRunResult
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.result


@dataclass
class FakeSelectedContextRuntime:
    """Test double for the selected-context local runtime use case."""

    calls: list[
        tuple[
            LocalAgentRunCommand,
            tuple[SelectedSkill, ...],
            tuple[SelectedSkillResource, ...],
        ]
    ] = field(default_factory=list)
    result: LocalAgentRunResult = field(
        default_factory=lambda: LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="context-ok"),
    )

    def run(
        self,
        command: LocalAgentRunCommand,
        *,
        skill_selections: tuple[SelectedSkill, ...] = (),
        resource_selections: tuple[SelectedSkillResource, ...] = (),
    ) -> LocalAgentRunResult:
        self.calls.append((command, skill_selections, resource_selections))
        return self.result


def test_run_command_maps_prompt_and_model_to_runtime_command() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="pong"),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_feature_cli_command(
        CliRunCommand(prompt="Reply with pong", model_hint="codex-compatible"),
        dependencies=AgentRuntimeCliDependencies(runtime=runtime),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "pong\n"
    assert stderr.getvalue() == ""
    assert runtime.calls == [LocalAgentRunCommand(prompt="Reply with pong", model_hint="codex-compatible")]


def test_run_command_uses_injected_augmenter_for_explicit_selected_context() -> None:
    runtime = FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="unused"))
    selected_context_runtime = FakeSelectedContextRuntime()

    exit_code = run_feature_cli_command(
        CliRunCommand(
            prompt="Use selected context",
            skill_ids=("python-testing",),
            resources=(CliSelectedResource(skill_id="python-testing", resource_id="references/example.md"),),
        ),
        dependencies=AgentRuntimeCliDependencies(
            runtime=runtime,
            selected_context_runtime=selected_context_runtime,
        ),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert selected_context_runtime.calls == [
        (
            LocalAgentRunCommand(prompt="Use selected context"),
            (SelectedSkill(skill_id="python-testing"),),
            (SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md"),),
        ),
    ]
    assert runtime.calls == []


def test_run_invocation_uses_selected_context_runtime_with_selected_skill() -> None:
    selected_context_runtime = FakeSelectedContextRuntime()

    exit_code = run_feature_cli_command(
        CliInvocation(
            command=CliRunCommand(prompt="Use selected context", skill_ids=("python-testing",)),
            composition_options=AgentRuntimeCliCompositionOptions(skill_roots=(Path("synthetic-skills"),)),
        ),
        dependencies=AgentRuntimeCliDependencies(selected_context_runtime=selected_context_runtime),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert selected_context_runtime.calls == [
        (
            LocalAgentRunCommand(prompt="Use selected context"),
            (SelectedSkill(skill_id="python-testing"),),
            (),
        ),
    ]


def test_run_invocation_appends_requested_usage_and_price_evidence() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(
            status=LocalAgentRunStatus.SUCCESS,
            output_text="pong",
            usage_evidence=(
                ModelUsageEvidence(
                    provider="codex",
                    status=ModelUsageCollectionStatus.COLLECTED,
                    source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
                    confidence=ModelUsageEvidenceConfidence.EXTRACTED,
                    model="gpt-5.3-codex-spark",
                    tokens=ModelTokenUsageEvidence(input_tokens=1, output_tokens=1, total_tokens=2),
                ),
            ),
            cost_evidence=(
                ModelCostEvidence(
                    pricing_status=ModelPricingStatus.UNKNOWN,
                    source=ModelUsageEvidenceSource.SOURCE_CODE_OBSERVATION,
                    confidence=ModelUsageEvidenceConfidence.UNKNOWN,
                    observations=(ModelUsageObservation(message="pricing is unknown"),),
                ),
            ),
        ),
    )
    stdout = StringIO()

    exit_code = run_feature_cli_command(
        CliInvocation(
            command=CliRunCommand(prompt="Reply with pong"),
            global_options=CliGlobalOptions(print_usage=True, print_prices=True),
        ),
        dependencies=AgentRuntimeCliDependencies(runtime=runtime),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert stdout.getvalue() == (
        "pong\n"
        "Usage evidence:\n"
        "- provider=codex status=collected source=response_payload confidence=extracted "
        "model=gpt-5.3-codex-spark input_tokens=1 output_tokens=1 total_tokens=2\n"
        "Pricing evidence:\n"
        "- status=unknown source=source_code_observation confidence=unknown observation='pricing is unknown'\n"
    )


def test_run_command_skips_augmentation_when_no_context_is_selected() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="pong"),
    )
    selected_context_runtime = FakeSelectedContextRuntime()

    run_feature_cli_command(
        CliRunCommand(prompt="Reply with pong"),
        dependencies=AgentRuntimeCliDependencies(
            runtime=runtime,
            selected_context_runtime=selected_context_runtime,
        ),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert selected_context_runtime.calls == []


def test_product_run_with_injected_selected_context_runtime_does_not_create_default_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_created() -> object:
        msg = "selected-context run must not create an unused default runtime"
        raise AssertionError(msg)

    monkeypatch.setattr(agent_runtime_cli_contribution, "_create_default_runtime", fail_if_created)
    selected_context_runtime = FakeSelectedContextRuntime()

    exit_code = run_cli_command(
        CliInvocation(command=CliRunCommand(prompt="Use selected context", skill_ids=("python-testing",))),
        options=CliCommandExecutionOptions(
            contributions=create_cli_contributions(
                agent_runtime_dependencies=AgentRuntimeCliDependencies(
                    selected_context_runtime=selected_context_runtime,
                ),
            ),
            stdout=StringIO(),
            stderr=StringIO(),
        ),
    )

    assert exit_code == 0
    assert selected_context_runtime.calls == [
        (
            LocalAgentRunCommand(prompt="Use selected context"),
            (SelectedSkill(skill_id="python-testing"),),
            (),
        ),
    ]


def test_product_run_without_selected_context_does_not_create_selected_context_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_created(*args: object, **kwargs: object) -> object:
        _ = args, kwargs
        msg = "plain run must not create an unused selected-context runtime"
        raise AssertionError(msg)

    monkeypatch.setattr(agent_runtime_cli_contribution, "_create_default_selected_context_runtime", fail_if_created)
    runtime = FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="pong"))

    exit_code = run_cli_command(
        CliInvocation(command=CliRunCommand(prompt="Reply with pong")),
        options=CliCommandExecutionOptions(
            contributions=create_cli_contributions(
                agent_runtime_dependencies=AgentRuntimeCliDependencies(runtime=runtime),
            ),
            stdout=StringIO(),
            stderr=StringIO(),
        ),
    )

    assert exit_code == 0
    assert runtime.calls == [LocalAgentRunCommand(prompt="Reply with pong")]


def test_run_command_maps_non_success_status_to_stable_exit_code_and_stderr() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(
            status=LocalAgentRunStatus.CONFIGURATION_ERROR,
            observations=(
                RuntimeObservation(
                    message="model dependency failed",
                    metadata={"category": "missing_configuration"},
                ),
            ),
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_feature_cli_command(
        CliRunCommand(prompt="Reply with pong"),
        dependencies=AgentRuntimeCliDependencies(runtime=runtime),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_CONFIGURATION_ERROR_EXIT_CODE
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "status: configuration_error\nobservation: model dependency failed category=missing_configuration\n"
    )


def test_run_command_bounds_observation_metadata_for_safe_evidence_capture() -> None:
    long_metadata_value = "x" * (EXPECTED_BOUNDED_OUTPUT_LINE_CHARS + 10)
    runtime = FakeRuntime(
        result=LocalAgentRunResult(
            status=LocalAgentRunStatus.MODEL_ERROR,
            observations=(
                RuntimeObservation(
                    message="backend returned normalized model error",
                    metadata={"safe_detail": long_metadata_value},
                ),
            ),
        ),
    )
    stderr = StringIO()

    exit_code = run_feature_cli_command(
        CliRunCommand(prompt="Reply with pong"),
        dependencies=AgentRuntimeCliDependencies(runtime=runtime),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == EXPECTED_MODEL_ERROR_EXIT_CODE
    assert "observation: backend returned normalized model error safe_detail=" in stderr.getvalue()
    assert "...<truncated>\n" in stderr.getvalue()
    assert long_metadata_value not in stderr.getvalue()
