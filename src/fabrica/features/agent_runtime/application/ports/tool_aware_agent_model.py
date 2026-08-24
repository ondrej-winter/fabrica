"""Tool-aware model port for bounded local agent runtime loops."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SafeRuntimeMetadataValue,
    ToolAwareModelResponse,
    ToolCallResult,
    ToolCancellationSignal,
    ToolDefinition,
)


class ToolAwareAgentModelError(Exception):
    """Runtime-safe model dependency error raised across the tool-aware model port."""

    def __init__(
        self,
        message: str,
        *,
        category: str = "model_error",
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.metadata = dict(metadata or {})


class ToolAwareAgentModel(Protocol):
    """Outbound port for one tool-aware model turn."""

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        """Run one model turn with available tools, prior tool results, and cancellation."""
        ...
