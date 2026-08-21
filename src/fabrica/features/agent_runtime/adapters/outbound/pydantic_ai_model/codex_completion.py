"""Codex transport completion bridge for the PydanticAI runtime adapter."""

from typing import Protocol

from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model.completion import (
    PydanticAICompletionError,
    PydanticAICompletionRequest,
)
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunStatus, SafeRuntimeMetadataValue
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
)


class _CodexTransportCompletion(Protocol):
    """Published Codex completion API required by the PydanticAI bridge."""

    async def complete(self, command: CodexCompletionCommand) -> CodexTransportResult:
        """Run one Codex transport completion."""
        ...


class CodexTransportPydanticAICompletion:
    """Adapt the Codex completion application API to PydanticAI completion calls."""

    def __init__(self, transport: _CodexTransportCompletion) -> None:
        self._transport = transport

    async def complete(self, request: PydanticAICompletionRequest) -> str:
        """Return Codex completion text for one PydanticAI-rendered request."""
        result = await self._transport.complete(CodexCompletionCommand(prompt=request.prompt))
        if result.status is CodexTransportStatus.SUCCESS and result.output_text is not None:
            return result.output_text

        message = "Codex transport completion failed"
        raise PydanticAICompletionError(
            message,
            status=_map_status(result.status),
            metadata=_safe_error_metadata(result),
        )


def _map_status(status: CodexTransportStatus) -> LocalAgentRunStatus:
    if status in {CodexTransportStatus.AUTHENTICATION_FAILED, CodexTransportStatus.CREDENTIAL_ERROR}:
        return LocalAgentRunStatus.CONFIGURATION_ERROR
    return LocalAgentRunStatus.MODEL_ERROR


def _safe_error_metadata(result: CodexTransportResult) -> dict[str, SafeRuntimeMetadataValue]:
    metadata: dict[str, SafeRuntimeMetadataValue] = {
        "transport_status": result.status.value,
        "observation_count": len(result.observations),
    }
    first_observation = result.observations[0] if result.observations else None
    if first_observation is not None:
        metadata.update(_safe_observation_metadata(first_observation))
    return metadata


def _safe_observation_metadata(observation: CodexTransportObservation) -> dict[str, SafeRuntimeMetadataValue]:
    metadata: dict[str, SafeRuntimeMetadataValue] = {"transport_message": observation.message}
    for key in ("category", "error_type", "http_status", "response_shape"):
        value = observation.metadata.get(key)
        if isinstance(value, str | int | float | bool):
            metadata[f"transport_{key}"] = value
    return metadata
