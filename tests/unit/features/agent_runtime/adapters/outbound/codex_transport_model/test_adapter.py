"""Tests for the Codex transport-backed runtime model adapter."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.adapters.outbound.codex_transport_model import CodexTransportAgentModel
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunStatus,
    RuntimeObservation,
)
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
)


@dataclass
class FakeCodexTransportCompletion:
    result: CodexTransportResult
    calls: list[CodexCompletionCommand] = field(default_factory=list)

    def complete(self, command: CodexCompletionCommand) -> CodexTransportResult:
        self.calls.append(command)
        return self.result


def test_adapter_maps_successful_transport_result_to_runtime_result() -> None:
    transport = FakeCodexTransportCompletion(
        result=CodexTransportResult(
            status=CodexTransportStatus.SUCCESS,
            output_text="pong",
            observations=(CodexTransportObservation(message="backend probe succeeded"),),
        ),
    )
    command = LocalAgentRunCommand(prompt="Reply with the single word: pong")

    result = CodexTransportAgentModel(transport=transport).run(command)

    assert result.status is LocalAgentRunStatus.SUCCESS
    assert result.succeeded is True
    assert result.output_text == "pong"
    assert result.observations == (
        RuntimeObservation(message="backend probe succeeded", metadata={"transport_status": "success"}),
    )
    assert transport.calls == [CodexCompletionCommand(prompt="Reply with the single word: pong")]


def test_adapter_includes_runtime_context_as_bounded_prompt_text() -> None:
    transport = FakeCodexTransportCompletion(
        result=CodexTransportResult(status=CodexTransportStatus.SUCCESS, output_text="pong"),
    )
    command = LocalAgentRunCommand(
        prompt="Answer from context only",
        context=(LocalAgentContextBlock(text="The answer is pong.", label="note"),),
    )

    CodexTransportAgentModel(transport=transport).run(command)

    assert transport.calls == [
        CodexCompletionCommand(
            prompt="Context:\n[note]\nThe answer is pong.\n\nPrompt:\nAnswer from context only",
        ),
    ]


@pytest.mark.parametrize(
    "transport_status",
    [
        CodexTransportStatus.AUTHENTICATION_FAILED,
        CodexTransportStatus.CREDENTIAL_ERROR,
    ],
)
def test_adapter_maps_credential_transport_failures_to_configuration_errors(
    transport_status: CodexTransportStatus,
) -> None:
    transport = FakeCodexTransportCompletion(
        result=CodexTransportResult(
            status=transport_status,
            observations=(
                CodexTransportObservation(
                    message="credential loading failed",
                    metadata={"error_type": "SyntheticCredentialError"},
                ),
            ),
        ),
    )

    result = CodexTransportAgentModel(transport=transport).run(LocalAgentRunCommand(prompt="ping"))

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
    assert result.succeeded is False
    assert result.output_text is None
    assert result.observations == (
        RuntimeObservation(
            message="credential loading failed",
            metadata={
                "transport_status": transport_status.value,
                "error_type": "SyntheticCredentialError",
            },
        ),
    )


@pytest.mark.parametrize(
    "transport_status",
    [
        CodexTransportStatus.RATE_LIMITED,
        CodexTransportStatus.QUOTA_EXCEEDED,
        CodexTransportStatus.BACKEND_SHAPE_MISMATCH,
        CodexTransportStatus.TRANSPORT_ERROR,
    ],
)
def test_adapter_maps_model_transport_failures_to_model_errors(
    transport_status: CodexTransportStatus,
) -> None:
    transport = FakeCodexTransportCompletion(
        result=CodexTransportResult(
            status=transport_status,
            observations=(
                CodexTransportObservation(
                    message="backend request failed",
                    metadata={"category": "synthetic"},
                ),
            ),
        ),
    )

    result = CodexTransportAgentModel(transport=transport).run(LocalAgentRunCommand(prompt="ping"))

    assert result.status is LocalAgentRunStatus.MODEL_ERROR
    assert result.succeeded is False
    assert result.output_text is None
    assert result.observations == (
        RuntimeObservation(
            message="backend request failed",
            metadata={"transport_status": transport_status.value, "category": "synthetic"},
        ),
    )
