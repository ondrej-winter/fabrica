"""Tool execution port for bounded local agent runtime tool loops."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    SafeRuntimeMetadataValue,
    ToolCallRequest,
    ToolCallResult,
    ToolLoopLimits,
)


class ToolExecutionError(Exception):
    """Application-safe failure raised for unexpected tool adapter errors."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.metadata = dict(metadata or {})


class ToolExecutor(Protocol):
    """Outbound port for invoking one explicitly registered tool."""

    def execute_tool(self, request: ToolCallRequest, limits: ToolLoopLimits) -> ToolCallResult:
        """Execute one normalized tool request and return a bounded application result."""
        ...
