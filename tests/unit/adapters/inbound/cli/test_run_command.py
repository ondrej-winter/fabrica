"""Tests for the local agent runtime CLI run command."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from fabrica.adapters.inbound.cli import (
    CliCommandDependencies,
    CliGlobalOptions,
    CliInvocation,
    run_cli_command,
)
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import CliRunCommand, CliSelectedResource
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
    SelectedSkill,
    SelectedSkillResource,
)

EXPECTED_CONFIGURATION_ERROR_EXIT_CODE = 2
EXPECTED_MODEL_ERROR_EXIT_CODE = 3
EXPECTED_BOUNDED_OUTPUT_LINE_CHARS = 4_000


@dataclass
class FakeRuntime:
    """Test double for the local runtime use case."""

    result: LocalAgentRunResult
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.result


@dataclass
class RecordingAugmenter:
    """Test double for selected skill/resource context augmentation."""

    calls: list[
        tuple[
            LocalAgentRunCommand,
            tuple[SelectedSkill, ...],
            tuple[SelectedSkillResource, ...],
            tuple[Path, ...],
            bool,
        ]
    ] = field(default_factory=list)

    def __call__(
        self,
        command: LocalAgentRunCommand,
        skill_selections: tuple[SelectedSkill, ...],
        resource_selections: tuple[SelectedSkillResource, ...],
        *,
        skill_roots: tuple[Path, ...],
        verbose_diagnostics: bool,
    ) -> LocalAgentRunCommand:
        self.calls.append((command, skill_selections, resource_selections, skill_roots, verbose_diagnostics))
        return LocalAgentRunCommand(
            prompt=command.prompt,
            model_hint=command.model_hint,
            context=(LocalAgentContextBlock(text="synthetic skill context", label="python-testing"),),
        )


def test_run_command_maps_prompt_and_model_to_runtime_command() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="pong"),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        CliRunCommand(prompt="Reply with pong", model_hint="codex-compatible"),
        dependencies=CliCommandDependencies(runtime=runtime),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "pong\n"
    assert stderr.getvalue() == ""
    assert runtime.calls == [LocalAgentRunCommand(prompt="Reply with pong", model_hint="codex-compatible")]


def test_run_command_uses_injected_augmenter_for_explicit_selected_context() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="context-ok"),
    )
    augmenter = RecordingAugmenter()

    exit_code = run_cli_command(
        CliRunCommand(
            prompt="Use selected context",
            skill_ids=("python-testing",),
            resources=(CliSelectedResource(skill_id="python-testing", resource_id="references/example.md"),),
            skill_roots=(Path("synthetic-skills"),),
        ),
        dependencies=CliCommandDependencies(runtime=runtime, command_augmenter=augmenter),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert augmenter.calls == [
        (
            LocalAgentRunCommand(prompt="Use selected context"),
            (SelectedSkill(skill_id="python-testing"),),
            (SelectedSkillResource(skill_id="python-testing", resource_id="references/example.md"),),
            (Path("synthetic-skills"),),
            False,
        ),
    ]
    assert runtime.calls == [
        LocalAgentRunCommand(
            prompt="Use selected context",
            context=(LocalAgentContextBlock(text="synthetic skill context", label="python-testing"),),
        ),
    ]


def test_run_invocation_passes_global_verbose_diagnostics_to_augmenter() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="context-ok"),
    )
    augmenter = RecordingAugmenter()

    exit_code = run_cli_command(
        CliInvocation(
            command=CliRunCommand(
                prompt="Use selected context",
                skill_ids=("python-testing",),
                skill_roots=(Path("synthetic-skills"),),
            ),
            global_options=CliGlobalOptions(verbose_diagnostics=True),
        ),
        dependencies=CliCommandDependencies(runtime=runtime, command_augmenter=augmenter),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert augmenter.calls[0][4] is True


def test_run_command_skips_augmentation_when_no_context_is_selected() -> None:
    runtime = FakeRuntime(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="pong"),
    )
    augmenter = RecordingAugmenter()

    run_cli_command(
        CliRunCommand(prompt="Reply with pong"),
        dependencies=CliCommandDependencies(runtime=runtime, command_augmenter=augmenter),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert augmenter.calls == []


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

    exit_code = run_cli_command(
        CliRunCommand(prompt="Reply with pong"),
        dependencies=CliCommandDependencies(runtime=runtime),
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

    exit_code = run_cli_command(
        CliRunCommand(prompt="Reply with pong"),
        dependencies=CliCommandDependencies(runtime=runtime),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == EXPECTED_MODEL_ERROR_EXIT_CODE
    assert "observation: backend returned normalized model error safe_detail=" in stderr.getvalue()
    assert "...<truncated>\n" in stderr.getvalue()
    assert long_metadata_value not in stderr.getvalue()
