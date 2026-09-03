"""Expose terminal completion as the model-facing ``submit_and_exit`` tool."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    RUN_ID_CONTEXT_KEY,
    SUBMIT_AND_EXIT_TOOL_DEFINITION,
    CompletionOutcome,
    CompletionSubmission,
    CompletionVerification,
    RegisteredToolOutcome,
    SubmitRunCompletionCommand,
    ToolArgumentValue,
    ToolExecutionContext,
    ToolMutationGuarantee,
    ToolTextContent,
)
from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.agent_runtime.application.use_cases import SubmitRunCompletion, SubmitRunCompletionError


@dataclass(frozen=True, slots=True)
class SubmitAndExitRegisteredToolAdapter:
    """Map terminal tool arguments and opaque run context to completion submission."""

    use_case: SubmitRunCompletion

    async def handle(
        self,
        arguments: Mapping[str, ToolArgumentValue],
        context: ToolExecutionContext,
    ) -> RegisteredToolOutcome:
        """Submit completion or return a stable, recoverable tool rejection."""
        try:
            submission = _submission_from_arguments(arguments)
            run_id = _run_id_from_context(context)
        except (TypeError, ValueError) as err:
            return RegisteredToolOutcome.recoverable_rejection(error_code="INVALID_ARGUMENTS", error_message=str(err))

        try:
            result = await self.use_case.submit(
                SubmitRunCompletionCommand(
                    run_id=run_id,
                    tool_call_id=context.call_id,
                    submission=submission,
                )
            )
        except SubmitRunCompletionError as err:
            return RegisteredToolOutcome.recoverable_rejection(error_code=err.code, error_message=str(err))

        payload = {
            "run_id": result.record.run_id,
            "status": result.status.value,
        }
        return RegisteredToolOutcome.model_continue_success(
            mutation_guarantee=ToolMutationGuarantee.COMMITTED,
            content=(ToolTextContent(json.dumps(payload, sort_keys=True, separators=(",", ":"))),),
        )


def create_submit_and_exit_registered_tool(use_case: SubmitRunCompletion) -> AsyncRegisteredTool:
    """Create the model-facing registered tool for terminal completion submission."""
    adapter = SubmitAndExitRegisteredToolAdapter(use_case=use_case)
    return AsyncRegisteredTool(definition=SUBMIT_AND_EXIT_TOOL_DEFINITION, handler=adapter.handle)


def _submission_from_arguments(arguments: Mapping[str, ToolArgumentValue]) -> CompletionSubmission:
    if set(arguments) != {"outcome", "summary", "verification"}:
        msg = "submit_and_exit requires exactly outcome, summary, and verification arguments"
        raise ValueError(msg)
    outcome = arguments["outcome"]
    summary = arguments["summary"]
    verification = arguments["verification"]
    if not isinstance(outcome, str):
        msg = "outcome must be a string"
        raise TypeError(msg)
    if not isinstance(summary, str):
        msg = "summary must be a string"
        raise TypeError(msg)
    if not isinstance(verification, str):
        msg = "verification must be a string"
        raise TypeError(msg)
    try:
        return CompletionSubmission(
            outcome=CompletionOutcome(outcome),
            summary=summary,
            verification=CompletionVerification(verification),
        )
    except ValueError as err:
        msg = "submit_and_exit arguments contain an unsupported completion value"
        raise ValueError(msg) from err


def _run_id_from_context(context: ToolExecutionContext) -> str:
    run_id = context.opaque_values.get(RUN_ID_CONTEXT_KEY)
    if not isinstance(run_id, str):
        msg = "the current runtime does not provide a completion run id"
        raise TypeError(msg)
    return run_id


__all__ = ["SubmitAndExitRegisteredToolAdapter", "create_submit_and_exit_registered_tool"]
