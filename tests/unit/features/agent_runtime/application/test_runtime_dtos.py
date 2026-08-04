"""Tests for local agent runtime application DTO contracts."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentContextBlock,
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
)
from fabrica.features.agent_runtime.application.dtos.runtime import MAX_CONTEXT_TEXT_CHARS, MAX_PROMPT_CHARS


def test_runtime_status_values_match_normalized_contract() -> None:
    assert {status.value for status in LocalAgentRunStatus} == {
        "success",
        "model_error",
        "configuration_error",
        "unsupported_capability",
        "safety_denied",
    }


def test_run_command_carries_prompt_context_and_model_hint_without_backend_details() -> None:
    context_block = LocalAgentContextBlock(
        text="Relevant local context",
        label="notes",
        metadata={"source": "test"},
    )

    command = LocalAgentRunCommand(
        prompt="Reply with the single word: pong",
        context=(context_block,),
        model_hint="codex-compatible",
    )

    assert command.prompt == "Reply with the single word: pong"
    assert command.context == (context_block,)
    assert command.model_hint == "codex-compatible"


def test_run_command_rejects_empty_or_unbounded_prompts() -> None:
    with pytest.raises(ValueError, match="prompt must not be empty"):
        LocalAgentRunCommand(prompt="")

    with pytest.raises(ValueError, match="prompt exceeds"):
        LocalAgentRunCommand(prompt="x" * (MAX_PROMPT_CHARS + 1))


def test_context_block_rejects_unbounded_text() -> None:
    with pytest.raises(ValueError, match="context block text exceeds"):
        LocalAgentContextBlock(text="x" * (MAX_CONTEXT_TEXT_CHARS + 1))


def test_observation_and_context_metadata_are_copied_and_immutable() -> None:
    metadata = {"category": "model", "attempt": 1}
    observation = RuntimeObservation(message="model completed", metadata=metadata)
    context_block = LocalAgentContextBlock(text="safe text", metadata=metadata)

    metadata["category"] = "mutated"

    assert observation.metadata["category"] == "model"
    assert context_block.metadata["category"] == "model"
    with pytest.raises(TypeError):
        cast("dict[str, object]", observation.metadata)["category"] = "changed"
    with pytest.raises(TypeError):
        cast("dict[str, object]", context_block.metadata)["category"] = "changed"


def test_result_exposes_success_helper_and_safe_observations() -> None:
    observation = RuntimeObservation(message="model returned output", metadata={"component": "fake_model"})
    result = LocalAgentRunResult(
        status=LocalAgentRunStatus.SUCCESS,
        output_text="pong",
        observations=(observation,),
    )

    assert result.succeeded is True
    assert result.output_text == "pong"
    assert result.observations == (observation,)


def test_non_success_result_is_not_successful() -> None:
    result = LocalAgentRunResult(status=LocalAgentRunStatus.CONFIGURATION_ERROR)

    assert result.succeeded is False
    assert result.output_text is None
    assert result.observations == ()


def test_runtime_dtos_are_immutable_boundary_values() -> None:
    command = LocalAgentRunCommand(prompt="Reply with pong")
    result = LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS)

    with pytest.raises(FrozenInstanceError):
        setattr(command, "prompt", "changed")  # noqa: B010
    with pytest.raises(FrozenInstanceError):
        setattr(result, "status", LocalAgentRunStatus.MODEL_ERROR)  # noqa: B010
