"""Transport probe command and result DTOs."""

from dataclasses import dataclass, field
from enum import StrEnum

from fabrica.features.codex_transport.application.dtos.observations import CodexTransportObservation


class CodexTransportStatus(StrEnum):
    """Normalized outcomes for a Codex backend transport probe."""

    SUCCESS = "success"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    BACKEND_SHAPE_MISMATCH = "backend_shape_mismatch"
    TRANSPORT_ERROR = "transport_error"
    CREDENTIAL_ERROR = "credential_error"


@dataclass(frozen=True, slots=True)
class CodexCompletionCommand:
    """Application command for one non-streaming Codex completion."""

    prompt: str


@dataclass(frozen=True, slots=True)
class CodexTransportProbeCommand:
    """Application command for one non-streaming Codex backend probe."""

    prompt: str


@dataclass(frozen=True, slots=True)
class CodexTransportResult:
    """Normalized, application-safe result of a Codex transport probe."""

    status: CodexTransportStatus
    output_text: str | None = None
    observations: tuple[CodexTransportObservation, ...] = field(default_factory=tuple)

    @property
    def succeeded(self) -> bool:
        """Return whether the probe completed successfully."""
        return self.status is CodexTransportStatus.SUCCESS
