"""Tests for bounded tool-loop orchestration."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    RuntimeObservation,
    ToolAwareModelResponse,
    ToolBatchPolicy,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolCancellationSignal,
    ToolDefinition,
    ToolExecutionRuntimeDisposition,
    ToolLoopLimits,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModelError, ToolExecutionError
from fabrica.features.agent_runtime.application.use_cases import RunToolLoop, run_tool_loop

EXPECTED_REQUIRED_COMPLETION_MODEL_CALLS = 2


@dataclass
class FakeToolAwareModel:
    responses: list[ToolAwareModelResponse] = field(default_factory=list)
    error: ToolAwareAgentModelError | None = None
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
        del cancellation
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
    opaque_contexts: list[Mapping[str, object]] = field(default_factory=list)

    async def execute_tool(
        self,
        request: ToolCallRequest,
        limits: ToolLoopLimits,
        cancellation: ToolCancellationSignal,
        opaque_context: Mapping[str, object] | None = None,
    ) -> ToolCallResult:
        del cancellation
        self.calls.append((request, limits))
        self.opaque_contexts.append(opaque_context or {})
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

    result = asyncio.run(RunToolLoop(model=model, tool_executor=FakeToolExecutor()).run(command))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.succeeded is True
    assert result.output_text == "done"
    assert result.tool_results == ()
    assert result.observations == (RuntimeObservation(message="model completed"),)
    assert model.calls == [(command, (), ())]


def test_run_tool_loop_retains_plain_text_and_reminds_once_when_completion_tool_is_required() -> None:
    command = LocalAgentRunCommand(prompt="Complete the task")
    model = FakeToolAwareModel(
        responses=[
            ToolAwareModelResponse(output_text="The task is done."),
            ToolAwareModelResponse(output_text="Still done."),
        ],
    )

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=FakeToolExecutor()).run(
            command,
            limits=ToolLoopLimits(max_tool_iterations=2, require_completion_tool=True),
        )
    )

    assert result.status is ToolLoopRunStatus.COMPLETION_TOOL_REQUIRED
    assert result.output_text is None
    assert len(model.calls) == EXPECTED_REQUIRED_COMPLETION_MODEL_CALLS
    assert model.calls[0][0] == command
    reminder_command = model.calls[1][0]
    assert reminder_command.instructions[0].instruction_type == "completion_tool_required"
    assert "submit_and_exit" in reminder_command.instructions[0].text
    assert result.observations == (
        RuntimeObservation(
            message="tool loop retained plain text while completion tool was required",
            metadata={"output_chars": len("The task is done.")},
        ),
        RuntimeObservation(
            message="tool loop retained plain text while completion tool was required",
            metadata={"output_chars": len("Still done.")},
        ),
    )


def test_run_tool_loop_stops_after_successful_terminal_tool_without_another_model_turn() -> None:
    command = LocalAgentRunCommand(prompt="Complete the task")
    submit_call = ToolCallRequest(call_id="call-submit", tool_name="submit_and_exit")
    terminal_result = ToolCallResult(
        call_id="call-submit",
        tool_name="submit_and_exit",
        status=ToolCallResultStatus.SUCCESS,
        runtime_disposition=ToolExecutionRuntimeDisposition.STOP_RUNTIME,
    )
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(submit_call,))])
    executor = FakeToolExecutor(results_by_call_id={submit_call.call_id: terminal_result})

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=executor).run(
            command,
            limits=ToolLoopLimits(require_completion_tool=True),
        )
    )

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text is None
    assert result.tool_results == (terminal_result,)
    assert len(model.calls) == 1


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

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=executor).run(command, available_tools=(tool,), limits=limits)
    )

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "note contents"
    assert result.tool_results == (
        ToolCallResult(
            call_id="call-1",
            tool_name="lookup_note",
            status=ToolCallResultStatus.SUCCESS,
            arguments={"note_id": "abc"},
            result_text="note contents",
        ),
    )
    assert executor.calls == [(tool_call, limits)]
    assert model.calls == [(command, (tool,), ()), (command, (tool,), result.tool_results)]


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

    result = asyncio.run(RunToolLoop(model=model, tool_executor=executor).run(command, limits=limits))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.tool_results == (first_result, second_result)
    assert executor.calls == [(first_call, limits), (second_call, limits)]


def test_run_tool_loop_rejects_solo_tool_in_mixed_batch_before_execution() -> None:
    command = LocalAgentRunCommand(prompt="Ask then inspect")
    question_call = ToolCallRequest(call_id="call-question", tool_name="ask_question")
    lookup_call = ToolCallRequest(call_id="call-lookup", tool_name="lookup_note")
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(question_call, lookup_call))])
    executor = FakeToolExecutor()
    tools = (
        ToolDefinition(name="ask_question", description="Ask the user", batch_policy=ToolBatchPolicy.REQUIRE_SOLO),
        ToolDefinition(name="lookup_note", description="Lookup a note"),
    )

    result = asyncio.run(RunToolLoop(model=model, tool_executor=executor).run(command, available_tools=tools))

    assert result.status is ToolLoopRunStatus.INVALID_TOOL_REQUEST
    assert executor.calls == []
    assert result.observations[-1] == RuntimeObservation(
        message="tool loop rejected a solo-only tool in a mixed batch",
        metadata={"tool_name": "ask_question", "error_code": "ASK_QUESTION_MUST_BE_SOLO"},
    )


@pytest.mark.parametrize(
    "tool_calls",
    [
        (
            ToolCallRequest(call_id="call-submit", tool_name="submit_and_exit"),
            ToolCallRequest(call_id="call-ordinary", tool_name="lookup_note"),
        ),
        (
            ToolCallRequest(call_id="call-ordinary", tool_name="lookup_note"),
            ToolCallRequest(call_id="call-submit", tool_name="submit_and_exit"),
        ),
    ],
)
def test_run_tool_loop_rejects_submit_and_exit_mixed_with_other_tools_before_execution(
    tool_calls: tuple[ToolCallRequest, ToolCallRequest],
) -> None:
    command = LocalAgentRunCommand(prompt="Complete and inspect")
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=tool_calls)])
    executor = FakeToolExecutor()
    tools = (
        ToolDefinition(
            name="submit_and_exit", description="Submit terminal completion", batch_policy=ToolBatchPolicy.REQUIRE_SOLO
        ),
        ToolDefinition(name="lookup_note", description="Lookup a note"),
    )

    result = asyncio.run(RunToolLoop(model=model, tool_executor=executor).run(command, available_tools=tools))

    assert result.status is ToolLoopRunStatus.INVALID_TOOL_REQUEST
    assert result.tool_results == ()
    assert executor.calls == []
    assert result.observations[-1] == RuntimeObservation(
        message="tool loop rejected a solo-only tool in a mixed batch",
        metadata={"tool_name": "submit_and_exit", "error_code": "TERMINAL_TOOL_MIXED_WITH_OTHER_TOOLS"},
    )


def test_run_tool_loop_forwards_opaque_context_without_exposing_it_to_the_model() -> None:
    command = LocalAgentRunCommand(prompt="Use a tool")
    tool = ToolDefinition(name="lookup_note", description="Lookup a note")
    tool_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    model = FakeToolAwareModel(
        responses=[ToolAwareModelResponse(tool_calls=(tool_call,)), ToolAwareModelResponse(output_text="done")]
    )
    executor = FakeToolExecutor(
        results_by_call_id={
            "call-1": ToolCallResult(call_id="call-1", tool_name="lookup_note", status=ToolCallResultStatus.SUCCESS)
        }
    )
    opaque_context = {"host.owner": object()}

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=executor).run(
            command,
            available_tools=(tool,),
            opaque_tool_context=opaque_context,
        )
    )

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert executor.opaque_contexts == [opaque_context]
    assert model.calls == [(command, (tool,), ()), (command, (tool,), result.tool_results)]


def test_run_tool_loop_invokes_terminal_hooks_with_opaque_context_after_completion() -> None:
    async def scenario() -> None:
        received_contexts: list[Mapping[str, object]] = []

        async def record_terminal_context(opaque_context: Mapping[str, object]) -> None:
            received_contexts.append(opaque_context)

        opaque_context = {"host.owner": object()}
        result = await RunToolLoop(
            model=FakeToolAwareModel(responses=[ToolAwareModelResponse(output_text="done")]),
            tool_executor=FakeToolExecutor(),
            terminal_hooks=(record_terminal_context,),
        ).run(LocalAgentRunCommand(prompt="Finish"), opaque_tool_context=opaque_context)

        assert result.status is ToolLoopRunStatus.SUCCESS
        assert received_contexts == [opaque_context]

    asyncio.run(scenario())


def test_run_tool_loop_invokes_terminal_hooks_before_reraising_task_cancellation() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cleaned_up = asyncio.Event()

        @dataclass
        class BlockingToolExecutor:
            async def execute_tool(
                self,
                request: ToolCallRequest,
                limits: ToolLoopLimits,
                cancellation: ToolCancellationSignal,
                opaque_context: Mapping[str, object] | None = None,
            ) -> ToolCallResult:
                del request, limits, cancellation, opaque_context
                started.set()
                await asyncio.Event().wait()
                raise AssertionError

        async def record_cleanup(opaque_context: Mapping[str, object]) -> None:
            assert opaque_context == {"host.owner": "owner-1"}
            cleaned_up.set()

        task = asyncio.create_task(
            RunToolLoop(
                model=FakeToolAwareModel(
                    responses=[ToolAwareModelResponse(tool_calls=(ToolCallRequest("call-1", "lookup_note"),))]
                ),
                tool_executor=BlockingToolExecutor(),
                terminal_hooks=(record_cleanup,),
            ).run(LocalAgentRunCommand(prompt="Wait"), opaque_tool_context={"host.owner": "owner-1"})
        )
        await started.wait()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert cleaned_up.is_set()

    asyncio.run(scenario())


def test_default_cancellation_signal_remains_pending_until_its_waiter_is_cancelled() -> None:
    async def scenario() -> None:
        cancellation = run_tool_loop._NeverCancelledToolCancellationSignal()  # noqa: SLF001

        assert cancellation.is_cancelled is False
        waiting_task = asyncio.create_task(cancellation.wait_until_cancelled())
        await asyncio.sleep(0)
        assert waiting_task.done() is False

        waiting_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting_task

    asyncio.run(scenario())


def test_run_tool_loop_rejects_excessive_tool_calls_before_execution() -> None:
    command = LocalAgentRunCommand(prompt="Use too many tools")
    first_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    second_call = ToolCallRequest(call_id="call-2", tool_name="lookup_note")
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(first_call, second_call))])
    executor = FakeToolExecutor()

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=executor).run(
            command,
            limits=ToolLoopLimits(max_tool_iterations=1, max_tool_calls_per_turn=1, max_tool_result_chars=100),
        ),
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

    result = asyncio.run(RunToolLoop(model=model, tool_executor=executor).run(command))

    assert result.status is ToolLoopRunStatus.INVALID_TOOL_REQUEST
    assert result.tool_results == ()
    assert executor.calls == []
    assert result.observations == (
        RuntimeObservation(
            message="tool loop rejected duplicate tool call id",
            metadata={"tool_call_id": "call-1", "duplicate_scope": "turn"},
        ),
    )


def test_run_tool_loop_replays_exact_duplicate_call_id_across_run_without_reexecution() -> None:
    command = LocalAgentRunCommand(prompt="Reuse a call id")
    first_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    reused_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    first_result = ToolCallResult(call_id="call-1", tool_name="lookup_note", status=ToolCallResultStatus.SUCCESS)
    model = FakeToolAwareModel(
        responses=[
            ToolAwareModelResponse(tool_calls=(first_call,)),
            ToolAwareModelResponse(tool_calls=(reused_call,)),
            ToolAwareModelResponse(output_text="done"),
        ],
    )
    executor = FakeToolExecutor(results_by_call_id={"call-1": first_result})

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=executor).run(
            command,
            limits=ToolLoopLimits(max_tool_iterations=2, max_tool_calls_per_turn=1, max_tool_result_chars=100),
        ),
    )

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "done"
    assert result.tool_results == (first_result, first_result)
    assert executor.calls == [
        (first_call, ToolLoopLimits(max_tool_iterations=2, max_tool_calls_per_turn=1, max_tool_result_chars=100))
    ]


def test_run_tool_loop_rejects_reused_call_id_with_different_arguments_before_execution() -> None:
    command = LocalAgentRunCommand(prompt="Reuse a call id")
    first_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"value": "one"})
    reused_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"value": "two"})
    first_result = ToolCallResult(call_id="call-1", tool_name="lookup_note", status=ToolCallResultStatus.SUCCESS)
    model = FakeToolAwareModel(
        responses=[ToolAwareModelResponse(tool_calls=(first_call,)), ToolAwareModelResponse(tool_calls=(reused_call,))],
    )
    executor = FakeToolExecutor(results_by_call_id={"call-1": first_result})

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=executor).run(
            command,
            limits=ToolLoopLimits(max_tool_iterations=2, max_tool_calls_per_turn=1, max_tool_result_chars=100),
        ),
    )

    assert result.status is ToolLoopRunStatus.INVALID_TOOL_REQUEST
    assert result.tool_results == (
        ToolCallResult(
            call_id="call-1",
            tool_name="lookup_note",
            status=ToolCallResultStatus.SUCCESS,
            arguments={"value": "one"},
        ),
    )
    assert executor.calls == [
        (first_call, ToolLoopLimits(max_tool_iterations=2, max_tool_calls_per_turn=1, max_tool_result_chars=100))
    ]
    assert result.observations == (
        RuntimeObservation(
            message="tool loop rejected duplicate tool call id with conflicting request",
            metadata={"tool_call_id": "call-1"},
        ),
    )


def test_run_tool_loop_continues_after_recoverable_tool_rejection() -> None:
    command = LocalAgentRunCommand(prompt="Use a tool")
    tool_call = ToolCallRequest(call_id="call-1", tool_name="apply_patch")
    rejection = ToolCallResult(
        call_id="call-1",
        tool_name="apply_patch",
        status=ToolCallResultStatus.REJECTED,
        result_text='{"status":"rejected"}',
        error_message="patch rejected",
    )
    model = FakeToolAwareModel(
        responses=[ToolAwareModelResponse(tool_calls=(tool_call,)), ToolAwareModelResponse(output_text="try again")],
    )
    executor = FakeToolExecutor(results_by_call_id={"call-1": rejection})

    result = asyncio.run(RunToolLoop(model=model, tool_executor=executor).run(command))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "try again"
    assert model.calls[-1][2] == (rejection,)


def test_run_tool_loop_stops_on_fatal_tool_disposition() -> None:
    result = _run_single_tool_result(
        ToolCallResultStatus.TOOL_FAILURE,
        runtime_disposition=ToolExecutionRuntimeDisposition.STOP_RUNTIME,
    )

    assert result.status is ToolLoopRunStatus.TOOL_FAILURE


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
    model = FakeToolAwareModel(
        error=ToolAwareAgentModelError(
            "unavailable",
            category="configuration",
            observations=(RuntimeObservation(message="backend unavailable", metadata={"http_status": 503}),),
        ),
    )

    result = asyncio.run(RunToolLoop(model=model, tool_executor=FakeToolExecutor()).run(command))

    assert result.status is ToolLoopRunStatus.MODEL_ERROR
    assert result.observations == (
        RuntimeObservation(message="backend unavailable", metadata={"http_status": 503}),
        RuntimeObservation(message="unavailable", metadata={"category": "configuration"}),
    )


def test_run_tool_loop_normalizes_tool_adapter_error() -> None:
    command = LocalAgentRunCommand(prompt="Use a tool")
    tool_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(tool_call,))])
    executor = FakeToolExecutor(error=ToolExecutionError("boom", category="synthetic"))

    result = asyncio.run(RunToolLoop(model=model, tool_executor=executor).run(command))

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

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=executor).run(
            command,
            limits=ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=3),
        ),
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

    result = asyncio.run(
        RunToolLoop(model=model, tool_executor=executor).run(
            command,
            limits=ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=100),
        ),
    )

    assert result.status is ToolLoopRunStatus.MAX_ITERATIONS_EXCEEDED
    assert len(executor.calls) == 1
    assert result.observations[-1] == RuntimeObservation(
        message="tool loop stopped at max iterations",
        metadata={"max_tool_iterations": 1},
    )


def _run_single_tool_result(
    status: ToolCallResultStatus,
    *,
    runtime_disposition: ToolExecutionRuntimeDisposition = ToolExecutionRuntimeDisposition.CONTINUE_MODEL,
) -> ToolLoopRunResult:
    command = LocalAgentRunCommand(prompt="Use a tool")
    tool_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")
    tool_result = ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=status,
        runtime_disposition=runtime_disposition,
        error_message="synthetic failure" if status is not ToolCallResultStatus.SUCCESS else None,
    )
    model = FakeToolAwareModel(responses=[ToolAwareModelResponse(tool_calls=(tool_call,))])
    executor = FakeToolExecutor(results_by_call_id={"call-1": tool_result})

    return asyncio.run(RunToolLoop(model=model, tool_executor=executor).run(command))
