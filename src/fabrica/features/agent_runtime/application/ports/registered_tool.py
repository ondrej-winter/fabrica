"""Registered in-process tool contracts for local agent runtimes."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolDefinition,
    ToolExecutionContext,
)


class RegisteredToolRejectionError(Exception):
    """Signal a sanitized, recoverable rejection from a synchronous tool handler."""

    def __init__(self, *, error_code: str, error_message: str) -> None:
        super().__init__(error_message)
        self.error_code = error_code
        self.error_message = error_message


RegisteredToolHandler = Callable[[Mapping[str, ToolArgumentValue]], str]
AsyncRegisteredToolHandler = Callable[
    [Mapping[str, ToolArgumentValue], ToolExecutionContext],
    Awaitable[RegisteredToolOutcome],
]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    """Explicitly registered in-process callable and application tool definition."""

    definition: ToolDefinition
    handler: RegisteredToolHandler


@dataclass(frozen=True, slots=True)
class AsyncRegisteredTool:
    """Async registered tool contract for cancellation-aware typed outcomes."""

    definition: ToolDefinition
    handler: AsyncRegisteredToolHandler
