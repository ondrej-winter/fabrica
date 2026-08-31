"""Tests for the explicit registered in-process tool adapter."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping

import pytest

from fabrica.features.agent_runtime.adapters.outbound.registered_tool import (
    AsyncRegisteredTool,
    RegisteredSkillToolPreparer,
    RegisteredTool,
    RegisteredToolExecutor,
    RegisteredToolHandler,
    SkillAssociatedRegisteredTool,
)
from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    RuntimeObservation,
    SelectedSkill,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    ToolArgumentValue,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolExecutionContext,
    ToolImageContent,
    ToolLoopLimits,
    ToolMutationGuarantee,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.use_cases import PrepareSkillTools


def test_registered_tool_executor_runs_explicit_synthetic_callable() -> None:
    tool = RegisteredTool(
        definition=ToolDefinition(name="lookup_note", description="Lookup a synthetic note"),
        handler=lambda arguments: f"note:{arguments['note_id']}",
    )
    executor = RegisteredToolExecutor((tool,))

    result = asyncio.run(
        executor.execute_tool(
            ToolCallRequest(call_id="call-1", tool_name="lookup_note", arguments={"note_id": "abc"}),
            ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=100),
            _NeverCancelledToolCancellationSignal(),
        ),
    )

    assert result == ToolCallResult(
        call_id="call-1",
        tool_name="lookup_note",
        status=ToolCallResultStatus.SUCCESS,
        result_text="note:abc",
    )
    assert executor.tool_definitions == (tool.definition,)


def test_async_registered_tool_contract_keeps_typed_handler_without_execution() -> None:
    called = False

    async def synthetic_tool(
        _arguments: Mapping[str, ToolArgumentValue],
        _context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        nonlocal called
        called = True
        return RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            result_text="ok",
        )

    tool = AsyncRegisteredTool(
        definition=ToolDefinition(name="async_lookup_note", description="Lookup a synthetic note asynchronously"),
        handler=synthetic_tool,
    )

    assert tool.definition.name == "async_lookup_note"
    assert called is False


def test_registered_tool_executor_runs_async_typed_tool_with_execution_context() -> None:
    contexts: list[ToolExecutionContext] = []

    async def synthetic_tool(
        _arguments: Mapping[str, ToolArgumentValue],
        context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        contexts.append(context)
        return RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            result_text="ok",
        )

    executor = RegisteredToolExecutor(
        (
            AsyncRegisteredTool(
                definition=ToolDefinition(
                    name="async_lookup_note", description="Lookup a synthetic note asynchronously"
                ),
                handler=synthetic_tool,
            ),
        ),
    )

    result = asyncio.run(
        executor.execute_tool(
            ToolCallRequest(call_id="call-1", tool_name="async_lookup_note", arguments={"note_id": "abc"}),
            ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=100),
            _NeverCancelledToolCancellationSignal(),
        ),
    )

    assert result.status is ToolCallResultStatus.SUCCESS
    assert result.result_text is not None
    assert '"status":"success"' in result.result_text
    assert contexts[0].call_id == "call-1"
    assert contexts[0].argument_digest.startswith("sha256:")


def test_registered_tool_executor_preserves_typed_ordered_content_parts() -> None:
    async def synthetic_tool(
        _arguments: Mapping[str, ToolArgumentValue],
        _context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        return RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            content=(
                ToolTextContent(text="first"),
                ToolImageContent(data=b"\x89PNG\r\n\x1a\nimage", media_type="image/png"),
                ToolTextContent(text="last"),
            ),
        )

    result = asyncio.run(
        RegisteredToolExecutor(
            (
                AsyncRegisteredTool(
                    definition=ToolDefinition(name="read_files", description="Read synthetic files"),
                    handler=synthetic_tool,
                ),
            ),
        ).execute_tool(
            ToolCallRequest(call_id="call-1", tool_name="read_files"),
            ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=1_000),
            _NeverCancelledToolCancellationSignal(),
        ),
    )

    assert result.status is ToolCallResultStatus.SUCCESS
    assert tuple(type(part) for part in result.content) == (ToolTextContent, ToolImageContent, ToolTextContent)


def test_registered_tool_executor_preserves_96000_character_multipart_typed_outcome_without_result_text() -> None:
    escape_heavy_result = '"' * 96_000

    async def synthetic_tool(
        _arguments: Mapping[str, ToolArgumentValue],
        _context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        return RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            content=(
                ToolTextContent(text=escape_heavy_result[:48_000]),
                ToolTextContent(text=escape_heavy_result[48_000:]),
            ),
        )

    result = asyncio.run(
        RegisteredToolExecutor(
            (
                AsyncRegisteredTool(
                    definition=ToolDefinition(name="run_commands", description="Run synthetic commands"),
                    handler=synthetic_tool,
                ),
            ),
        ).execute_tool(
            ToolCallRequest(call_id="call-1", tool_name="run_commands"),
            ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=1),
            _NeverCancelledToolCancellationSignal(),
        ),
    )

    assert result.status is ToolCallResultStatus.SUCCESS
    assert result.result_text is None
    assert tuple(part.text for part in result.content if isinstance(part, ToolTextContent)) == (
        escape_heavy_result[:48_000],
        escape_heavy_result[48_000:],
    )
    assert sum(len(part.text) for part in result.content if isinstance(part, ToolTextContent)) == len(
        escape_heavy_result
    )


def test_registered_tool_executor_maps_async_rejection_to_recoverable_result() -> None:
    async def reject_tool(
        _arguments: Mapping[str, ToolArgumentValue],
        _context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        return RegisteredToolOutcome.recoverable_rejection(
            error_code="HUNK_CONTEXT_NOT_FOUND",
            error_message="context not found",
        )

    result = _execute_async_tool_with_handler(reject_tool)

    assert result.status is ToolCallResultStatus.REJECTED
    assert result.result_text is not None
    assert '"status":"rejected"' in result.result_text
    assert '"mutation_guarantee":"no_mutation"' in result.result_text


def test_registered_tool_executor_maps_async_fatal_outcome_to_stop_disposition() -> None:
    async def fail_tool(
        _arguments: Mapping[str, ToolArgumentValue],
        _context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        return RegisteredToolOutcome.fatal_runtime_stop(
            error_code="ROLLBACK_FAILED",
            mutation_guarantee=ToolMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
            error_message="rollback failed",
        )

    result = _execute_async_tool_with_handler(fail_tool)

    assert result.status is ToolCallResultStatus.TOOL_FAILURE
    assert result.runtime_disposition is not None
    assert result.result_text is not None
    assert '"fatal":true' in result.result_text


def test_registered_tool_executor_fails_closed_for_unknown_tool() -> None:
    executor = RegisteredToolExecutor()

    result = asyncio.run(
        executor.execute_tool(
            ToolCallRequest(call_id="call-1", tool_name="missing_tool"),
            ToolLoopLimits(),
            _NeverCancelledToolCancellationSignal(),
        ),
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
    def reject_arguments(_arguments: Mapping[str, ToolArgumentValue]) -> str:
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
    def time_out(_arguments: Mapping[str, ToolArgumentValue]) -> str:
        msg = "private timeout detail"
        raise TimeoutError(msg)

    result = _execute_tool_with_handler(time_out)

    assert result.status is ToolCallResultStatus.TIMEOUT
    assert result.error_message == "registered tool execution timed out"
    assert "private timeout detail" not in str(result)


def test_registered_tool_executor_maps_runtime_error_to_tool_failure() -> None:
    def fail(_arguments: Mapping[str, ToolArgumentValue]) -> str:
        msg = "private failure detail"
        raise RuntimeError(msg)

    result = _execute_tool_with_handler(fail)

    assert result.status is ToolCallResultStatus.TOOL_FAILURE
    assert result.error_message == "registered tool execution failed"
    assert "private failure detail" not in str(result)


def test_registered_tool_executor_maps_unexpected_exception_to_tool_failure() -> None:
    def fail(_arguments: Mapping[str, ToolArgumentValue]) -> str:
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

    def synthetic_tool(_arguments: Mapping[str, ToolArgumentValue]) -> str:
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

    def synthetic_tool(_arguments: Mapping[str, ToolArgumentValue]) -> str:
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
    return asyncio.run(
        executor.execute_tool(
            ToolCallRequest(call_id="call-1", tool_name="lookup_note"),
            limits or ToolLoopLimits(),
            _NeverCancelledToolCancellationSignal(),
        ),
    )


def _execute_async_tool_with_handler(
    handler: Callable[[Mapping[str, ToolArgumentValue], ToolExecutionContext], Awaitable[RegisteredToolOutcome]],
) -> ToolCallResult:
    executor = RegisteredToolExecutor(
        (
            AsyncRegisteredTool(
                definition=ToolDefinition(name="apply_patch", description="Apply a synthetic patch"),
                handler=handler,
            ),
        ),
    )
    return asyncio.run(
        executor.execute_tool(
            ToolCallRequest(call_id="call-1", tool_name="apply_patch"),
            ToolLoopLimits(max_tool_iterations=1, max_tool_result_chars=500),
            _NeverCancelledToolCancellationSignal(),
        ),
    )


class _NeverCancelledToolCancellationSignal:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        msg = "test signal is never cancelled"
        raise AssertionError(msg)
