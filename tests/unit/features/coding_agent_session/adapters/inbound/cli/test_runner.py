"""Tests for coding-agent-session CLI execution and output."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from fabrica.features.agent_runtime.application.dtos import (
    RuntimeObservation,
    ToolCancellationSignal,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.coding_agent_session.adapters.inbound.cli import (
    CliCodingAgentSessionCommand,
    CodingAgentSessionCliStreams,
    run_coding_agent_session_cli_command,
)
from fabrica.features.coding_agent_session.adapters.inbound.cli.output import write_session_result
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionResult,
    CodingAgentSessionRuntimeResult,
    MutationDisposition,
    MutationDispositionStatus,
    MutationGateEvidence,
    SessionStatus,
)

EXPECTED_SESSION_FAILURE_EXIT_CODE = 3
EXPECTED_SESSION_CANCELLATION_EXIT_CODE = 130


@dataclass
class FakeSessionRuntime:
    """In-memory session runtime boundary for CLI tests."""

    result: CodingAgentSessionRuntimeResult
    calls: list[CodingAgentSessionCommand] = field(default_factory=list)

    async def run(
        self,
        command: CodingAgentSessionCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> CodingAgentSessionRuntimeResult:
        """Record one session command and return the configured outcome."""
        del cancellation
        self.calls.append(command)
        return self.result


def test_runner_forwards_explicit_context_and_renders_completed_session() -> None:
    runtime = FakeSessionRuntime(_result(ToolLoopRunStatus.SUCCESS, mutation_enabled=True, output_text="Done."))
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_coding_agent_session_cli_command(
        CliCodingAgentSessionCommand(
            workspace_root=Path("/workspace"),
            prompt="Fix tests",
            skill_ids=("python-testing",),
        ),
        streams=CodingAgentSessionCliStreams(stdout=stdout, stderr=stderr),
        runtime=runtime,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "Done.\nMutation disposition: not_attempted\nSession status: completed\n"
    assert stderr.getvalue() == ""
    command = runtime.calls[0]
    assert command.workspace_root == Path("/workspace")
    assert command.prompt == "Fix tests"
    assert tuple(selection.skill_id for selection in command.selected_skills) == ("python-testing",)


def test_runner_renders_read_only_fallback_with_success_exit_code() -> None:
    runtime = FakeSessionRuntime(_result(ToolLoopRunStatus.SUCCESS, mutation_enabled=False))
    stdout = StringIO()

    exit_code = run_coding_agent_session_cli_command(
        CliCodingAgentSessionCommand(workspace_root=Path("/workspace"), prompt="Inspect"),
        streams=CodingAgentSessionCliStreams(stdout=stdout, stderr=StringIO()),
        runtime=runtime,
    )

    assert exit_code == 0
    assert stdout.getvalue() == (
        "Mutation: unavailable; session completed read-only.\n"
        "Mutation gate: capability_unavailable\n"
        "Mutation disposition: not_attempted\n"
        "Session status: completed_read_only\n"
    )


def test_runner_maps_failed_tool_loop_to_stable_failure_exit_code() -> None:
    runtime = FakeSessionRuntime(
        _result(
            ToolLoopRunStatus.MODEL_ERROR,
            mutation_enabled=True,
            observations=(RuntimeObservation(message="Codex backend returned an unsuccessful response"),),
        ),
    )
    stderr = StringIO()

    exit_code = run_coding_agent_session_cli_command(
        CliCodingAgentSessionCommand(workspace_root=Path("/workspace"), prompt="Inspect"),
        streams=CodingAgentSessionCliStreams(stdout=StringIO(), stderr=stderr),
        runtime=runtime,
    )

    assert exit_code == EXPECTED_SESSION_FAILURE_EXIT_CODE
    assert stderr.getvalue() == (
        "tool-loop status: model_error\ndiagnostic: Codex backend returned an unsuccessful response\n"
    )


def test_result_writer_maps_cancelled_session_to_stable_exit_code() -> None:
    stdout = StringIO()
    stderr = StringIO()
    runtime_result = _result(ToolLoopRunStatus.SUCCESS, mutation_enabled=True)

    exit_code = write_session_result(
        CodingAgentSessionResult(status=SessionStatus.CANCELLED, runtime_result=runtime_result),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_SESSION_CANCELLATION_EXIT_CODE
    assert stdout.getvalue() == "Mutation disposition: not_attempted\nSession status: cancelled\n"
    assert stderr.getvalue() == "session cancelled\n"


def _result(
    tool_loop_status: ToolLoopRunStatus,
    *,
    mutation_enabled: bool,
    output_text: str | None = None,
    observations: tuple[RuntimeObservation, ...] = (),
) -> CodingAgentSessionRuntimeResult:
    return CodingAgentSessionRuntimeResult(
        tool_loop_result=ToolLoopRunResult(
            status=tool_loop_status,
            output_text=output_text,
            observations=observations,
        ),
        mutation_gate=(
            MutationGateEvidence(mutation_enabled=True)
            if mutation_enabled
            else MutationGateEvidence(mutation_enabled=False, reason="capability_unavailable")
        ),
        mutation_disposition=MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED),
    )
