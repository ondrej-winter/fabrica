"""Session runtime port owned by the coding-agent-session application layer."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import ToolCancellationSignal
from fabrica.features.coding_agent_session.application.dtos import (
    CodingAgentSessionCommand,
    CodingAgentSessionRuntimeResult,
)


class CodingAgentSessionRuntime(Protocol):
    """Run one composed coding-agent session without terminal or bootstrap dependencies."""

    async def run(
        self,
        command: CodingAgentSessionCommand,
        *,
        cancellation: ToolCancellationSignal | None = None,
    ) -> CodingAgentSessionRuntimeResult:
        """Run a session and return tool-loop plus mutation-gate evidence."""
