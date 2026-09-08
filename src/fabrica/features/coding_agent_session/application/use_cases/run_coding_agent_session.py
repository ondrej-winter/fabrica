"""Use case for one terminal-hosted coding-agent session."""

from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import ToolCancellationSignal
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionResult,
    SessionStatus,
)
from fabrica.features.coding_agent_session.application.ports import CodingAgentSessionRuntime


@dataclass(frozen=True, slots=True)
class RunCodingAgentSession:
    """Delegate a validated session command to the composed runtime boundary."""

    runtime: CodingAgentSessionRuntime

    async def run(
        self,
        command: CodingAgentSessionCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> CodingAgentSessionResult:
        """Run one session and map authoritative runtime evidence to a final status."""
        runtime_result = await self.runtime.run(command, cancellation=cancellation)
        if cancellation is not None and cancellation.is_cancelled:
            status = SessionStatus.CANCELLED
        elif not runtime_result.tool_loop_result.succeeded:
            status = SessionStatus.FAILED
        elif not runtime_result.mutation_gate.mutation_enabled:
            status = SessionStatus.COMPLETED_READ_ONLY
        else:
            status = SessionStatus.COMPLETED
        return CodingAgentSessionResult(status=status, runtime_result=runtime_result)
