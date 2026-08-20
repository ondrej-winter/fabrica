"""Model execution port for local agent runtime use cases."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    SafeRuntimeMetadataValue,
)


class AgentModelError(Exception):
    """Runtime-safe model dependency error raised across the model port."""

    def __init__(
        self,
        message: str,
        *,
        status: LocalAgentRunStatus = LocalAgentRunStatus.MODEL_ERROR,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.metadata = dict(metadata or {})


class AgentModel(Protocol):
    """Outbound port for completing one local agent runtime command."""

    async def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run the model/session dependency for one local agent command."""
        ...
