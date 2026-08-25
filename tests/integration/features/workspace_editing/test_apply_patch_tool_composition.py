"""Offline integration tests for explicit apply-patch tool-loop composition."""

import asyncio
import json
from dataclasses import dataclass, field

from fabrica.bootstrap import create_apply_patch_registered_tool_adapter, create_tool_loop_runtime
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunStatus,
)
from fabrica.features.workspace_editing.adapters.inbound.registered_tool import APPLY_PATCH_TOOL_NAME
from fabrica.features.workspace_editing.application.dtos import (
    PatchLimits,
    PatchMutationGuarantee,
    PatchResult,
    PatchResultStatus,
)

PLAN_DIGEST = "sha256:" + "c" * 64


@dataclass(slots=True)
class ApplyPatchToolAwareModel:
    """Fake model that requests the explicitly composed apply-patch tool once."""

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
        """Request apply-patch, then return the tool result text."""
        del cancellation
        self.calls.append((command, available_tools, tool_results))
        if not tool_results:
            return ToolAwareModelResponse(
                tool_calls=(
                    ToolCallRequest(
                        call_id="call-1",
                        tool_name=APPLY_PATCH_TOOL_NAME,
                        arguments={"input": "*** Begin Patch\n*** End Patch"},
                    ),
                ),
            )
        return ToolAwareModelResponse(output_text=f"final:{tool_results[0].result_text}")


def test_apply_patch_tool_helper_composes_explicit_use_case_without_mutating_during_construction() -> None:
    model = ApplyPatchToolAwareModel()
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
    assert use_case.calls == (("*** Begin Patch\n*** End Patch", PatchLimits(max_output_chars=500)),)
    assert model.calls[0][1] == runtime.available_tools
    assert model.calls[1][2] == result.tool_results


def _committed_result() -> PatchResult:
    return PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=PLAN_DIGEST,
    )


@dataclass(slots=True)
class _FakeApplyPatch:
    result: PatchResult
    calls: tuple[tuple[str, PatchLimits | None], ...] = ()

    async def apply(self, patch_text: str, limits: PatchLimits | None = None) -> PatchResult:
        self.calls = (*self.calls, (patch_text, limits))
        return self.result
