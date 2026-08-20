"""Tests for bounded tool-loop orchestration."""

from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    RuntimeObservation,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModelError, ToolExecutionError
from fabrica.features.agent_runtime.application.use_cases import RunToolLoop


@dataclass
class FakeToolAwareModel:
    responses: list[ToolAwareModelResponse] = field(default_factory=list)
    error: ToolAwareAgentModelError | None = None
    calls: list[tuple[LocalAgentRunCommand, tuple[ToolDefinition, ...], tuple[ToolCallResult, ...]]] = field(
        default_factory=list,
    )

    def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
    ) -> ToolAwareModelResponse:
        self.calls.append((command, available_tools, tool_results))
        if self.error is not None:
            raise self.error
        if not self.responses:
            msg = "test fake requires a response or error"
            raise AssertionError(msg)
        return self.responses.pop(0)


@dataclass
class FakeToolExecutor:
    results_by_call_id: dict[str, ToolCallResult] = field(default_factory=dict)
    error: ToolExecutionError | None = None
    calls: list[tuple[ToolCallRequest, ToolLoopLimits]] = field(default_factory=list)

    def execute_tool(self, request: ToolCallRequest, limits: ToolLoopLimits) -> ToolCallResult:
        self.calls.append((request, limits))
        if self.error is not None:
            raise self.error
        return self.results_by_call_id[request.call_id]


def test_run_tool_loop_returns_final_model_output_without_tools() -> None:
    command = LocalAgentRunCommand(prompt="Answer directly")
    model = FakeToolAwareModel(
        responses=(
            [
                ToolAwareModelResponse(
                    output_text="done",
                    observations=(RuntimeObservation(message="model completed"),),
                ),
            ]
        ),
    )

    result = RunToolLoop(model=model, tool_executor=FakeToolExecutor()).run(command)

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.succeeded is True
    assert result.output_text == "done"
    assert result.tool_results == ()
    assert result.observations == (RuntimeObservation(message="model completed"),)
    assert model.calls == [(command, (), ())]


def test_run_tool_loop_executes_tool_and_returns_result_to_model() -> None:
    command = LocalAgentRunCommand(prompt="Use the lookup tool")
    tool = ToolDefinition(name="lookup_note", description="Lookup a synthetic note")
    tool_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"note_id": "abc"})
    tool_result = ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=ToolCallResultStatus.SUCCESS,
        result_text="note contents",
    )
    model = FakeToolAwareModel(
        responses=[
            ToolAwareModelResponse(tool_calls=(tool_call,)),
            ToolAwareModelResponse(output_text="note contents"),
        ],
    )
    executor = FakeToolExecutor(results_by_call_id={"call-1": tool_result})
    limits = ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=100)

    result = RunToolLoop(model=model, tool_executor=executor).run(command, available_tools=(tool,), limits=limits)

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "note contents"
    assert result.tool_results == (tool_result,)
    assert executor.calls == [(tool_call, limits)]
    assert model.calls == [(command, (tool,), ()), (command, (tool,), (tool_result,))]


def test_run_tool_loop_executes_all_calls_at_per_turn_limit() -> None:
    command = LocalAgentRunCommand(prompt="Use two tools")
    first_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    second_call = ToolCallRequest(call_id="call-2", tool_name="lookup_note")
    first_result = ToolCallResult(call_id="call-1", tool_name="lookup_note", status=ToolCallResultStatus.SUCCESS)
    second_result = ToolCallResult(call_id="call-2", tool_name="lookup_note", status=ToolCallResultStatus.SUCCESS)
    model = FakeToolAwareModel(
        responses=[
            ToolAwareModelResponse(tool_calls=(first_call, second_call)),
            ToolAwareModelResponse(output_text="done"),
        ],
    )
    executor = FakeToolExecutor(results_by_call_id={"call-1": first_result, "call-2": second_result})
    limits = ToolLoopLimits(max_tool_iterations=2, max_tool_calls_per_turn=2, max_tool_result_chars=100)

    result = RunToolLoop(model=model, tool_executor=executor).run(command, limits=limits)

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.tool_results == (first_result, second_result)
    assert executor.calls == [(first_call, limits), (second_call, limits)]


def test_run_tool_loop_rejects_excessive_tool_calls_before_execution() -> None:
    command = LocalAgentRunCommand(prompt="Use too many tools")
    first_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    second_call = ToolCallRequest(call_id="call-2", tool_name="lookup_note")
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(first_call, second_call))])
    executor = FakeToolExecutor()

    result = RunToolLoop(model=model, tool_executor=executor).run(
        command,
        limits=ToolLoopLimits(max_tool_iterations=1, max_tool_calls_per_turn=1, max_tool_result_chars=100),
    )

    assert result.status is ToolLoopRunStatus.TOOL_LIMIT_EXCEEDED
    assert result.tool_results == ()
    assert executor.calls == []
    assert result.observations == (
        RuntimeObservation(
            message="tool loop rejected excessive tool calls",
            metadata={"tool_call_count": 2, "max_tool_calls_per_turn": 1},
        ),
    )


def test_run_tool_loop_rejects_duplicate_call_ids_in_one_turn_before_execution() -> None:
    command = LocalAgentRunCommand(prompt="Use duplicate calls")
    first_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    second_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(first_call, second_call))])
    executor = FakeToolExecutor()

    result = RunToolLoop(model=model, tool_executor=executor).run(command)

    assert result.status is ToolLoopRunStatus.INVALID_TOOL_REQUEST
    assert result.tool_results == ()
    assert executor.calls == []
    assert result.observations == (
        RuntimeObservation(
            message="tool loop rejected duplicate tool call id",
            metadata={"tool_call_id": "call-1", "duplicate_scope": "turn"},
        ),
    )


def test_run_tool_loop_rejects_reused_call_id_across_run_before_reexecution() -> None:
    command = LocalAgentRunCommand(prompt="Reuse a call id")
    first_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    reused_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    first_result = ToolCallResult(call_id="call-1", tool_name="lookup_note", status=ToolCallResultStatus.SUCCESS)
    model = FakeToolAwareModel(
        responses=[ToolAwareModelResponse(tool_calls=(first_call,)), ToolAwareModelResponse(tool_calls=(reused_call,))],
    )
    executor = FakeToolExecutor(results_by_call_id={"call-1": first_result})

    result = RunToolLoop(model=model, tool_executor=executor).run(
        command,
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_calls_per_turn=1, max_tool_result_chars=100),
    )

    assert result.status is ToolLoopRunStatus.INVALID_TOOL_REQUEST
    assert result.tool_results == (first_result,)
    assert executor.calls == [
        (first_call, ToolLoopLimits(max_tool_iterations=2, max_tool_calls_per_turn=1, max_tool_result_chars=100))
    ]
    assert result.observations == (
        RuntimeObservation(
            message="tool loop rejected duplicate tool call id",
            metadata={"tool_call_id": "call-1", "duplicate_scope": "run"},
        ),
    )


def test_run_tool_loop_stops_on_unknown_tool() -> None:
    result = _run_single_tool_result(ToolCallResultStatus.UNKNOWN_TOOL)

    assert result.status is ToolLoopRunStatus.UNKNOWN_TOOL


def test_run_tool_loop_stops_on_invalid_arguments() -> None:
    result = _run_single_tool_result(ToolCallResultStatus.INVALID_ARGUMENTS)

    assert result.status is ToolLoopRunStatus.INVALID_TOOL_REQUEST


def test_run_tool_loop_stops_on_tool_failure() -> None:
    result = _run_single_tool_result(ToolCallResultStatus.TOOL_FAILURE)

    assert result.status is ToolLoopRunStatus.TOOL_FAILURE


def test_run_tool_loop_stops_on_timeout_limit_and_adapter_statuses() -> None:
    assert _run_single_tool_result(ToolCallResultStatus.TIMEOUT).status is ToolLoopRunStatus.TOOL_TIMEOUT
    assert _run_single_tool_result(ToolCallResultStatus.LIMIT_EXCEEDED).status is ToolLoopRunStatus.TOOL_LIMIT_EXCEEDED
    assert _run_single_tool_result(ToolCallResultStatus.ADAPTER_ERROR).status is ToolLoopRunStatus.TOOL_ADAPTER_ERROR


def test_run_tool_loop_normalizes_model_failure() -> None:
    command = LocalAgentRunCommand(prompt="Use a tool")
    model = FakeToolAwareModel(error=ToolAwareAgentModelError("unavailable", category="configuration"))

    result = RunToolLoop(model=model, tool_executor=FakeToolExecutor()).run(command)

    assert result.status is ToolLoopRunStatus.MODEL_ERROR
    assert result.observations == (
        RuntimeObservation(message="tool-aware model dependency failed", metadata={"category": "configuration"}),
    )


def test_run_tool_loop_normalizes_tool_adapter_error() -> None:
    command = LocalAgentRunCommand(prompt="Use a tool")
    tool_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(tool_call,))])
    executor = FakeToolExecutor(error=ToolExecutionError("boom", category="synthetic"))

    result = RunToolLoop(model=model, tool_executor=executor).run(command)

    assert result.status is ToolLoopRunStatus.TOOL_ADAPTER_ERROR
    assert result.tool_results == (
        ToolCallResult(
            call_id="call-1",
            tool_name="lookup_note",
            status=ToolCallResultStatus.ADAPTER_ERROR,
            error_message="tool execution adapter failed",
            observations=(
                RuntimeObservation(
                    message="tool execution adapter failed",
                    metadata={"tool_name": "lookup_note", "category": "synthetic"},
                ),
            ),
        ),
    )


def test_run_tool_loop_truncates_tool_result_before_returning_to_model() -> None:
    command = LocalAgentRunCommand(prompt="Use a tool")
    tool_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    model = FakeToolAwareModel(
        responses=[ToolAwareModelResponse(tool_calls=(tool_call,)), ToolAwareModelResponse(output_text="done")],
    )
    executor = FakeToolExecutor(
        results_by_call_id={
            "call-1": ToolCallResult(
                call_id="call-1",
                tool_name="lookup_note",
                status=ToolCallResultStatus.SUCCESS,
                result_text="abcdef",
            ),
        },
    )

    result = RunToolLoop(model=model, tool_executor=executor).run(
        command,
        limits=ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=3),
    )

    truncated_result = ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=ToolCallResultStatus.SUCCESS,
        result_text="abc",
        observations=(
            RuntimeObservation(
                message="tool result text was truncated", metadata={"tool_name": "lookup_note", "max_chars": 3}
            ),
        ),
    )
    assert result.tool_results == (truncated_result,)
    assert model.calls[-1][2] == (truncated_result,)


def test_run_tool_loop_stops_at_max_iterations() -> None:
    command = LocalAgentRunCommand(prompt="Keep using tools")
    first_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    second_call = ToolCallRequest(call_id="call-2", tool_name="lookup_note")
    model = FakeToolAwareModel(
        responses=[ToolAwareModelResponse(tool_calls=(first_call,)), ToolAwareModelResponse(tool_calls=(second_call,))],
    )
    executor = FakeToolExecutor(
        results_by_call_id={
            "call-1": ToolCallResult(call_id="call-1", tool_name="lookup_note", status=ToolCallResultStatus.SUCCESS),
        },
    )

    result = RunToolLoop(model=model, tool_executor=executor).run(
        command,
        limits=ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=100),
    )

    assert result.status is ToolLoopRunStatus.MAX_ITERATIONS_EXCEEDED
    assert len(executor.calls) == 1
    assert result.observations[-1] == RuntimeObservation(
        message="tool loop stopped at max iterations",
        metadata={"max_tool_iterations": 1},
    )


def _run_single_tool_result(status: ToolCallResultStatus) -> ToolLoopRunResult:
    command = LocalAgentRunCommand(prompt="Use a tool")
    tool_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    tool_result = ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=status,
        error_message="synthetic failure" if status is not ToolCallResultStatus.SUCCESS else None,
    )
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(tool_call,))])
    executor = FakeToolExecutor(results_by_call_id={"call-1": tool_result})

    return RunToolLoop(model=model, tool_executor=executor).run(command)
