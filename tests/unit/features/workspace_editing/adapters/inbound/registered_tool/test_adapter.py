"""Tests for the model-facing apply-patch registered-tool adapter."""

from asyncio import run
from dataclasses import dataclass
from datetime import UTC, datetime

from fabrica.features.agent_runtime.application.dtos import (
    ToolExecutionContext,
    ToolExecutionPhaseDeadline,
    ToolExecutionRuntimeDisposition,
    ToolMutationGuarantee,
    ToolOutcomeStatus,
)
from fabrica.features.workspace_editing.adapters.inbound.registered_tool import (
    APPLY_PATCH_TOOL_DEFINITION,
    APPLY_PATCH_TOOL_DESCRIPTION,
    APPLY_PATCH_TOOL_NAME,
    ApplyPatchRegisteredToolAdapter,
    create_apply_patch_registered_tool,
)
from fabrica.features.workspace_editing.adapters.inbound.registered_tool.adapter import patch_result_to_tool_outcome
from fabrica.features.workspace_editing.application.dtos import (
    PatchExecutionContext,
    PatchExecutionPhase,
    PatchLimits,
    PatchMutationGuarantee,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error

PLAN_DIGEST = "sha256:" + "a" * 64


def test_apply_patch_registered_tool_exposes_canonical_schema_and_description() -> None:
    tool = create_apply_patch_registered_tool(_FakeApplyPatch(_committed_result()))

    assert tool.definition == APPLY_PATCH_TOOL_DEFINITION
    assert tool.definition.name == APPLY_PATCH_TOOL_NAME
    assert tool.definition.argument_schema == {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "Raw canonical apply-patch body.",
                "minLength": 1,
                "maxLength": 262_144,
            }
        },
        "required": ("input",),
        "additionalProperties": False,
    }
    assert APPLY_PATCH_TOOL_DESCRIPTION.startswith("Apply context-based patches")
    assert "Pass the raw patch body directly in `input`." in APPLY_PATCH_TOOL_DESCRIPTION


def test_apply_patch_registered_tool_passes_string_input_to_use_case() -> None:
    use_case = _FakeApplyPatch(_committed_result())
    adapter = ApplyPatchRegisteredToolAdapter(use_case=use_case, limits=PatchLimits(max_output_chars=500))

    outcome = run(adapter.handle({"input": "*** Begin Patch\n*** End Patch"}, _context()))

    assert len(use_case.calls) == 1
    patch_text, limits, execution = use_case.calls[0]
    assert patch_text == "*** Begin Patch\n*** End Patch"
    assert limits == PatchLimits(max_output_chars=500)
    assert execution is not None
    assert execution.deadline_for(PatchExecutionPhase.PLANNING) == datetime(2026, 9, 2, tzinfo=UTC)
    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert outcome.mutation_guarantee is ToolMutationGuarantee.COMMITTED
    assert outcome.result_text is not None
    assert '"status":"committed"' in outcome.result_text


def test_apply_patch_registered_tool_rejects_missing_or_non_string_input_before_use_case() -> None:
    use_case = _FakeApplyPatch(_committed_result())
    adapter = ApplyPatchRegisteredToolAdapter(use_case=use_case)

    outcome = run(adapter.handle({"input": 123}, _context()))
    missing = run(adapter.handle({}, _context()))

    assert use_case.calls == ()
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_ARGUMENTS"
    assert missing.status is ToolOutcomeStatus.REJECTED


def test_patch_result_mapping_keeps_no_mutation_rejection_recoverable() -> None:
    error = patch_error("SOURCE_NOT_FOUND", message="source not found")
    result = PatchResult(status=PatchResultStatus.REJECTED, mutation_guarantee=error.mutation_guarantee, error=error)

    outcome = patch_result_to_tool_outcome(result)

    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.runtime_disposition is ToolExecutionRuntimeDisposition.CONTINUE_MODEL
    assert outcome.mutation_guarantee is ToolMutationGuarantee.NO_MUTATION
    assert outcome.error_code == "SOURCE_NOT_FOUND"
    assert outcome.error_message == "source not found"


def test_patch_result_mapping_stops_runtime_for_retained_reversible_effects() -> None:
    error = patch_error(
        "CREATED_DIRECTORY_RETAINED",
        message="directory retained",
        metadata={"path": "generated", "final_state": "retained_external_content"},
    )
    result = PatchResult(
        status=PatchResultStatus.RECOVERY_REQUIRED,
        mutation_guarantee=error.mutation_guarantee,
        error=error,
    )

    outcome = patch_result_to_tool_outcome(result)

    assert outcome.status is ToolOutcomeStatus.FATAL
    assert outcome.runtime_disposition is ToolExecutionRuntimeDisposition.STOP_RUNTIME
    assert outcome.mutation_guarantee is ToolMutationGuarantee.REVERSIBLE_EFFECTS_RETAINED
    assert outcome.error_code == "CREATED_DIRECTORY_RETAINED"


def test_patch_result_mapping_stops_runtime_for_partial_or_uncertain_mutation() -> None:
    error = patch_error(
        "INDETERMINATE_COMMIT_STATE",
        message="unknown",
        metadata={"plan_digest": PLAN_DIGEST},
    )
    result = PatchResult(
        status=PatchResultStatus.INDETERMINATE_COMMIT_STATE,
        mutation_guarantee=error.mutation_guarantee,
        plan_digest=PLAN_DIGEST,
        error=error,
    )

    outcome = patch_result_to_tool_outcome(result)

    assert outcome.status is ToolOutcomeStatus.FATAL
    assert outcome.runtime_disposition is ToolExecutionRuntimeDisposition.STOP_RUNTIME
    assert outcome.mutation_guarantee is ToolMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION
    assert outcome.details["plan_digest"] == PLAN_DIGEST


def _committed_result() -> PatchResult:
    return PatchResult(
        status=PatchResultStatus.COMMITTED,
        mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        plan_digest=PLAN_DIGEST,
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


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        call_id="call-1",
        argument_digest=PLAN_DIGEST,
        cancellation=_NeverCancelledToolCancellationSignal(),
        phase_deadlines=(
            ToolExecutionPhaseDeadline(
                phase=PatchExecutionPhase.PLANNING.value,
                deadline_at=datetime(2026, 9, 2, tzinfo=UTC),
            ),
        ),
    )


class _NeverCancelledToolCancellationSignal:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        msg = "test signal is never cancelled"
        raise AssertionError(msg)
