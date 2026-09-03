"""Tests for submit-and-exit completion runtime boundary contracts."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field

from fabrica.bootstrap.composition.completion_runtime import CompletionToolLoopRuntime
from fabrica.bootstrap.composition.tool_loop import ToolLoopRuntime
from fabrica.features.agent_runtime.application.dtos import (
    CompletionOutcome,
    CompletionRecord,
    CompletionVerification,
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunStatus,
)
from fabrica.features.agent_runtime.application.use_cases import RunToolLoop


@dataclass
class _TextModel:
    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        del command, available_tools, cancellation
        if tool_results:
            return ToolAwareModelResponse(output_text="not a completion")
        return ToolAwareModelResponse(tool_calls=(ToolCallRequest(call_id="call-1", tool_name="no_op"),))


@dataclass
class _ContextCapturingExecutor:
    contexts: list[dict[str, object]] = field(default_factory=list)

    async def execute_tool(
        self,
        request: ToolCallRequest,
        limits: ToolLoopLimits,
        cancellation: ToolCancellationSignal,
        opaque_context: Mapping[str, object] | None = None,
    ) -> ToolCallResult:
        del limits, cancellation
        self.contexts.append(dict(opaque_context or {}))
        return ToolCallResult(call_id=request.call_id, tool_name=request.tool_name, status=ToolCallResultStatus.SUCCESS)


def test_completion_record_is_immutable_and_carries_canonical_terminal_fields() -> None:
    record = CompletionRecord(
        run_id="run-1",
        tool_call_id="call-1",
        payload_digest="sha256:" + "1" * 64,
        outcome=CompletionOutcome.COMPLETED,
        summary="Implemented the requested change.",
        verification=CompletionVerification.VERIFIED,
    )

    assert record.summary == "Implemented the requested change."
    assert record.outcome is CompletionOutcome.COMPLETED


def test_completion_tool_loop_run_generates_and_propagates_opaque_run_id() -> None:
    executor = _ContextCapturingExecutor()
    runtime = CompletionToolLoopRuntime(
        runtime=ToolLoopRuntime(runner=RunToolLoop(model=_TextModel(), tool_executor=executor), available_tools=()),
    )

    run = runtime.start_run()
    result = asyncio.run(run.run(LocalAgentRunCommand(prompt="Finish")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert run.run_id.startswith("run_")
    assert executor.contexts == [{"agent_runtime.run_id": run.run_id}]
