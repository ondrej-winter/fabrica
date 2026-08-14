"""Tests for the local agent runtime CLI run command."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from typing import TYPE_CHECKING, TextIO

import fabrica.bootstrap.cli as bootstrap_cli
from fabrica.adapters.inbound.cli import CliGlobalOptions
from fabrica.adapters.inbound.cli.output import write_model_evidence_report
from fabrica.bootstrap.cli import CliDependencyOverrides, run_cli
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliSelectedResource,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.contracts import (
    AgentRuntimeCliOptions,
    AgentRuntimeCliStreams,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.runner import (
    run_local_agent_cli_command,
    run_selected_context_agent_cli_command,
)
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

if TYPE_CHECKING:
    import pytest

EXPECTED_CONFIGURATION_ERROR_EXIT_CODE = 2
EXPECTED_MODEL_ERROR_EXIT_CODE = 3
EXPECTED_BOUNDED_OUTPUT_LINE_CHARS = 4_000


def run_feature_cli_command(  # noqa: PLR0913
    command: CliRunCommand,
    *,
    runtime: FakeRuntime | None = None,
    selected_context_runtime: FakeSelectedContextRuntime | None = None,
    global_options: CliGlobalOptions | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    options = global_options or CliGlobalOptions()
    streams = AgentRuntimeCliStreams(stdout=stdout or StringIO(), stderr=stderr or StringIO())
    if command.skill_ids or command.resources:
        assert selected_context_runtime is not None
        return run_selected_context_agent_cli_command(
            command,
            options=AgentRuntimeCliOptions(
                print_usage=options.print_usage,
                print_prices=options.print_prices,
            ),
            streams=streams,
            runtime=selected_context_runtime,
            evidence_writer=_write_evidence,
        )

    assert runtime is not None
    return run_local_agent_cli_command(
        command,
        options=AgentRuntimeCliOptions(
            print_usage=options.print_usage,
            print_prices=options.print_prices,
        ),
        streams=streams,
        runtime=runtime,
        evidence_writer=_write_evidence,
    )


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
        runtime=runtime,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "pong\n"
    assert stderr.getvalue() == ""
    assert runtime.calls == [LocalAgentRunCommand(prompt="Reply with pong", model_hint="codex-compatible")]


def test_run_command_writes_success_output_without_cli_line_truncation() -> None:
    long_output = "x" * (EXPECTED_BOUNDED_OUTPUT_LINE_CHARS + 10)
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text=long_output),
    )
    stdout = StringIO()

    exit_code = run_feature_cli_command(
        CliRunCommand(prompt="Reply with pong"),
        runtime=runtime,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert stdout.getvalue() == f"{long_output}\n"


def test_run_command_uses_injected_augmenter_for_explicit_selected_context() -> None:
    runtime = FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="unused"))
    selected_context_runtime = FakeSelectedContextRuntime()

    exit_code = run_feature_cli_command(
        CliRunCommand(
            prompt="Use selected context",
            skill_ids=("python-testing",),
            resources=(CliSelectedResource(skill_id="python-testing", resource_id="references/example.md"),),
        ),
        selected_context_runtime=selected_context_runtime,
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


def test_run_command_uses_selected_context_runtime_with_selected_skill() -> None:
    selected_context_runtime = FakeSelectedContextRuntime()

    exit_code = run_feature_cli_command(
        CliRunCommand(prompt="Use selected context", skill_ids=("python-testing",)),
        selected_context_runtime=selected_context_runtime,
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


def test_run_command_appends_requested_usage_and_price_evidence() -> None:
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
        CliRunCommand(prompt="Reply with pong"),
        runtime=runtime,
        global_options=CliGlobalOptions(print_usage=True, print_prices=True),
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
        runtime=runtime,
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

    monkeypatch.setattr(bootstrap_cli, "_create_default_runtime", fail_if_created)
    selected_context_runtime = FakeSelectedContextRuntime()

    exit_code = run_cli(
        ("run", "--prompt", "Use selected context", "--skill", "python-testing"),
        overrides=CliDependencyOverrides(
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

    monkeypatch.setattr(bootstrap_cli, "_create_default_selected_context_runtime", fail_if_created)
    runtime = FakeRuntime(result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="pong"))

    exit_code = run_cli(
        ("run", "--prompt", "Reply with pong"),
        overrides=CliDependencyOverrides(runtime=runtime),
        stdout=StringIO(),
        stderr=StringIO(),
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
        runtime=runtime,
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
        runtime=runtime,
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == EXPECTED_MODEL_ERROR_EXIT_CODE
    assert "observation: backend returned normalized model error safe_detail=" in stderr.getvalue()
    assert "...<truncated>\n" in stderr.getvalue()
    assert long_metadata_value not in stderr.getvalue()
