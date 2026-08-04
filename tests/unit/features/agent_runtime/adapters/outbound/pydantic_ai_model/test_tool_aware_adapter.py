"""Tests for the PydanticAI tool-aware runtime model adapter."""

from dataclasses import dataclass, field

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart

from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import (
    PydanticAIToolAwareAgentModel,
    PydanticAIToolAwareTurnRequest,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    RuntimeObservation,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModelError


@dataclass
class FakeToolAwareTurn:
    response: ModelResponse | None = None
    error: Exception | None = None
    calls: list[PydanticAIToolAwareTurnRequest] = field(default_factory=list)

    def run_turn(self, request: PydanticAIToolAwareTurnRequest) -> ModelResponse:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.response is None:
            msg = "test fake requires a response or error"
            raise AssertionError(msg)
        return self.response


def test_tool_aware_adapter_maps_text_response_to_final_output() -> None:
    turn = FakeToolAwareTurn(response=ModelResponse(parts=[TextPart("done")]))
    command = LocalAgentRunCommand(
        prompt="Answer from context",
        context=(LocalAgentContextBlock(text="The answer is done.", label="note"),),
        model_hint="codex-max",
    )

    result = PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(command, available_tools=())

    assert result.output_text == "done"
    assert result.tool_calls == ()
    assert result.observations == (RuntimeObservation(message="pydanticai tool-aware model returned final text"),)
    assert turn.calls[0].prompt == "Context:\n[note]\nThe answer is done.\n\nPrompt:\nAnswer from context"
    assert turn.calls[0].model_hint == "codex-max"
    assert turn.calls[0].messages


def test_tool_aware_adapter_maps_tool_call_response_to_application_request() -> None:
    tool = ToolDefinition(name="lookup_note", description="Lookup a synthetic note")
    turn = FakeToolAwareTurn(
        response=ModelResponse(
            parts=[ToolCallPart(tool_name="lookup_note", args={"note_id": "abc", "limit": 1}, tool_call_id="call-1")],
        ),
    )

    result = PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
        LocalAgentRunCommand(prompt="Use a tool"),
        available_tools=(tool,),
    )

    assert result.output_text is None
    assert result.tool_calls == (
        ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"note_id": "abc", "limit": 1}),
    )
    assert result.observations == (RuntimeObservation(message="pydanticai tool-aware model requested tools"),)
    assert turn.calls[0].available_tools == (tool,)


def test_tool_aware_adapter_passes_prior_tool_results_as_pydanticai_tool_returns() -> None:
    turn = FakeToolAwareTurn(response=ModelResponse(parts=[TextPart("final")]))
    tool_result = ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=ToolCallResultStatus.SUCCESS,
        result_text="note contents",
    )

    PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
        LocalAgentRunCommand(prompt="Continue"),
        available_tools=(),
        tool_results=(tool_result,),
    )

    tool_return = turn.calls[0].messages[1].parts[0]
    assert isinstance(tool_return, ToolReturnPart)
    assert tool_return.tool_name == "lookup_note"
    assert tool_return.tool_call_id == "call-1"
    assert tool_return.content == "note contents"
    assert tool_return.outcome == "success"
    assert tool_return.metadata == {"status": "success"}


def test_tool_aware_adapter_maps_failed_prior_tool_results_as_failed_returns() -> None:
    turn = FakeToolAwareTurn(response=ModelResponse(parts=[TextPart("final")]))
    tool_result = ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=ToolCallResultStatus.TOOL_FAILURE,
        error_message="synthetic failure",
    )

    PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
        LocalAgentRunCommand(prompt="Continue"),
        available_tools=(),
        tool_results=(tool_result,),
    )

    tool_return = turn.calls[0].messages[1].parts[0]
    assert isinstance(tool_return, ToolReturnPart)
    assert tool_return.content == "synthetic failure"
    assert tool_return.outcome == "failed"
    assert tool_return.metadata == {"status": "tool_failure"}


def test_tool_aware_adapter_rejects_tool_call_with_unsupported_argument_value() -> None:
    turn = FakeToolAwareTurn(
        response=ModelResponse(
            parts=[ToolCallPart(tool_name="lookup_note", args={"nested": {"unsafe": "value"}}, tool_call_id="call-1")],
        ),
    )

    with pytest.raises(ToolAwareAgentModelError) as error_info:
        PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
            LocalAgentRunCommand(prompt="Use a tool"),
            available_tools=(),
        )

    assert error_info.value.category == "invalid_tool_arguments"
    assert error_info.value.metadata == {"argument_name": "nested", "argument_type": "dict"}


def test_tool_aware_adapter_normalizes_dependency_failure() -> None:
    turn = FakeToolAwareTurn(error=RuntimeError("do not leak details"))

    with pytest.raises(ToolAwareAgentModelError) as error_info:
        PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
            LocalAgentRunCommand(prompt="ping"),
            available_tools=(),
        )

    assert error_info.value.category == "pydanticai_tool_aware_error"
    assert error_info.value.metadata == {"error_type": "RuntimeError"}
    assert "do not leak details" not in str(error_info.value)
