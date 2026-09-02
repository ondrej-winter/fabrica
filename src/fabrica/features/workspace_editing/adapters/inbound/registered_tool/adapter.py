"""Expose the canonical apply-patch use case as one model-facing registered tool."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolDefinition,
    ToolExecutionContext,
    ToolMutationGuarantee,
)
from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_editing.application.dtos import (
    DEFAULT_MAX_PATCH_OUTPUT_CHARS,
    PatchExecutionContext,
    PatchExecutionPhase,
    PatchLimits,
    PatchMutationGuarantee,
    PatchResult,
    PatchResultStatus,
    PatchRuntimeMapping,
)

if TYPE_CHECKING:
    from datetime import datetime

APPLY_PATCH_TOOL_NAME = "apply_patch"
APPLY_PATCH_TOOL_DESCRIPTION = """Apply context-based patches to UTF-8 text files in the workspace.

Pass the raw patch body directly in `input`.

Supported operations:
- *** Add File: <path>
- *** Update File: <path>
- *** Delete File: <path>
- *** Move to: <new-path> immediately after an Update File header

Use context lines with one leading space, deleted lines with -, and inserted
lines with +. Use @@ or @@ <anchor> to separate hunks. Use
@@ before <anchor> or @@ after <anchor> for insertion-only hunks.

Do not use line numbers. Prefer small, focused patches.

Add File and Move destinations automatically create missing parent directories
inside the workspace. Created directories are shown in the planned changes and
approval preview.

The full patch is planned and authorized before commit. If any hunk cannot be
matched safely, the patch is rejected and no intended changes are applied."""
APPLY_PATCH_TOOL_DEFINITION = ToolDefinition(
    name=APPLY_PATCH_TOOL_NAME,
    description=APPLY_PATCH_TOOL_DESCRIPTION,
    argument_schema={
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
    },
)


class PatchApplier(Protocol):
    """Application-compatible apply-patch boundary consumed by this adapter."""

    async def apply(
        self,
        patch_text: str,
        limits: PatchLimits | None = None,
        execution: PatchExecutionContext | None = None,
    ) -> PatchResult:
        """Apply one canonical patch body."""
        ...


@dataclass(frozen=True, slots=True)
class ApplyPatchRegisteredToolAdapter:
    """Map model tool arguments to the apply-patch application use case."""

    use_case: PatchApplier
    limits: PatchLimits | None = None

    async def handle(
        self,
        arguments: Mapping[str, ToolArgumentValue],
        context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        """Run one canonical patch request and return a typed runtime outcome."""
        input_value = arguments.get("input")
        if not isinstance(input_value, str):
            return RegisteredToolOutcome.recoverable_rejection(
                error_code="INVALID_ARGUMENTS",
                error_message="apply_patch requires a string `input` argument",
            )
        result = await self.use_case.apply(input_value, self.limits, _patch_execution_context(context))
        return patch_result_to_tool_outcome(result, limits=self.limits)


def create_apply_patch_registered_tool(
    use_case: PatchApplier, limits: PatchLimits | None = None
) -> AsyncRegisteredTool:
    """Create the sole model-facing registered tool for workspace mutation."""
    adapter = ApplyPatchRegisteredToolAdapter(use_case=use_case, limits=limits)
    return AsyncRegisteredTool(definition=APPLY_PATCH_TOOL_DEFINITION, handler=adapter.handle)


def patch_result_to_tool_outcome(result: PatchResult, *, limits: PatchLimits | None = None) -> RegisteredToolOutcome:
    """Translate application patch results into agent-runtime typed outcomes."""
    output_limit = limits.max_output_chars if limits is not None else DEFAULT_MAX_PATCH_OUTPUT_CHARS
    result_text = result.to_bounded_json(max_chars=output_limit)
    details = {"patch_status": result.status.value}
    if result.plan_digest is not None:
        details["plan_digest"] = result.plan_digest

    if result.status is PatchResultStatus.COMMITTED:
        return RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=_tool_mutation_guarantee(result.mutation_guarantee),
            result_text=result_text,
            details=details,
        )

    error_code = result.error.code if result.error is not None else result.status.value.upper()
    error_message = (
        result.error.message if result.error is not None and result.error.message is not None else result.status.value
    )
    if result.error is not None and result.error.runtime_mapping is PatchRuntimeMapping.FATAL:
        return RegisteredToolOutcome.fatal_runtime_stop(
            error_code=error_code,
            mutation_guarantee=_tool_mutation_guarantee(result.mutation_guarantee),
            error_message=error_message,
            details=details,
        )
    if result.mutation_guarantee in {
        PatchMutationGuarantee.REVERSIBLE_EFFECTS_RETAINED,
        PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
    }:
        return RegisteredToolOutcome.fatal_runtime_stop(
            error_code=error_code,
            mutation_guarantee=_tool_mutation_guarantee(result.mutation_guarantee),
            error_message=error_message,
            details=details,
        )
    return RegisteredToolOutcome.recoverable_rejection(
        error_code=error_code,
        error_message=error_message,
        details=details,
    )


def _tool_mutation_guarantee(guarantee: PatchMutationGuarantee) -> ToolMutationGuarantee:
    return ToolMutationGuarantee(guarantee.value)


def _patch_execution_context(context: ToolExecutionContext) -> PatchExecutionContext:
    deadlines: dict[PatchExecutionPhase, datetime] = {}
    for phase in PatchExecutionPhase:
        deadline = context.phase_deadline(phase.value)
        if deadline is not None:
            deadlines[phase] = deadline
    return PatchExecutionContext(cancellation=context.cancellation, phase_deadlines=deadlines)


__all__ = [
    "APPLY_PATCH_TOOL_DEFINITION",
    "APPLY_PATCH_TOOL_DESCRIPTION",
    "APPLY_PATCH_TOOL_NAME",
    "ApplyPatchRegisteredToolAdapter",
    "PatchApplier",
    "create_apply_patch_registered_tool",
    "patch_result_to_tool_outcome",
]
