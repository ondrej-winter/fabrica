"""Deterministic agent-runtime model harnesses for integration composition tests."""

from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCancellationSignal,
    ToolDefinition,
)


@dataclass(slots=True)
class SingleToolCallThenFinalModel:
    """Request one explicit tool, then return its result text as final output."""

    tool_call: ToolCallRequest
    calls: list[tuple[LocalAgentRunCommand, tuple[ToolDefinition, ...], tuple[ToolCallResult, ...]]] = field(
        default_factory=list,
    )

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        """Return the initial tool request or a final response from its result."""
        del cancellation
        self.calls.append((command, available_tools, tool_results))
        if not tool_results:
            return ToolAwareModelResponse(tool_calls=(self.tool_call,))
        return ToolAwareModelResponse(output_text=f"final:{tool_results[0].result_text}")
