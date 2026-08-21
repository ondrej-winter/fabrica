"""Tests for the Codex-backed PydanticAI completion bridge."""

import asyncio
from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import (
    CodexTransportPydanticAICompletion,
    PydanticAICompletionError,
    PydanticAICompletionRequest,
)
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunStatus
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
)


@dataclass
class FakeCodexCompletionTransport:
    result: CodexTransportResult
    calls: list[CodexCompletionCommand] = field(default_factory=list)

    async def complete(self, command: CodexCompletionCommand) -> CodexTransportResult:
        self.calls.append(command)
        return self.result


def test_codex_completion_returns_successful_transport_output() -> None:
    transport = FakeCodexCompletionTransport(
        result=CodexTransportResult(
            status=CodexTransportStatus.SUCCESS,
            output_text="pong",
        ),
    )
    request = PydanticAICompletionRequest(
        prompt="Reply with pong",
        model_hint="codex-max",
        messages=("synthetic pydanticai message",),
    )

    output_text = asyncio.run(CodexTransportPydanticAICompletion(transport=transport).complete(request))

    assert output_text == "pong"
    assert transport.calls == [CodexCompletionCommand(prompt="Reply with pong")]


def test_codex_completion_maps_credential_failures_to_configuration_error() -> None:
    transport = FakeCodexCompletionTransport(
        result=CodexTransportResult(
            status=CodexTransportStatus.CREDENTIAL_ERROR,
            observations=(
                CodexTransportObservation(
                    message="credential loading failed",
                    metadata={"error_type": "CodexCredentialUnavailableError"},
                ),
            ),
        ),
    )

    with pytest.raises(PydanticAICompletionError) as error_info:
        asyncio.run(CodexTransportPydanticAICompletion(transport=transport).complete(_request()))

    assert error_info.value.status is LocalAgentRunStatus.CONFIGURATION_ERROR
    assert error_info.value.metadata == {
        "transport_status": "credential_error",
        "observation_count": 1,
        "transport_message": "credential loading failed",
        "transport_error_type": "CodexCredentialUnavailableError",
    }


def test_codex_completion_maps_backend_failures_to_model_error_without_raw_payloads() -> None:
    transport = FakeCodexCompletionTransport(
        result=CodexTransportResult(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            observations=(
                CodexTransportObservation(
                    message="Codex backend returned an unsuccessful response",
                    metadata={
                        "category": "backend_error",
                        "http_status": 500,
                        "response_shape": "error",
                        "raw_payload": "do not leak backend response body",
                    },
                ),
            ),
        ),
    )

    with pytest.raises(PydanticAICompletionError) as error_info:
        asyncio.run(CodexTransportPydanticAICompletion(transport=transport).complete(_request()))

    assert error_info.value.status is LocalAgentRunStatus.MODEL_ERROR
    assert error_info.value.metadata == {
        "transport_status": "transport_error",
        "observation_count": 1,
        "transport_message": "Codex backend returned an unsuccessful response",
        "transport_category": "backend_error",
        "transport_http_status": 500,
        "transport_response_shape": "error",
    }
    assert "do not leak backend response body" not in str(error_info.value.metadata)


def _request() -> PydanticAICompletionRequest:
    return PydanticAICompletionRequest(prompt="ping", model_hint=None, messages=())
