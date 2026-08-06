"""Transport completion command and result DTOs."""

from dataclasses import dataclass, field
from enum import StrEnum

from fabrica.features.codex_transport.application.dtos.observations import CodexTransportObservation
from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence


class CodexTransportStatus(StrEnum):
    """Normalized outcomes for Codex backend calls."""

    SUCCESS = "success"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    BACKEND_SHAPE_MISMATCH = "backend_shape_mismatch"
    TRANSPORT_ERROR = "transport_error"
    CREDENTIAL_ERROR = "credential_error"


@dataclass(frozen=True, slots=True)
class CodexCompletionCommand:
    """Application command for one normalized Codex completion result."""

    prompt: str

    def __post_init__(self) -> None:
        _validate_prompt(self.prompt)


@dataclass(frozen=True, slots=True)
class CodexTransportResult:
    """Normalized, application-safe result of a Codex transport completion."""

    status: CodexTransportStatus
    output_text: str | None = None
    observations: tuple[CodexTransportObservation, ...] = field(default_factory=tuple)
    usage_evidence: tuple[ModelUsageEvidence, ...] = field(default_factory=tuple)
    cost_evidence: tuple[ModelCostEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status is CodexTransportStatus.SUCCESS and self.output_text is None:
            msg = "successful Codex transport results must include output_text"
            raise ValueError(msg)
        if self.status is not CodexTransportStatus.SUCCESS and self.output_text is not None:
            msg = "non-success Codex transport results must not include output_text"
            raise ValueError(msg)
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "usage_evidence", tuple(self.usage_evidence))
        object.__setattr__(self, "cost_evidence", tuple(self.cost_evidence))

    @property
    def succeeded(self) -> bool:
        """Return whether the completion finished successfully."""
        return self.status is CodexTransportStatus.SUCCESS


def _validate_prompt(prompt: str) -> None:
    if not prompt.strip():
        msg = "Codex prompts must not be empty or whitespace-only"
        raise ValueError(msg)
