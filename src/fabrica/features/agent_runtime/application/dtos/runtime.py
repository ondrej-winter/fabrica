"""Runtime command, result, and diagnostic DTOs."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from fabrica.features.agent_runtime.application.dtos.usage import ModelCostEvidence, ModelUsageEvidence

MAX_PROMPT_CHARS = 20_000
MAX_CONTEXT_TEXT_CHARS = 500_000

SafeRuntimeMetadataValue = str | int | float | bool | None


class LocalAgentRunStatus(StrEnum):
    """Normalized outcomes for one local agent runtime invocation."""

    SUCCESS = "success"
    MODEL_ERROR = "model_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    SAFETY_DENIED = "safety_denied"


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    """Redacted diagnostic information for a local agent runtime run."""

    message: str
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LocalAgentContextBlock:
    """Bounded text context made available to a local agent run."""

    text: str
    label: str | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.text) > MAX_CONTEXT_TEXT_CHARS:
            msg = "context block text exceeds the local runtime bound"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LocalAgentRunCommand:
    """Application command for one local agent runtime run."""

    prompt: str
    context: tuple[LocalAgentContextBlock, ...] = field(default_factory=tuple)
    model_hint: str | None = None

    def __post_init__(self) -> None:
        if not self.prompt:
            msg = "prompt must not be empty"
            raise ValueError(msg)
        if len(self.prompt) > MAX_PROMPT_CHARS:
            msg = "prompt exceeds the local runtime bound"
            raise ValueError(msg)
        object.__setattr__(self, "context", tuple(self.context))


@dataclass(frozen=True, slots=True)
class LocalAgentRunResult:
    """Normalized, application-safe result of one local agent runtime run."""

    status: LocalAgentRunStatus
    output_text: str | None = None
    observations: tuple[RuntimeObservation, ...] = field(default_factory=tuple)
    usage_evidence: tuple[ModelUsageEvidence, ...] = field(default_factory=tuple)
    cost_evidence: tuple[ModelCostEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "usage_evidence", tuple(self.usage_evidence))
        object.__setattr__(self, "cost_evidence", tuple(self.cost_evidence))

    @property
    def succeeded(self) -> bool:
        """Return whether the local agent run completed successfully."""
        return self.status is LocalAgentRunStatus.SUCCESS
