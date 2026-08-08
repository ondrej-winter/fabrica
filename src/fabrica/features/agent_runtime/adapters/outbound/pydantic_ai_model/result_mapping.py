"""Runtime result mapping helpers for PydanticAI adapter failures."""

from collections.abc import Mapping

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunResult,
    LocalAgentRunStatus,
    RuntimeObservation,
    SafeRuntimeMetadataValue,
)

PYDANTIC_AI_MODEL_ADAPTER_NAME = "pydantic_ai_model"


def failure_result(
    status: LocalAgentRunStatus,
    message: str,
    metadata: Mapping[str, SafeRuntimeMetadataValue],
) -> LocalAgentRunResult:
    """Return a safe failed runtime result for a PydanticAI adapter boundary."""
    return LocalAgentRunResult(
        status=status,
        observations=(
            RuntimeObservation(
                message=message,
                metadata={"adapter": PYDANTIC_AI_MODEL_ADAPTER_NAME, **metadata},
            ),
        ),
    )
