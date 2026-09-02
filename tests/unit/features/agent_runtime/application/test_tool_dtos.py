"""Tests for tool-loop application DTO contracts."""

from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_MAX_TOOL_CALLS_PER_TURN,
    MAX_APPLY_PATCH_INPUT_CHARS,
    MAX_TOOL_ARGUMENT_NESTING_DEPTH,
    MAX_TOOL_ARGUMENT_SEQUENCE_ENTRIES,
    MAX_TOOL_ARGUMENT_STRING_CHARS,
    MAX_TOOL_CALL_ID_CHARS,
    MAX_TOOL_CONTENT_PARTS,
    MAX_TOOL_CONTENT_TEXT_CHARS,
    MAX_TOOL_DESCRIPTION_CHARS,
    MAX_TOOL_ERROR_MESSAGE_CHARS,
    MAX_TOOL_IMAGE_BYTES,
    MAX_TOOL_NAME_CHARS,
    MAX_TOOL_RESPONSE_TEXT_CHARS,
    RegisteredToolOutcome,
    RuntimeObservation,
    ToolArgumentValue,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolContentPart,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionPhaseDeadline,
    ToolExecutionRuntimeDisposition,
    ToolImageContent,
    ToolLoopLimits,
    ToolLoopRunResult,
    ToolLoopRunStatus,
    ToolMutationGuarantee,
    ToolOutcomeStatus,
    ToolTextContent,
    canonical_tool_arguments_digest,
    canonical_tool_arguments_json,
)
from fabrica.features.agent_runtime.application.dtos.runtime import MAX_CONTEXT_TEXT_CHARS

EXPECTED_MAX_TOOL_ITERATIONS = 2
EXPECTED_MAX_TOOL_RESULT_CHARS = 20


class NeverCancelledSignal:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        return None


def test_tool_status_values_match_normalized_contracts() -> None:
    assert {status.value for status in ToolCallResultStatus} == {
        "success",
        "rejected",
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


def test_tool_execution_context_carries_digest_deadlines_and_cancellation() -> None:
    digest = canonical_tool_arguments_digest({"path": "src/example.py", "limit": 3})
    deadline = ToolExecutionPhaseDeadline(
        phase="planning",
        deadline_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=30),
    )

    context = ToolExecutionContext(
        call_id="call-1",
        argument_digest=digest,
        cancellation=NeverCancelledSignal(),
        phase_deadlines=(deadline,),
    )

    assert context.call_id == "call-1"
    assert context.argument_digest.startswith("sha256:")
    assert context.phase_deadline("planning") == deadline.deadline_at
    assert context.cancellation.is_cancelled is False
    with pytest.raises(FrozenInstanceError):
        context.call_id = "changed"  # ty: ignore[invalid-assignment]
    with pytest.raises(ValueError, match="timezone-aware"):
        ToolExecutionPhaseDeadline(phase="planning", deadline_at=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None))


def test_tool_argument_digest_uses_canonical_json() -> None:
    left = {"b": (2, {"nested": "safe"}), "a": "safe"}
    right = {"a": "safe", "b": (2, {"nested": "safe"})}

    assert canonical_tool_arguments_json(left) == '{"a":"safe","b":[2,{"nested":"safe"}]}'
    assert canonical_tool_arguments_digest(left) == canonical_tool_arguments_digest(right)
    with pytest.raises(ValueError, match="finite"):
        canonical_tool_arguments_json({"bad": float("inf")})


@pytest.mark.parametrize("input_length", [0, 1, 20_000, 20_001, 262_144])
def test_tool_call_request_accepts_apply_patch_input_through_public_limit(input_length: int) -> None:
    request = ToolCallRequest(
        call_id="call-1",
        tool_name="apply_patch",
        arguments={"input": "x" * input_length},
    )

    assert request.arguments["input"] == "x" * input_length
    assert canonical_tool_arguments_digest(request.arguments, tool_name=request.tool_name).startswith("sha256:")


def test_tool_call_request_rejects_apply_patch_input_over_public_limit() -> None:
    with pytest.raises(ValueError, match="apply_patch input exceeds"):
        ToolCallRequest(
            call_id="call-1",
            tool_name="apply_patch",
            arguments={"input": "x" * (MAX_APPLY_PATCH_INPUT_CHARS + 1)},
        )


def test_tool_call_request_retains_generic_string_limit_for_other_tools() -> None:
    with pytest.raises(ValueError, match="tool argument strings exceed"):
        ToolCallRequest(
            call_id="call-1",
            tool_name="lookup_note",
            arguments={"input": "x" * (MAX_TOOL_ARGUMENT_STRING_CHARS + 1)},
        )


def test_tool_call_request_normalizes_bounded_immutable_recursive_json_arguments() -> None:
    request = ToolCallRequest(
        call_id="call-1",
        tool_name="lookup_note",
        arguments={"files": ({"path": "src/example.py", "lines": (1, 3)},)},
    )

    assert request.arguments == {"files": ({"path": "src/example.py", "lines": (1, 3)},)}
    with pytest.raises(TypeError):
        cast("dict[str, object]", request.arguments)["files"] = ()
    with pytest.raises(ValueError, match="nesting depth"):
        ToolCallRequest(
            call_id="call-2",
            tool_name="lookup_note",
            arguments=cast(
                "Mapping[str, ToolArgumentValue]",
                {"nested": _nested_tuple(MAX_TOOL_ARGUMENT_NESTING_DEPTH + 1)},
            ),
        )
    with pytest.raises(ValueError, match="sequence"):
        ToolCallRequest(
            call_id="call-3",
            tool_name="lookup_note",
            arguments={"items": tuple(range(MAX_TOOL_ARGUMENT_SEQUENCE_ENTRIES + 1))},
        )
    with pytest.raises(TypeError, match="immutable JSON"):
        ToolCallRequest(
            call_id="call-4",
            tool_name="lookup_note",
            arguments=cast("Mapping[str, ToolArgumentValue]", {"items": ["mutable"]}),
        )


@pytest.mark.parametrize(
    ("arguments", "error_type", "message"),
    [
        (cast("Mapping[str, ToolArgumentValue]", {1: "value"}), TypeError, "keys must be strings"),
        ({"x" * (MAX_TOOL_ARGUMENT_STRING_CHARS + 1): "value"}, ValueError, "keys exceed"),
        ({"value": "x" * (MAX_TOOL_ARGUMENT_STRING_CHARS + 1)}, ValueError, "strings exceed"),
        (cast("Mapping[str, ToolArgumentValue]", {"value": object()}), TypeError, "immutable JSON"),
    ],
)
def test_tool_call_request_rejects_invalid_recursive_json_values(
    arguments: Mapping[str, ToolArgumentValue], error_type: type[Exception], message: str
) -> None:
    with pytest.raises(error_type, match=message):
        ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments=arguments)


def test_tool_content_parts_enforce_provider_neutral_bounds() -> None:
    assert ToolTextContent(text="x" * MAX_TOOL_CONTENT_TEXT_CHARS).text == "x" * MAX_TOOL_CONTENT_TEXT_CHARS
    with pytest.raises(ValueError, match="text content exceeds"):
        ToolTextContent(text="x" * (MAX_TOOL_CONTENT_TEXT_CHARS + 1))
    with pytest.raises(ValueError, match="must not be empty"):
        ToolImageContent(data=b"", media_type="image/png")
    with pytest.raises(ValueError, match="image bound"):
        ToolImageContent(data=b"x" * (MAX_TOOL_IMAGE_BYTES + 1), media_type="image/png")
    with pytest.raises(ValueError, match="media type is unsupported"):
        ToolImageContent(data=b"image", media_type="image/svg+xml")
    with pytest.raises(ValueError, match="content exceeds"):
        ToolCallResult(
            call_id="call-1",
            tool_name="read_files",
            status=ToolCallResultStatus.SUCCESS,
            content=tuple(ToolTextContent(text="part") for _ in range(MAX_TOOL_CONTENT_PARTS + 1)),
        )
    with pytest.raises(TypeError, match="text or image parts"):
        ToolCallResult(
            call_id="call-1",
            tool_name="read_files",
            status=ToolCallResultStatus.SUCCESS,
            content=cast("tuple[ToolContentPart, ...]", ("invalid",)),
        )


def test_registered_tool_outcome_invariants_distinguish_runtime_disposition() -> None:
    success = RegisteredToolOutcome.model_continue_success(
        mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
        result_text="ok",
    )
    rejection = RegisteredToolOutcome.recoverable_rejection(
        error_code="HUNK_CONTEXT_NOT_FOUND",
        error_message="context not found",
    )
    fatal = RegisteredToolOutcome.fatal_runtime_stop(
        error_code="ROLLBACK_FAILED",
        mutation_guarantee=ToolMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
        error_message="rollback failed",
    )

    assert success.status is ToolOutcomeStatus.SUCCESS
    assert success.runtime_disposition is ToolExecutionRuntimeDisposition.CONTINUE_MODEL
    assert rejection.status is ToolOutcomeStatus.REJECTED
    assert rejection.retryable is True
    assert fatal.status is ToolOutcomeStatus.FATAL
    assert fatal.runtime_disposition is ToolExecutionRuntimeDisposition.STOP_RUNTIME
    with pytest.raises(ValueError, match="success outcomes must not include an error code"):
        RegisteredToolOutcome(
            status=ToolOutcomeStatus.SUCCESS,
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            error_code="INVALID_PATCH",
        )


def test_registered_tool_outcome_bounding_preserves_required_fields() -> None:
    outcome = RegisteredToolOutcome.recoverable_rejection(
        error_code="INVALID_PATCH",
        error_message="invalid patch",
        details={"excerpt": "x" * 1_000},
    )

    serialized = outcome.to_bounded_json(max_chars=160)

    assert '"status":"rejected"' in serialized
    assert '"mutation_guarantee":"no_mutation"' in serialized
    assert '"code":"INVALID_PATCH"' in serialized
    assert '"retryable":true' in serialized
    assert '"fatal":false' in serialized
    assert "excerpt" not in serialized
    with pytest.raises(ValueError, match="mandatory tool outcome fields"):
        outcome.to_bounded_json(max_chars=10)


def test_tool_result_preserves_ordered_provider_neutral_text_and_image_content() -> None:
    image = ToolImageContent(data=b"\x89PNG\r\n\x1a\nimage", media_type="image/png")
    result = ToolCallResult(
        call_id="call-1",
        tool_name="read_files",
        status=ToolCallResultStatus.SUCCESS,
        content=(ToolTextContent(text="src/example.py"), image, ToolTextContent(text="done")),
    )

    assert result.content == (ToolTextContent(text="src/example.py"), image, ToolTextContent(text="done"))
    assert "image" not in RegisteredToolOutcome.model_continue_success(
        mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
        content=result.content,
    ).to_bounded_json(max_chars=1_000)


def _nested_tuple(depth: int) -> tuple[object, ...]:
    value: tuple[object, ...] = ()
    for _ in range(depth):
        value = (value,)
    return value
