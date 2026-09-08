"""Tests for coding-agent-session orchestration."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from fabrica.features.agent_runtime.application.dtos import ToolCancellationSignal, ToolLoopRunResult, ToolLoopRunStatus
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionRuntimeResult,
    MutationDisposition,
    MutationDispositionStatus,
    MutationGateEvidence,
    SessionStatus,
)
from fabrica.features.coding_agent_session.application.use_cases import RunCodingAgentSession


@dataclass
class FakeSessionRuntime:
    """In-memory session runtime boundary for orchestration tests."""

    result: CodingAgentSessionRuntimeResult
    calls: list[CodingAgentSessionCommand] = field(default_factory=list)

    async def run(
        self,
        command: CodingAgentSessionCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> CodingAgentSessionRuntimeResult:
        """Record the delegated command and return the configured result."""
        del cancellation
        self.calls.append(command)
        return self.result


@dataclass(frozen=True)
class CancelledSignal:
    """Cancellation signal that has already been cancelled."""

    @property
    def is_cancelled(self) -> bool:
        """Return that cancellation has been requested."""
        return True

    async def wait_until_cancelled(self) -> None:
        """Return immediately because cancellation is already requested."""


@pytest.mark.parametrize(
    ("runtime_result", "cancellation", "expected_status"),
    [
        (
            CodingAgentSessionRuntimeResult(
                tool_loop_result=ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS),
                mutation_gate=MutationGateEvidence(mutation_enabled=True),
                mutation_disposition=MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED),
            ),
            None,
            SessionStatus.COMPLETED,
        ),
        (
            CodingAgentSessionRuntimeResult(
                tool_loop_result=ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS),
                mutation_gate=MutationGateEvidence(mutation_enabled=False, reason="capability unavailable"),
                mutation_disposition=MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED),
            ),
            None,
            SessionStatus.COMPLETED_READ_ONLY,
        ),
        (
            CodingAgentSessionRuntimeResult(
                tool_loop_result=ToolLoopRunResult(status=ToolLoopRunStatus.MODEL_ERROR),
                mutation_gate=MutationGateEvidence(mutation_enabled=True),
                mutation_disposition=MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED),
            ),
            None,
            SessionStatus.FAILED,
        ),
        (
            CodingAgentSessionRuntimeResult(
                tool_loop_result=ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS),
                mutation_gate=MutationGateEvidence(mutation_enabled=True),
                mutation_disposition=MutationDisposition(MutationDispositionStatus.NOT_ATTEMPTED),
            ),
            CancelledSignal(),
            SessionStatus.CANCELLED,
        ),
    ],
)
def test_session_maps_runtime_and_cancellation_evidence_to_final_status(
    runtime_result: CodingAgentSessionRuntimeResult,
    cancellation: ToolCancellationSignal | None,
    expected_status: SessionStatus,
) -> None:
    """Map session outcomes without allowing orchestration to invent mutation evidence."""
    runtime = FakeSessionRuntime(runtime_result)
    command = CodingAgentSessionCommand(workspace_root=Path("/workspace"), prompt="Inspect")

    result = asyncio.run(RunCodingAgentSession(runtime).run(command, cancellation=cancellation))

    assert result.status is expected_status
    assert runtime.calls == [command]
