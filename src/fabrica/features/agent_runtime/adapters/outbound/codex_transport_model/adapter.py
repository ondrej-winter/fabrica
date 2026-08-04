"""Runtime model adapter backed by the Codex transport application API."""

from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
)
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
)


class _CodexTransportCompletion(Protocol):
    """Published Codex transport completion API required by this adapter."""

    def complete(self, command: CodexCompletionCommand) -> CodexTransportResult:
        """Run one Codex transport completion."""
        ...


class CodexTransportAgentModel:
    """Adapt the Codex transport probe use case to the runtime model port."""

    def __init__(self, transport: _CodexTransportCompletion) -> None:
        self._transport = transport

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        """Run one local agent command through the Codex transport API."""
        transport_result = self._transport.complete(
            CodexCompletionCommand(prompt=_build_transport_prompt(command)),
        )
        runtime_status = _map_status(transport_result.status)
        return LocalAgentRunResult(
            status=runtime_status,
            output_text=transport_result.output_text if runtime_status is LocalAgentRunStatus.SUCCESS else None,
            observations=_map_observations(transport_result),
        )


def _build_transport_prompt(command: LocalAgentRunCommand) -> str:
    if not command.context:
        return command.prompt

    context_text = "\n\n".join(_format_context_block(block) for block in command.context)
    return f"Context:\n{context_text}\n\nPrompt:\n{command.prompt}"


def _format_context_block(block: LocalAgentContextBlock) -> str:
    if block.label is None:
        return block.text
    return f"[{block.label}]\n{block.text}"


def _map_status(status: CodexTransportStatus) -> LocalAgentRunStatus:
    if status is CodexTransportStatus.SUCCESS:
        return LocalAgentRunStatus.SUCCESS
    if status in {CodexTransportStatus.AUTHENTICATION_FAILED, CodexTransportStatus.CREDENTIAL_ERROR}:
        return LocalAgentRunStatus.CONFIGURATION_ERROR
    return LocalAgentRunStatus.MODEL_ERROR


def _map_observations(result: CodexTransportResult) -> tuple[RuntimeObservation, ...]:
    return tuple(_map_observation(result.status, observation) for observation in result.observations)


def _map_observation(
    status: CodexTransportStatus,
    observation: CodexTransportObservation,
) -> RuntimeObservation:
    return RuntimeObservation(
        message=observation.message,
        metadata={"transport_status": status.value, **observation.metadata},
    )
