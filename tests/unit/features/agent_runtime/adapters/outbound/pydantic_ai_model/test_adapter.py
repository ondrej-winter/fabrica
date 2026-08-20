"""Tests for the PydanticAI-backed runtime model adapter."""

import asyncio
from dataclasses import dataclass, field

from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import (
    PydanticAIAgentModel,
    PydanticAICompletionError,
    PydanticAICompletionRequest,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunStatus,
    RuntimeObservation,
)


@dataclass
class FakeCompletion:
    output_text: str = "pong"
    error: PydanticAICompletionError | None = None
    calls: list[PydanticAICompletionRequest] = field(default_factory=list)

    def complete(self, request: PydanticAICompletionRequest) -> str:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.output_text


def test_adapter_maps_successful_pydanticai_result_to_runtime_result() -> None:
    completion = FakeCompletion(output_text="pong")
    command = LocalAgentRunCommand(prompt="Reply with the single word: pong")

    result = asyncio.run(PydanticAIAgentModel(completion=completion).run(command))

    assert result.status is LocalAgentRunStatus.SUCCESS
    assert result.succeeded is True
    assert result.output_text == "pong"
    assert result.observations == (
        RuntimeObservation(
            message="pydanticai completion succeeded",
            metadata={
                "model_name": "synthetic-codex",
                "pydantic_ai_model_system": "fabrica-pydanticai",
            },
        ),
    )
    assert completion.calls[0].prompt == "Reply with the single word: pong"
    assert completion.calls[0].model_hint is None


def test_adapter_includes_runtime_context_as_bounded_prompt_text() -> None:
    completion = FakeCompletion()
    command = LocalAgentRunCommand(
        prompt="Answer from context only",
        context=(LocalAgentContextBlock(text="The answer is pong.", label="note"),),
    )

    asyncio.run(PydanticAIAgentModel(completion=completion).run(command))

    assert completion.calls[0].prompt == "Context:\n[note]\nThe answer is pong.\n\nPrompt:\nAnswer from context only"


def test_adapter_passes_model_hint_to_completion_and_pydanticai_model_name() -> None:
    completion = FakeCompletion()
    command = LocalAgentRunCommand(prompt="ping", model_hint="codex-max")

    result = asyncio.run(PydanticAIAgentModel(completion=completion).run(command))

    assert completion.calls[0].model_hint == "codex-max"
    assert result.observations == (
        RuntimeObservation(
            message="pydanticai completion succeeded",
            metadata={
                "model_name": "codex-max",
                "pydantic_ai_model_system": "fabrica-pydanticai",
            },
        ),
    )


def test_adapter_exposes_pydanticai_rendered_messages_to_synthetic_completion() -> None:
    completion = FakeCompletion()

    asyncio.run(PydanticAIAgentModel(completion=completion).run(LocalAgentRunCommand(prompt="ping")))

    assert completion.calls[0].messages
    assert "ping" in completion.calls[0].messages[0]
    assert "user-prompt" in completion.calls[0].messages[0]


def test_adapter_maps_completion_dependency_failure_to_safe_runtime_result() -> None:
    completion = FakeCompletion(
        error=PydanticAICompletionError(
            "do not leak raw backend payload",
            status=LocalAgentRunStatus.CONFIGURATION_ERROR,
            metadata={"error_type": "SyntheticCredentialError"},
        ),
    )

    result = asyncio.run(PydanticAIAgentModel(completion=completion).run(LocalAgentRunCommand(prompt="ping")))

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
    assert result.succeeded is False
    assert result.output_text is None
    assert result.observations == (
        RuntimeObservation(
            message="pydanticai completion failed",
            metadata={"adapter": "pydantic_ai_model", "error_type": "SyntheticCredentialError"},
        ),
    )
    assert "do not leak raw backend payload" not in str(result.observations)
