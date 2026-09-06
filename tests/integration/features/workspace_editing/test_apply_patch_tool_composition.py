"""Offline, non-production tests for injected apply-patch tool-loop composition."""

import asyncio
import json
from dataclasses import dataclass, field

from fabrica.bootstrap import create_apply_patch_registered_tool_adapter, create_tool_loop_runtime
from fabrica.features.agent_runtime.application.dtos import (
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
from fabrica.features.workspace_editing.adapters.inbound.registered_tool import APPLY_PATCH_TOOL_NAME
from fabrica.features.workspace_editing.application.dtos import (
    PatchExecutionContext,
    PatchLimits,
    PatchMutationGuarantee,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from tests.integration.support.agent_runtime_tool_loop import SingleToolCallThenFinalModel

PLAN_DIGEST = "sha256:" + "c" * 64
EXPECTED_TOOL_LOOP_TURN_COUNT = 2


@dataclass(slots=True)
class _ScriptedApplyPatchToolAwareModel:
    """Return a fixed sequence of model responses for runtime-ledger scenarios."""

    responses: list[ToolAwareModelResponse]
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
        """Return the next deterministic model response."""
        del cancellation
        self.calls.append((command, available_tools, tool_results))
        return self.responses.pop(0)


def test_apply_patch_tool_helper_composes_explicit_use_case_without_mutating_during_construction() -> None:
    model = SingleToolCallThenFinalModel(
        ToolCallRequest(
            call_id="call-1",
            tool_name=APPLY_PATCH_TOOL_NAME,
            arguments={"input": "*** Begin Patch\n*** End Patch"},
        )
    )
    use_case = _FakeApplyPatch(_committed_result())

    tool = create_apply_patch_registered_tool_adapter(use_case, limits=PatchLimits(max_output_chars=500))
    runtime = create_tool_loop_runtime(
        model=model,
        tools=(tool,),
        limits=ToolLoopLimits(max_tool_iterations=2, max_tool_result_chars=500),
    )

    assert tuple(tool_definition.name for tool_definition in runtime.available_tools) == (APPLY_PATCH_TOOL_NAME,)
    assert use_case.calls == ()
    assert model.calls == []

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Apply the patch.")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert len(result.tool_results) == 1
    assert result.tool_results[0].result_text is not None
    tool_result_payload = json.loads(result.tool_results[0].result_text)
    assert tool_result_payload["details"]["patch_status"] == "committed"
    assert tool_result_payload["mutation_guarantee"] == "committed"
    assert tool_result_payload["status"] == "success"
    assert result.output_text is not None
    assert result.output_text.startswith("final:")
    assert len(use_case.calls) == 1
    patch_text, patch_limits, execution = use_case.calls[0]
    assert patch_text == "*** Begin Patch\n*** End Patch"
    assert patch_limits == PatchLimits(max_output_chars=500)
    assert execution is not None
    assert model.calls[0][1] == runtime.available_tools
    assert model.calls[1][2] == result.tool_results


def test_apply_patch_tool_loop_continues_after_recoverable_patch_rejection() -> None:
    model = SingleToolCallThenFinalModel(
        ToolCallRequest(
            call_id="call-1",
            tool_name=APPLY_PATCH_TOOL_NAME,
            arguments={"input": "*** Begin Patch\n*** End Patch"},
        )
    )
    use_case = _FakeApplyPatch(_rejected_result())
    tool = create_apply_patch_registered_tool_adapter(use_case)
    runtime = create_tool_loop_runtime(model=model, tools=(tool,), limits=ToolLoopLimits(max_tool_iterations=2))

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Apply the patch.")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert len(result.tool_results) == 1
    assert result.tool_results[0].status is ToolCallResultStatus.REJECTED
    assert result.output_text is not None
    assert result.output_text.startswith("final:")
    assert len(model.calls) == EXPECTED_TOOL_LOOP_TURN_COUNT
    assert model.calls[1][2] == result.tool_results


def test_apply_patch_tool_loop_stops_after_fatal_mutation_state() -> None:
    model = SingleToolCallThenFinalModel(
        ToolCallRequest(
            call_id="call-1",
            tool_name=APPLY_PATCH_TOOL_NAME,
            arguments={"input": "*** Begin Patch\n*** End Patch"},
        )
    )
    use_case = _FakeApplyPatch(_indeterminate_result())
    tool = create_apply_patch_registered_tool_adapter(use_case)
    runtime = create_tool_loop_runtime(model=model, tools=(tool,), limits=ToolLoopLimits(max_tool_iterations=2))

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Apply the patch.")))

    assert result.status is ToolLoopRunStatus.TOOL_FAILURE
    assert len(result.tool_results) == 1
    assert result.tool_results[0].status is ToolCallResultStatus.TOOL_FAILURE
    assert result.output_text is None
    assert len(model.calls) == 1


def test_apply_patch_tool_loop_replays_duplicate_delivery_without_reapplying_patch() -> None:
    patch_input = "*** Begin Patch\n*** End Patch"
    duplicate_call = ToolCallRequest(
        call_id="call-1",
        tool_name=APPLY_PATCH_TOOL_NAME,
        arguments={"input": patch_input},
    )
    model = _ScriptedApplyPatchToolAwareModel(
        responses=[
            ToolAwareModelResponse(tool_calls=(duplicate_call,)),
            ToolAwareModelResponse(tool_calls=(duplicate_call,)),
            ToolAwareModelResponse(output_text="done"),
        ]
    )
    use_case = _FakeApplyPatch(_committed_result())
    tool = create_apply_patch_registered_tool_adapter(use_case)
    runtime = create_tool_loop_runtime(model=model, tools=(tool,), limits=ToolLoopLimits(max_tool_iterations=2))

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Apply the patch once.")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text == "done"
    assert len(result.tool_results) == EXPECTED_TOOL_LOOP_TURN_COUNT
    assert result.tool_results[0] == result.tool_results[1]
    assert len(use_case.calls) == 1
    assert use_case.calls[0][0] == patch_input
    assert model.calls[2][2] == result.tool_results


def test_apply_patch_tool_loop_rejects_conflicting_duplicate_call_id_before_reapplying_patch() -> None:
    initial_call = ToolCallRequest(
        call_id="call-1",
        tool_name=APPLY_PATCH_TOOL_NAME,
        arguments={"input": "*** Begin Patch\n*** End Patch"},
    )
    conflicting_call = ToolCallRequest(
        call_id="call-1",
        tool_name=APPLY_PATCH_TOOL_NAME,
        arguments={"input": "*** Begin Patch\n*** Add File: new.py\n+value = 1\n*** End Patch"},
    )
    model = _ScriptedApplyPatchToolAwareModel(
        responses=[
            ToolAwareModelResponse(tool_calls=(initial_call,)),
            ToolAwareModelResponse(tool_calls=(conflicting_call,)),
        ]
    )
    use_case = _FakeApplyPatch(_committed_result())
    tool = create_apply_patch_registered_tool_adapter(use_case)
    runtime = create_tool_loop_runtime(model=model, tools=(tool,), limits=ToolLoopLimits(max_tool_iterations=2))

    result = asyncio.run(runtime.run(LocalAgentRunCommand(prompt="Apply the patch once.")))

    assert result.status is ToolLoopRunStatus.INVALID_TOOL_REQUEST
    assert len(result.tool_results) == 1
    assert len(use_case.calls) == 1
    assert use_case.calls[0][0] == initial_call.arguments["input"]
    assert result.observations[-1].message == "tool loop rejected duplicate tool call id with conflicting request"
    assert result.observations[-1].metadata == {"tool_call_id": "call-1"}


def _committed_result() -> PatchResult:
    return PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=PLAN_DIGEST,
    )


def _rejected_result() -> PatchResult:
    error = patch_error("SOURCE_NOT_FOUND", message="source not found")
    return PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=error.mutation_guarantee,
        error=error,
    )


def _indeterminate_result() -> PatchResult:
    error = patch_error(
        "INDETERMINATE_COMMIT_STATE",
        message="commit state is unknown",
        metadata={"plan_digest": PLAN_DIGEST},
    )
    return PatchResult(
        status=PatchResultStatus.INDETERMINATE_COMMIT_STATE,
        mutation_guarantee=error.mutation_guarantee,
        plan_digest=PLAN_DIGEST,
        error=error,
    )


@dataclass(slots=True)
class _FakeApplyPatch:
    result: PatchResult
    calls: tuple[tuple[str, PatchLimits | None, PatchExecutionContext | None], ...] = ()

    async def apply(
        self,
        patch_text: str,
        limits: PatchLimits | None = None,
        execution: PatchExecutionContext | None = None,
    ) -> PatchResult:
        self.calls = (*self.calls, (patch_text, limits, execution))
        return self.result
