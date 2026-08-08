"""Tool-aware PydanticAI adapter proof for the bounded runtime tool loop."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model.message_rendering import build_user_prompt
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    RuntimeObservation,
    SafeRuntimeMetadataValue,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
)
from fabrica.features.agent_runtime.application.ports import ToolAwareAgentModelError


@dataclass(frozen=True, slots=True)
class PydanticAIToolAwareTurnRequest:
    """Adapter-local request for one PydanticAI-shaped tool-aware model turn."""

    prompt: str
    model_hint: str | None
    available_tools: tuple[ToolDefinition, ...]
    tool_results: tuple[ToolCallResult, ...]
    messages: tuple[ModelMessage, ...]


class PydanticAIToolAwareTurn(Protocol):
    """Adapter-local dependency that returns one PydanticAI model response."""

    def run_turn(self, request: PydanticAIToolAwareTurnRequest) -> ModelResponse:
        """Return a PydanticAI response for one tool-aware turn."""
        ...


class PydanticAIToolAwareAgentModel:
    """Adapt PydanticAI tool-call messages to the application tool-aware model port."""

    def __init__(self, turn_runner: PydanticAIToolAwareTurn) -> None:
        self._turn_runner = turn_runner

    def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
    ) -> ToolAwareModelResponse:
        """Run one tool-aware model turn and normalize PydanticAI message parts."""
        prompt = build_user_prompt(command)
        messages = _build_messages(prompt, tool_results)
        try:
            response = self._turn_runner.run_turn(
                PydanticAIToolAwareTurnRequest(
                    prompt=prompt,
                    model_hint=command.model_hint,
                    available_tools=tuple(available_tools),
                    tool_results=tuple(tool_results),
                    messages=messages,
                ),
            )
        except ToolAwareAgentModelError:
            raise
        except Exception as err:
            msg = "pydanticai tool-aware turn dependency failed"
            raise ToolAwareAgentModelError(
                msg,
                category="pydanticai_tool_aware_error",
                metadata={"error_type": type(err).__name__},
            ) from err

        return _response_to_tool_aware_model_response(response)


def _build_messages(prompt: str, tool_results: tuple[ToolCallResult, ...]) -> tuple[ModelMessage, ...]:
    messages: tuple[ModelMessage, ...] = (ModelRequest(parts=[UserPromptPart(prompt)]),)
    if not tool_results:
        return messages
    return (*messages, ModelRequest(parts=tuple(_tool_return_part(result) for result in tool_results)))


def _tool_return_part(result: ToolCallResult) -> ToolReturnPart:
    content = result.result_text if result.status is ToolCallResultStatus.SUCCESS else result.error_message
    return ToolReturnPart(
        tool_name=result.tool_name,
        content=content or result.status.value,
        tool_call_id=result.call_id,
        outcome="success" if result.status is ToolCallResultStatus.SUCCESS else "failed",
        metadata={"status": result.status.value},
    )


def _response_to_tool_aware_model_response(response: ModelResponse) -> ToolAwareModelResponse:
    text_parts = tuple(part for part in response.parts if isinstance(part, TextPart))
    tool_call_parts = tuple(part for part in response.parts if isinstance(part, ToolCallPart))
    if text_parts and tool_call_parts:
        msg = "pydanticai response contained both text and tool calls"
        raise ToolAwareAgentModelError(msg, category="invalid_pydanticai_response")
    if text_parts:
        output_text = "".join(part.content for part in text_parts)
        return ToolAwareModelResponse(
            output_text=output_text,
            observations=(RuntimeObservation(message="pydanticai tool-aware model returned final text"),),
        )
    if tool_call_parts:
        return ToolAwareModelResponse(
            tool_calls=tuple(_tool_call_part_to_request(part) for part in tool_call_parts),
            observations=(RuntimeObservation(message="pydanticai tool-aware model requested tools"),),
        )

    msg = "pydanticai response contained no supported output parts"
    raise ToolAwareAgentModelError(msg, category="invalid_pydanticai_response")


def _tool_call_part_to_request(part: ToolCallPart) -> ToolCallRequest:
    try:
        raw_arguments = part.args_as_dict()
    except ValueError as err:
        msg = "pydanticai tool call arguments were not a JSON object"
        raise ToolAwareAgentModelError(
            msg,
            category="invalid_tool_arguments",
            metadata={"tool_name": part.tool_name},
        ) from err
    return ToolCallRequest(
        call_id=part.tool_call_id,
        tool_name=part.tool_name,
        arguments=_safe_arguments(raw_arguments),
    )


def _safe_arguments(arguments: Mapping[str, object]) -> dict[str, SafeRuntimeMetadataValue]:
    safe: dict[str, SafeRuntimeMetadataValue] = {}
    for key, value in arguments.items():
        if isinstance(value, str | int | float | bool) or value is None:
            safe[key] = value
            continue
        msg = "pydanticai tool call arguments contained unsupported values"
        raise ToolAwareAgentModelError(
            msg,
            category="invalid_tool_arguments",
            metadata={"argument_name": key, "argument_type": type(value).__name__},
        )
    return safe
