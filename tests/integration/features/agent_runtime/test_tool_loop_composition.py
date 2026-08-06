"""Offline integration tests for registered tool-loop composition."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

from fabrica.bootstrap import create_pydantic_ai_tool_loop_runtime, create_tool_loop_runtime
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import PydanticAIToolAwareTurnRequest
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredTool
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    SafeRuntimeMetadataValue,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunStatus,
)

EXPECTED_TOOL_LOOP_TURN_COUNT = 2


@dataclass
class SyntheticToolAwareModel:
    """Fake model that requests one tool then returns a final answer."""

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
        if not tool_results:
            return ToolAwareModelResponse(
                tool_calls=(ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"note_id": "abc"}),),
            )
        return ToolAwareModelResponse(output_text=f"final:{tool_results[0].result_text}")


@dataclass
class SyntheticPydanticAIToolAwareTurn:
    """Fake PydanticAI-shaped turn runner that requests one tool then returns text."""

    calls: list[PydanticAIToolAwareTurnRequest] = field(default_factory=list)

    def run_turn(self, request: PydanticAIToolAwareTurnRequest) -> ModelResponse:
        self.calls.append(request)
        if not request.tool_results:
            return ModelResponse(
                parts=[ToolCallPart(tool_name="lookup_note", args={"note_id": "abc"}, tool_call_id="call-1")],
            )
        return ModelResponse(parts=[TextPart(f"final:{request.tool_results[0].result_text}")])


def test_registered_tool_loop_composition_runs_synthetic_tool_to_final_output() -> None:
    model = SyntheticToolAwareModel()
    tool = RegisteredTool(
        definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
        handler=_lookup_note,
    )
    command = LocalAgentRunCommand(prompt="Use the lookup tool")

    runtime = create_tool_loop_runtime(
        model=model,
        tools=(tool,),
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=100),
    )
    result = runtime.run(command)

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "final:note:abc"
    assert len(result.tool_results) == 1
    assert model.calls[0] == (command, (tool.definition,), ())
    assert model.calls[1] == (command, (tool.definition,), result.tool_results)


def test_registered_tool_loop_composition_fails_closed_for_unknown_tool() -> None:
    runtime = create_tool_loop_runtime(
        model=SyntheticToolAwareModel(),
        tools=(),
        limits=ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=100),
    )

    result = runtime.run(LocalAgentRunCommand(prompt="Use the lookup tool"))

    assert result.status is ToolLoopRunStatus.UNKNOWN_TOOL
    assert result.tool_results[0].error_message == "requested tool is not registered"


def test_registered_tool_loop_factory_does_not_call_model_or_registered_tool_during_construction() -> None:
    model = SyntheticToolAwareModel()
    called = False

    def synthetic_tool(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        nonlocal called
        called = True
        return "called"

    runtime = create_tool_loop_runtime(
        model=model,
        tools=(
            RegisteredTool(
                definition=ToolDefinition(name="synthetic_tool", description="Synthetic tool"),
                handler=synthetic_tool,
            ),
        ),
    )

    assert runtime.available_tools == (ToolDefinition(name="synthetic_tool", description="Synthetic tool"),)
    assert model.calls == []
    assert called is False


def test_pydantic_ai_tool_loop_composition_runs_synthetic_tool_to_final_output() -> None:
    turn = SyntheticPydanticAIToolAwareTurn()
    tool = RegisteredTool(
        definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
        handler=_lookup_note,
    )
    command = LocalAgentRunCommand(prompt="Use the lookup tool", model_hint="synthetic-codex")

    runtime = create_pydantic_ai_tool_loop_runtime(
        turn_runner=turn,
        tools=(tool,),
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=100),
    )
    result = runtime.run(command)

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "final:note:abc"
    assert len(result.tool_results) == 1
    assert len(turn.calls) == EXPECTED_TOOL_LOOP_TURN_COUNT
    assert turn.calls[0].model_hint == "synthetic-codex"
    assert turn.calls[0].available_tools == (tool.definition,)
    assert turn.calls[0].tool_results == ()
    assert turn.calls[1].tool_results == result.tool_results


def test_pydantic_ai_tool_loop_factory_does_not_call_turn_or_tool_during_construction() -> None:
    turn = SyntheticPydanticAIToolAwareTurn()
    called = False

    def synthetic_tool(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        nonlocal called
        called = True
        return "called"

    runtime = create_pydantic_ai_tool_loop_runtime(
        turn_runner=turn,
        tools=(
            RegisteredTool(
                definition=ToolDefinition(name="synthetic_tool", description="Synthetic tool"),
                handler=synthetic_tool,
            ),
        ),
    )

    assert runtime.available_tools == (ToolDefinition(name="synthetic_tool", description="Synthetic tool"),)
    assert turn.calls == []
    assert called is False


def _lookup_note(arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
    note_id = arguments.get("note_id")
    if not isinstance(note_id, str):
        msg = "note_id must be a string"
        raise TypeError(msg)
    return f"note:{note_id}"
