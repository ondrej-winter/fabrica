"""Use case for running a bounded application-owned tool loop."""

from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    RuntimeObservation,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.agent_runtime.application.ports import (
    ToolAwareAgentModel,
    ToolAwareAgentModelError,
    ToolExecutionError,
    ToolExecutor,
)


class RunToolLoop:
    """Orchestrate a bounded prompt-model-tool loop through injected ports."""

    def __init__(self, model: ToolAwareAgentModel, tool_executor: ToolExecutor) -> None:
        self._model = model
        self._tool_executor = tool_executor

    def run(
        self,
        command: LocalAgentRunCommand,
        *,
        available_tools: tuple[ToolDefinition, ...] = (),
        limits: ToolLoopLimits | None = None,
    ) -> ToolLoopRunResult:
        """Run model turns and requested tools until final output or a safe stop condition."""
        active_limits = limits or ToolLoopLimits()
        tool_results: tuple[ToolCallResult, ...] = ()
        observations: tuple[RuntimeObservation, ...] = ()
        accepted_call_ids: set[str] = set()

        for iteration in range(active_limits.max_tool_iterations + 1):
            try:
                model_response = self._model.run_turn(command, tuple(available_tools), tool_results)
            except ToolAwareAgentModelError as err:
                return ToolLoopRunResult(
                    status=ToolLoopRunStatus.MODEL_ERROR,
                    tool_results=tool_results,
                    observations=(
                        *observations,
                        RuntimeObservation(
                            message="tool-aware model dependency failed",
                            metadata={"category": err.category, **err.metadata},
                        ),
                    ),
                )

            observations = (*observations, *model_response.observations)
            if model_response.output_text is not None:
                return ToolLoopRunResult(
                    status=ToolLoopRunStatus.SUCCESS,
                    output_text=model_response.output_text,
                    tool_results=tool_results,
                    observations=observations,
                )

            if iteration >= active_limits.max_tool_iterations:
                return ToolLoopRunResult(
                    status=ToolLoopRunStatus.MAX_ITERATIONS_EXCEEDED,
                    tool_results=tool_results,
                    observations=(
                        *observations,
                        RuntimeObservation(
                            message="tool loop stopped at max iterations",
                            metadata={"max_tool_iterations": active_limits.max_tool_iterations},
                        ),
                    ),
                )

            validation_failure = _validate_tool_call_batch(
                model_response.tool_calls,
                limits=active_limits,
                accepted_call_ids=accepted_call_ids,
            )
            if validation_failure is not None:
                return ToolLoopRunResult(
                    status=validation_failure.status,
                    tool_results=tool_results,
                    observations=(*observations, validation_failure.observation),
                )

            turn_results = tuple(
                self._execute_tool_call(tool_call, active_limits) for tool_call in model_response.tool_calls
            )
            accepted_call_ids.update(tool_call.call_id for tool_call in model_response.tool_calls)
            tool_results = (*tool_results, *turn_results)
            observations = (
                *observations,
                *(observation for result in turn_results for observation in result.observations),
            )
            stop_status = _first_stop_status(turn_results)
            if stop_status is not None:
                return ToolLoopRunResult(status=stop_status, tool_results=tool_results, observations=observations)

        return ToolLoopRunResult(status=ToolLoopRunStatus.MAX_ITERATIONS_EXCEEDED, tool_results=tool_results)

    def _execute_tool_call(self, tool_call: ToolCallRequest, limits: ToolLoopLimits) -> ToolCallResult:
        try:
            return self._tool_executor.execute_tool(tool_call, limits).bounded(limits)
        except ToolExecutionError as err:
            return ToolCallResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                status=ToolCallResultStatus.ADAPTER_ERROR,
                error_message="tool execution adapter failed",
                observations=(
                    RuntimeObservation(
                        message="tool execution adapter failed",
                        metadata={"tool_name": tool_call.tool_name, "category": err.category, **err.metadata},
                    ),
                ),
            )


@dataclass(frozen=True, slots=True)
class _ToolCallBatchValidationFailure:
    status: ToolLoopRunStatus
    observation: RuntimeObservation


def _validate_tool_call_batch(
    tool_calls: tuple[ToolCallRequest, ...],
    *,
    limits: ToolLoopLimits,
    accepted_call_ids: set[str],
) -> _ToolCallBatchValidationFailure | None:
    if len(tool_calls) > limits.max_tool_calls_per_turn:
        return _ToolCallBatchValidationFailure(
            status=ToolLoopRunStatus.TOOL_LIMIT_EXCEEDED,
            observation=RuntimeObservation(
                message="tool loop rejected excessive tool calls",
                metadata={
                    "tool_call_count": len(tool_calls),
                    "max_tool_calls_per_turn": limits.max_tool_calls_per_turn,
                },
            ),
        )

    seen_call_ids: set[str] = set()
    for tool_call in tool_calls:
        if tool_call.call_id in seen_call_ids:
            return _duplicate_call_id_failure(tool_call.call_id, duplicate_scope="turn")
        if tool_call.call_id in accepted_call_ids:
            return _duplicate_call_id_failure(tool_call.call_id, duplicate_scope="run")
        seen_call_ids.add(tool_call.call_id)

    return None


def _duplicate_call_id_failure(call_id: str, *, duplicate_scope: str) -> _ToolCallBatchValidationFailure:
    return _ToolCallBatchValidationFailure(
        status=ToolLoopRunStatus.INVALID_TOOL_REQUEST,
        observation=RuntimeObservation(
            message="tool loop rejected duplicate tool call id",
            metadata={"tool_call_id": call_id, "duplicate_scope": duplicate_scope},
        ),
    )


def _first_stop_status(results: tuple[ToolCallResult, ...]) -> ToolLoopRunStatus | None:
    for result in results:
        if result.status is ToolCallResultStatus.SUCCESS:
            continue
        return _tool_result_status_to_loop_status(result.status)
    return None


def _tool_result_status_to_loop_status(status: ToolCallResultStatus) -> ToolLoopRunStatus:
    if status is ToolCallResultStatus.UNKNOWN_TOOL:
        return ToolLoopRunStatus.UNKNOWN_TOOL
    if status is ToolCallResultStatus.INVALID_ARGUMENTS:
        return ToolLoopRunStatus.INVALID_TOOL_REQUEST
    if status is ToolCallResultStatus.TIMEOUT:
        return ToolLoopRunStatus.TOOL_TIMEOUT
    if status is ToolCallResultStatus.LIMIT_EXCEEDED:
        return ToolLoopRunStatus.TOOL_LIMIT_EXCEEDED
    if status is ToolCallResultStatus.ADAPTER_ERROR:
        return ToolLoopRunStatus.TOOL_ADAPTER_ERROR
    return ToolLoopRunStatus.TOOL_FAILURE
