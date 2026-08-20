"""Tests for tool-loop application DTO contracts."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_MAX_TOOL_CALLS_PER_TURN,
    MAX_TOOL_CALL_ID_CHARS,
    MAX_TOOL_DESCRIPTION_CHARS,
    MAX_TOOL_ERROR_MESSAGE_CHARS,
    MAX_TOOL_NAME_CHARS,
    MAX_TOOL_RESPONSE_TEXT_CHARS,
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
from fabrica.features.agent_runtime.application.dtos.runtime import MAX_CONTEXT_TEXT_CHARS

EXPECTED_MAX_TOOL_ITERATIONS = 2
EXPECTED_MAX_TOOL_RESULT_CHARS = 20


def test_tool_status_values_match_normalized_contracts() -> None:
    assert {status.value for status in ToolCallResultStatus} == {
        "success",
        "unknown_tool",
        "invalid_arguments",
        "tool_failure",
        "timeout",
        "limit_exceeded",
        "adapter_error",
    }
    assert {status.value for status in ToolLoopRunStatus} == {
        "success",
        "model_error",
        "unknown_tool",
        "invalid_tool_request",
        "tool_failure",
        "tool_timeout",
        "tool_limit_exceeded",
        "tool_adapter_error",
        "max_iterations_exceeded",
    }


def test_tool_definition_and_request_copy_mapping_fields() -> None:
    metadata = {"type": "string", "required": True}
    definition = ToolDefinition(name="lookup_note", description="Lookup a synthetic note", argument_schema=metadata)
    request = ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"note_id": "abc"})

    metadata["type"] = "changed"

    assert definition.argument_schema["type"] == "string"
    assert request.arguments["note_id"] == "abc"
    with pytest.raises(TypeError):
        cast("dict[str, object]", definition.argument_schema)["type"] = "changed"
    with pytest.raises(TypeError):
        cast("dict[str, object]", request.arguments)["note_id"] = "changed"


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: ToolDefinition(name="", description="safe"), "tool name must not be empty"),
        (lambda: ToolDefinition(name=" bad", description="safe"), "leading or trailing"),
        (lambda: ToolDefinition(name="bad/name", description="safe"), "unsupported characters"),
        (lambda: ToolDefinition(name="x" * (MAX_TOOL_NAME_CHARS + 1), description="safe"), "identifier bound"),
        (lambda: ToolDefinition(name="safe", description=""), "description must not be empty"),
        (
            lambda: ToolDefinition(name="safe", description="x" * (MAX_TOOL_DESCRIPTION_CHARS + 1)),
            "description exceeds",
        ),
        (lambda: ToolCallRequest(call_id="x" * (MAX_TOOL_CALL_ID_CHARS + 1), tool_name="safe"), "identifier bound"),
    ],
)
def test_tool_identifiers_and_descriptions_are_bounded(factory: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_tool_loop_limits_are_conservative_and_bounded() -> None:
    limits = ToolLoopLimits(
        max_tool_iterations=EXPECTED_MAX_TOOL_ITERATIONS,
        max_tool_result_chars=EXPECTED_MAX_TOOL_RESULT_CHARS,
    )

    assert limits.max_tool_iterations == EXPECTED_MAX_TOOL_ITERATIONS
    assert limits.max_tool_calls_per_turn == DEFAULT_MAX_TOOL_CALLS_PER_TURN
    assert limits.max_tool_result_chars == EXPECTED_MAX_TOOL_RESULT_CHARS
    with pytest.raises(ValueError, match="max_tool_iterations must be at least 1"):
        ToolLoopLimits(max_tool_iterations=0)
    with pytest.raises(ValueError, match="max_tool_calls_per_turn must be at least 1"):
        ToolLoopLimits(max_tool_calls_per_turn=0)
    with pytest.raises(ValueError, match="max_tool_result_chars must be at least 1"):
        ToolLoopLimits(max_tool_result_chars=0)
    with pytest.raises(ValueError, match="context block bound"):
        ToolLoopLimits(max_tool_result_chars=MAX_CONTEXT_TEXT_CHARS + 1)


def test_tool_result_bounds_text_and_truncates_for_loop_limits() -> None:
    result = ToolCallResult(
        call_id="call-1", tool_name="lookup_note", status=ToolCallResultStatus.SUCCESS, result_text="abcdef"
    )

    bounded = result.bounded(ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=3))

    assert bounded.result_text == "abc"
    assert bounded.observations == (
        RuntimeObservation(
            message="tool result text was truncated", metadata={"tool_name": "lookup_note", "max_chars": 3}
        ),
    )
    with pytest.raises(ValueError, match="result text exceeds"):
        ToolCallResult(
            call_id="call-1",
            tool_name="lookup_note",
            status=ToolCallResultStatus.SUCCESS,
            result_text="x" * (MAX_TOOL_RESPONSE_TEXT_CHARS + 1),
        )
    with pytest.raises(ValueError, match="error message exceeds"):
        ToolCallResult(
            call_id="call-1",
            tool_name="lookup_note",
            status=ToolCallResultStatus.TOOL_FAILURE,
            error_message="x" * (MAX_TOOL_ERROR_MESSAGE_CHARS + 1),
        )


def test_model_response_requires_exactly_one_response_kind() -> None:
    tool_call = ToolCallRequest(call_id="call-1", tool_name="lookup_note")

    assert ToolAwareModelResponse(output_text="done").output_text == "done"
    assert ToolAwareModelResponse(tool_calls=(tool_call,)).tool_calls == (tool_call,)
    with pytest.raises(ValueError, match="must include output text or tool calls"):
        ToolAwareModelResponse()
    with pytest.raises(ValueError, match="must not include both"):
        ToolAwareModelResponse(output_text="done", tool_calls=(tool_call,))


def test_tool_loop_result_exposes_success_helper_and_is_immutable() -> None:
    result = ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS, output_text="done")

    assert result.succeeded is True
    with pytest.raises(FrozenInstanceError):
        result.status = ToolLoopRunStatus.MODEL_ERROR  # ty: ignore[invalid-assignment]
    assert ToolLoopRunResult(status=ToolLoopRunStatus.MODEL_ERROR).succeeded is False
