"""Tests for the PydanticAI tool-aware runtime model adapter."""

import asyncio
from dataclasses import dataclass, field
from typing import cast

import pytest
from pydantic_ai.messages import BinaryContent, ModelResponse, TextPart, ToolCallPart, ToolReturnPart

from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import (
    PydanticAIToolAwareAgentModel,
    PydanticAIToolAwareTurnRequest,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    ModelTurnInstruction,
    RuntimeObservation,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolImageContent,
    ToolTextContent,
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

    result = asyncio.run(PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(command, available_tools=()))

    assert result.output_text == "done"
    assert result.tool_calls == ()
    assert result.observations == (RuntimeObservation(message="pydanticai tool-aware model returned final text"),)
    assert turn.calls[0].prompt == "Context:\n[note]\nThe answer is done.\n\nPrompt:\nAnswer from context"
    assert turn.calls[0].model_hint == "codex-max"
    assert turn.calls[0].messages


def test_tool_aware_adapter_renders_application_owned_turn_instructions() -> None:
    turn = FakeToolAwareTurn(response=ModelResponse(parts=[TextPart("done")]))
    command = LocalAgentRunCommand(
        prompt="Finish the task",
        instructions=(
            ModelTurnInstruction(
                instruction_type="completion_tool_required",
                text="Call submit_and_exit alone.",
            ),
        ),
    )

    asyncio.run(PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(command, available_tools=()))

    assert turn.calls[0].prompt == (
        "Instructions:\n[completion_tool_required]\nCall submit_and_exit alone.\n\nPrompt:\nFinish the task"
    )


def test_tool_aware_adapter_maps_tool_call_response_to_application_request() -> None:
    tool = ToolDefinition(name="lookup_note", description="Lookup a synthetic note")
    turn = FakeToolAwareTurn(
        response=ModelResponse(
            parts=[ToolCallPart(tool_name="lookup_note", args={"note_id": "abc", "limit": 1}, tool_call_id="call-1")],
        ),
    )

    result = asyncio.run(
        PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
            LocalAgentRunCommand(prompt="Use a tool"),
            available_tools=(tool,),
        ),
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

    asyncio.run(
        PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
            LocalAgentRunCommand(prompt="Continue"),
            available_tools=(),
            tool_results=(tool_result,),
        ),
    )

    tool_return = turn.calls[0].messages[1].parts[0]
    assert isinstance(tool_return, ToolReturnPart)
    assert tool_return.tool_name == "lookup_note"
    assert tool_return.tool_call_id == "call-1"
    assert tool_return.content == "note contents"
    assert tool_return.outcome == "success"
    assert tool_return.metadata == {"status": "success"}


def test_tool_aware_adapter_renders_ordered_provider_neutral_content_parts_at_provider_boundary() -> None:
    turn = FakeToolAwareTurn(response=ModelResponse(parts=[TextPart("final")]))
    tool_result = ToolCallResult(
        call_id="call-1",
        tool_name="read_files",
        status=ToolCallResultStatus.SUCCESS,
        content=(
            ToolTextContent(text="first"),
            ToolImageContent(data=b"\x89PNG\r\n\x1a\nimage", media_type="image/png"),
            ToolTextContent(text="last"),
        ),
    )

    asyncio.run(
        PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
            LocalAgentRunCommand(prompt="Continue"),
            available_tools=(),
            tool_results=(tool_result,),
        ),
    )

    tool_return = turn.calls[0].messages[1].parts[0]
    assert isinstance(tool_return, ToolReturnPart)
    assert isinstance(tool_return.content, tuple)
    first, image, last = cast("tuple[str | BinaryContent, ...]", tool_return.content)
    assert first == "first"
    assert isinstance(image, BinaryContent)
    assert image.data == b"\x89PNG\r\n\x1a\nimage"
    assert image.media_type == "image/png"
    assert last == "last"


def test_tool_aware_adapter_maps_failed_prior_tool_results_as_failed_returns() -> None:
    turn = FakeToolAwareTurn(response=ModelResponse(parts=[TextPart("final")]))
    tool_result = ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=ToolCallResultStatus.TOOL_FAILURE,
        error_message="synthetic failure",
    )

    asyncio.run(
        PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
            LocalAgentRunCommand(prompt="Continue"),
            available_tools=(),
            tool_results=(tool_result,),
        ),
    )

    tool_return = turn.calls[0].messages[1].parts[0]
    assert isinstance(tool_return, ToolReturnPart)
    assert tool_return.content == "synthetic failure"
    assert tool_return.outcome == "failed"
    assert tool_return.metadata == {"status": "tool_failure"}


def test_tool_aware_adapter_maps_nested_tool_call_arguments_to_immutable_json_values() -> None:
    turn = FakeToolAwareTurn(
        response=ModelResponse(
            parts=[ToolCallPart(tool_name="lookup_note", args={"nested": {"unsafe": "value"}}, tool_call_id="call-1")],
        ),
    )

    result = asyncio.run(
        PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
            LocalAgentRunCommand(prompt="Use a tool"),
            available_tools=(),
        ),
    )

    assert result.tool_calls[0].arguments == {"nested": {"unsafe": "value"}}
    with pytest.raises(TypeError):
        cast("dict[str, object]", result.tool_calls[0].arguments)["nested"] = "changed"


def test_tool_aware_adapter_rejects_unsupported_tool_call_argument_value() -> None:
    turn = FakeToolAwareTurn(
        response=ModelResponse(
            parts=[ToolCallPart(tool_name="lookup_note", args={"unsupported": {"value"}}, tool_call_id="call-1")],
        ),
    )

    with pytest.raises(ToolAwareAgentModelError) as error_info:
        asyncio.run(
            PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
                LocalAgentRunCommand(prompt="Use a tool"),
                available_tools=(),
            ),
        )

    assert error_info.value.category == "invalid_tool_arguments"
    assert error_info.value.metadata == {"argument_name": "unsupported", "argument_type": "set"}


@pytest.mark.parametrize(
    "parts",
    [
        (TextPart("done"), ToolCallPart(tool_name="lookup_note", args={}, tool_call_id="call-1")),
        (),
    ],
)
def test_tool_aware_adapter_rejects_invalid_pydanticai_response_parts(parts: tuple[object, ...]) -> None:
    turn = FakeToolAwareTurn(response=ModelResponse(parts=parts))  # ty: ignore[invalid-argument-type]

    with pytest.raises(ToolAwareAgentModelError) as error_info:
        asyncio.run(
            PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
                LocalAgentRunCommand(prompt="Continue"),
                available_tools=(),
            ),
        )

    assert error_info.value.category == "invalid_pydanticai_response"


def test_tool_aware_adapter_normalizes_dependency_failure() -> None:
    turn = FakeToolAwareTurn(error=RuntimeError("do not leak details"))

    with pytest.raises(ToolAwareAgentModelError) as error_info:
        asyncio.run(
            PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(
                LocalAgentRunCommand(prompt="ping"),
                available_tools=(),
            ),
        )

    assert error_info.value.category == "pydanticai_tool_aware_error"
    assert error_info.value.metadata == {"error_type": "RuntimeError"}
    assert "do not leak details" not in str(error_info.value)


def test_tool_aware_adapter_reraises_normalized_model_errors() -> None:
    expected = ToolAwareAgentModelError("already normalized", category="synthetic")
    turn = FakeToolAwareTurn(error=expected)

    with pytest.raises(ToolAwareAgentModelError) as error_info:
        asyncio.run(PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(LocalAgentRunCommand(prompt="ping"), ()))

    assert error_info.value is expected


def test_tool_aware_adapter_renders_list_arguments_as_immutable_tuples() -> None:
    turn = FakeToolAwareTurn(
        response=ModelResponse(parts=[ToolCallPart(tool_name="lookup", args={"items": [1, 2]}, tool_call_id="call-1")])
    )

    result = asyncio.run(
        PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(LocalAgentRunCommand(prompt="ping"), ())
    )

    assert result.tool_calls[0].arguments == {"items": (1, 2)}


def test_tool_aware_adapter_translates_non_object_tool_arguments(monkeypatch) -> None:
    def raise_value_error(self: ToolCallPart) -> dict[str, object]:
        del self
        msg = "not an object"
        raise ValueError(msg)

    monkeypatch.setattr(ToolCallPart, "args_as_dict", raise_value_error)
    turn = FakeToolAwareTurn(
        response=ModelResponse(parts=[ToolCallPart(tool_name="lookup", args="[]", tool_call_id="call-1")]),
    )

    with pytest.raises(ToolAwareAgentModelError) as error_info:
        asyncio.run(PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(LocalAgentRunCommand(prompt="ping"), ()))

    assert error_info.value.category == "invalid_tool_arguments"


def test_tool_aware_adapter_translates_arguments_rejected_by_application_dto() -> None:
    turn = FakeToolAwareTurn(
        response=ModelResponse(
            parts=[ToolCallPart(tool_name="lookup", args={"value": float("inf")}, tool_call_id="call-1")],
        ),
    )

    with pytest.raises(ToolAwareAgentModelError) as error_info:
        asyncio.run(PydanticAIToolAwareAgentModel(turn_runner=turn).run_turn(LocalAgentRunCommand(prompt="ping"), ()))

    assert error_info.value.category == "invalid_tool_arguments"
