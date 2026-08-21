"""Completion dependency contracts for the PydanticAI runtime adapter."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunStatus,
    SafeRuntimeMetadataValue,
)


@dataclass(frozen=True, slots=True)
class PydanticAICompletionRequest:
    """Adapter-local completion request rendered from PydanticAI messages."""

    prompt: str
    model_hint: str | None
    messages: tuple[str, ...]


class PydanticAICompletionError(Exception):
    """Runtime-safe synthetic completion dependency error."""

    def __init__(
        self,
        message: str,
        *,
        status: LocalAgentRunStatus = LocalAgentRunStatus.MODEL_ERROR,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.metadata = dict(metadata or {})


class PydanticAICompletion(Protocol):
    """Adapter-local dependency used by the custom PydanticAI model proof."""

    async def complete(self, request: PydanticAICompletionRequest) -> str:
        """Return text for one rendered PydanticAI request."""
        ...
