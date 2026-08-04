"""Tests for the explicit registered in-process tool adapter."""

from collections.abc import Mapping

import pytest

from fabrica.features.agent_runtime.adapters.outbound.registered_tool import (
    RegisteredSkillToolPreparer,
    RegisteredTool,
    RegisteredToolExecutor,
    RegisteredToolHandler,
    SkillAssociatedRegisteredTool,
)
from fabrica.features.agent_runtime.application.dtos import (
    RuntimeObservation,
    SafeRuntimeMetadataValue,
    SelectedSkill,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolLoopLimits,
)
from fabrica.features.agent_runtime.application.use_cases import PrepareSkillTools


def test_registered_tool_executor_runs_explicit_synthetic_callable() -> None:
    tool = RegisteredTool(
        definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
        handler=lambda arguments: f"note:{arguments['note_id']}",
    )
    executor = RegisteredToolExecutor((tool,))

    result = executor.execute_tool(
        ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"note_id": "abc"}),
        ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=100),
    )

    assert result == ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=ToolCallResultStatus.SUCCESS,
        result_text="note:abc",
    )
    assert executor.tool_definitions == (tool.definition,)


def test_registered_tool_executor_fails_closed_for_unknown_tool() -> None:
    executor = RegisteredToolExecutor()

    result = executor.execute_tool(
        ToolCallRequest(call_id="call-1", tool_name="missing_tool"),
        ToolLoopLimits(),
    )

    assert result.status is ToolCallResultStatus.UNKNOWN_TOOL
    assert result.error_message == "requested tool is not registered"
    assert result.observations == (
        RuntimeObservation(
            message="requested tool is not registered",
            metadata={"tool_name": "missing_tool", "category": "unknown_tool"},
        ),
    )


def test_registered_tool_executor_maps_value_error_to_invalid_arguments() -> None:
    def reject_arguments(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        msg = "private validation detail"
        raise ValueError(msg)

    result = _execute_tool_with_handler(reject_arguments)

    assert result.status is ToolCallResultStatus.INVALID_ARGUMENTS
    assert result.error_message == "registered tool rejected arguments"
    assert "private validation detail" not in str(result)


def test_registered_tool_executor_maps_missing_argument_to_invalid_arguments() -> None:
    result = _execute_tool_with_handler(lambda arguments: f"note:{arguments['missing']}")

    assert result.status is ToolCallResultStatus.INVALID_ARGUMENTS
    assert result.error_message == "registered tool rejected arguments"


def test_registered_tool_executor_maps_timeout_error_to_timeout() -> None:
    def time_out(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        msg = "private timeout detail"
        raise TimeoutError(msg)

    result = _execute_tool_with_handler(time_out)

    assert result.status is ToolCallResultStatus.TIMEOUT
    assert result.error_message == "registered tool execution timed out"
    assert "private timeout detail" not in str(result)


def test_registered_tool_executor_maps_runtime_error_to_tool_failure() -> None:
    def fail(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        msg = "private failure detail"
        raise RuntimeError(msg)

    result = _execute_tool_with_handler(fail)

    assert result.status is ToolCallResultStatus.TOOL_FAILURE
    assert result.error_message == "registered tool execution failed"
    assert "private failure detail" not in str(result)


def test_registered_tool_executor_maps_unexpected_exception_to_tool_failure() -> None:
    def fail(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        msg = "private os detail"
        raise OSError(msg)

    result = _execute_tool_with_handler(fail)

    assert result.status is ToolCallResultStatus.TOOL_FAILURE
    assert result.error_message == "registered tool execution failed"
    assert "private os detail" not in str(result)


def test_registered_tool_executor_bounds_oversized_output() -> None:
    result = _execute_tool_with_handler(
        lambda _arguments: "abcdef",
        limits=ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=3),
    )

    assert result == ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=ToolCallResultStatus.LIMIT_EXCEEDED,
        result_text="abc",
        error_message="registered tool result exceeded output limit",
        observations=(
            RuntimeObservation(
                message="registered tool result text was truncated",
                metadata={"tool_name": "lookup_note", "max_chars": 3},
            ),
        ),
    )


def test_constructing_registered_tool_executor_does_not_call_registered_tool() -> None:
    called = False

    def synthetic_tool(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        nonlocal called
        called = True
        return "called"

    RegisteredToolExecutor(
        (
            RegisteredTool(
                definition=ToolDefinition(name="synthetic_tool", description="Synthetic tool"),
                handler=synthetic_tool,
            ),
        ),
    )

    assert called is False


def test_registered_tool_executor_rejects_duplicate_tool_names() -> None:
    first = RegisteredTool(
        definition=ToolDefinition(name="synthetic_tool", description="First synthetic tool"),
        handler=lambda _arguments: "first",
    )
    second = RegisteredTool(
        definition=ToolDefinition(name="synthetic_tool", description="Second synthetic tool"),
        handler=lambda _arguments: "second",
    )

    with pytest.raises(ValueError, match="registered tool names must be unique"):
        RegisteredToolExecutor((first, second))


def test_registered_skill_tool_preparer_maps_explicit_registration_to_declaration() -> None:
    registered_tool = RegisteredTool(
        definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
        handler=lambda _arguments: "note:abc",
    )
    preparer = RegisteredSkillToolPreparer(
        (
            SkillAssociatedRegisteredTool(
                skill_id="python-testing",
                registered_tool=registered_tool,
                label="Lookup note",
                metadata={"capability": "lookup"},
            ),
        ),
    )

    result = PrepareSkillTools(preparer).prepare(
        SkillToolPreparationCommand(selected_skills=(SelectedSkill(skill_id="python-testing"),)),
    )

    assert len(result.declarations) == 1
    declaration = result.declarations[0]
    assert declaration.skill_id == "python-testing"
    assert declaration.status is SkillToolExposureStatus.REGISTERED
    assert declaration.tool == registered_tool.definition
    assert declaration.label == "Lookup note"
    assert declaration.metadata == {"capability": "lookup"}
    assert result.tool_definitions == (registered_tool.definition,)


def test_registered_skill_tool_preparer_does_not_call_registered_tool_during_preparation() -> None:
    called = False

    def synthetic_tool(_arguments: Mapping[str, SafeRuntimeMetadataValue]) -> str:
        nonlocal called
        called = True
        return "called"

    preparer = RegisteredSkillToolPreparer(
        (
            SkillAssociatedRegisteredTool(
                skill_id="python-testing",
                registered_tool=RegisteredTool(
                    definition=ToolDefinition(name="synthetic_tool", description="Synthetic tool"),
                    handler=synthetic_tool,
                ),
            ),
        ),
    )

    result = preparer.prepare(
        SkillToolPreparationCommand(selected_skills=(SelectedSkill(skill_id="python-testing"),)),
    )

    assert result.tool_definitions == (ToolDefinition(name="synthetic_tool", description="Synthetic tool"),)
    assert called is False


def test_registered_skill_tool_preparer_leaves_unknown_selection_to_application_normalization() -> None:
    preparer = RegisteredSkillToolPreparer(
        (
            SkillAssociatedRegisteredTool(
                skill_id="unselected",
                registered_tool=RegisteredTool(
                    definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
                    handler=lambda _arguments: "note:abc",
                ),
            ),
        ),
    )

    result = PrepareSkillTools(preparer).prepare(
        SkillToolPreparationCommand(selected_skills=(SelectedSkill(skill_id="python-testing"),)),
    )

    assert result.declarations[0].status is SkillToolExposureStatus.UNKNOWN_SELECTION
    assert result.declarations[0].tool is None
    assert result.tool_definitions == ()


def test_registered_skill_tool_preparer_leaves_duplicate_names_to_application_normalization() -> None:
    first = SkillAssociatedRegisteredTool(
        skill_id="python-testing",
        registered_tool=RegisteredTool(
            definition=ToolDefinition(name="lookup_note", description="Lookup note from first skill"),
            handler=lambda _arguments: "first",
        ),
    )
    second = SkillAssociatedRegisteredTool(
        skill_id="hexagonal-architecture",
        registered_tool=RegisteredTool(
            definition=ToolDefinition(name="lookup_note", description="Lookup note from second skill"),
            handler=lambda _arguments: "second",
        ),
    )

    result = PrepareSkillTools(RegisteredSkillToolPreparer((first, second))).prepare(
        SkillToolPreparationCommand(
            selected_skills=(
                SelectedSkill(skill_id="python-testing"),
                SelectedSkill(skill_id="hexagonal-architecture"),
            ),
        ),
    )

    assert result.declarations[0].status is SkillToolExposureStatus.REGISTERED
    assert result.declarations[1].status is SkillToolExposureStatus.DUPLICATE
    assert result.declarations[1].tool is None
    assert result.tool_definitions == (first.registered_tool.definition,)


def _execute_tool_with_handler(
    handler: RegisteredToolHandler,
    *,
    limits: ToolLoopLimits | None = None,
) -> ToolCallResult:
    executor = RegisteredToolExecutor(
        (
            RegisteredTool(
                definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
                handler=handler,
            ),
        ),
    )
    return executor.execute_tool(
        ToolCallRequest(call_id="call-1", tool_name="lookup_note"),
        limits or ToolLoopLimits(),
    )
