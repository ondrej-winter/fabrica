"""Adapt normalized Codex tool turns to the provider-neutral runtime model port."""

import json
from typing import Protocol, cast

from fabrica.features.agent_runtime.adapters.outbound.codex_transport_model.adapter import _build_transport_prompt
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    RuntimeObservation,
    ToolArgumentValue,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolCancellationSignal,
    ToolDefinition,
    ToolTextContent,
    canonical_tool_arguments_json,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModelError
from fabrica.features.codex_transport.application.dtos import (
    CodexToolDefinition,
    CodexToolResult,
    CodexToolTurnCommand,
    CodexToolTurnResult,
    CodexTransportStatus,
)


class _CodexToolTurnTransport(Protocol):
    """Published Codex transport API required by this runtime adapter."""

    async def run_turn(self, command: CodexToolTurnCommand) -> CodexToolTurnResult:
        """Run one normalized Codex tool-aware turn."""
        ...


class CodexTransportToolAwareAgentModel:
    """Adapt Codex tool turns without exposing provider state to the runtime."""

    def __init__(self, transport: _CodexToolTurnTransport) -> None:
        self._transport = transport

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        """Run one Codex tool-aware turn using the runtime-owned normalized transcript."""
        del cancellation
        result = await self._transport.run_turn(
            CodexToolTurnCommand(
                prompt=_build_transport_prompt(command),
                tools=tuple(_tool_definition(tool) for tool in available_tools),
                tool_results=tuple(_tool_result(item) for item in tool_results),
            )
        )
        if result.status is not CodexTransportStatus.SUCCESS:
            msg = "Codex tool-aware turn failed"
            raise ToolAwareAgentModelError(
                msg,
                category=result.status.value,
                metadata={"transport_status": result.status.value},
                observations=_observations(result),
            )
        if result.output_text is not None:
            return ToolAwareModelResponse(
                output_text=result.output_text,
                observations=_observations(result),
            )
        return ToolAwareModelResponse(
            tool_calls=tuple(
                _tool_call(call.call_id, call.tool_name, call.arguments_json) for call in result.tool_calls
            ),
            observations=_observations(result),
        )


def _tool_definition(tool: ToolDefinition) -> CodexToolDefinition:
    return CodexToolDefinition(
        name=tool.name,
        description=tool.description,
        argument_schema=tool.argument_schema,
    )


def _tool_result(result: ToolCallResult) -> CodexToolResult:
    return CodexToolResult(
        call_id=result.call_id,
        tool_name=result.tool_name,
        arguments_json=canonical_tool_arguments_json(result.arguments, tool_name=result.tool_name),
        result_text=_tool_result_text(result),
    )


def _tool_result_text(result: ToolCallResult) -> str:
    if result.status is not ToolCallResultStatus.SUCCESS:
        return result.error_message or result.status.value
    text_parts = tuple(part.text for part in result.content if isinstance(part, ToolTextContent))
    if text_parts:
        return "\n".join(text_parts)
    return result.result_text or result.status.value


def _tool_call(call_id: str, tool_name: str, arguments_json: str) -> ToolCallRequest:
    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError as err:
        msg = "Codex tool-call arguments were not valid JSON"
        raise ToolAwareAgentModelError(msg, category="invalid_tool_arguments") from err
    if not isinstance(arguments, dict):
        msg = "Codex tool-call arguments were not a JSON object"
        raise ToolAwareAgentModelError(msg, category="invalid_tool_arguments")
    try:
        return ToolCallRequest(
            call_id=call_id,
            tool_name=tool_name,
            arguments=cast("dict[str, ToolArgumentValue]", _immutable_json_value(arguments)),
        )
    except (TypeError, ValueError) as err:
        msg = "Codex tool-call arguments were invalid"
        raise ToolAwareAgentModelError(msg, category="invalid_tool_arguments") from err


def _immutable_json_value(value: object) -> ToolArgumentValue:
    if isinstance(value, dict):
        return cast("dict[str, ToolArgumentValue]", {key: _immutable_json_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_immutable_json_value(item) for item in value)
    return cast("ToolArgumentValue", value)


def _observations(result: CodexToolTurnResult) -> tuple[RuntimeObservation, ...]:
    return tuple(
        RuntimeObservation(
            message=observation.message,
            metadata={"transport_status": result.status.value, **observation.metadata},
        )
        for observation in result.observations
    )
