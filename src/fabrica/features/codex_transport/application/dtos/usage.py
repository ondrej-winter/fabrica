"""Usage evidence command and result DTOs."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from fabrica.features.codex_transport.application.dtos.observations import CodexTransportObservation

SafeUsageEvidenceValue = str | int | float | bool | None


class CodexUsageStatus(StrEnum):
    """Normalized outcomes for a Codex usage evidence probe."""

    SUCCESS = "success"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    BACKEND_SHAPE_MISMATCH = "backend_shape_mismatch"
    TRANSPORT_ERROR = "transport_error"
    CREDENTIAL_ERROR = "credential_error"


@dataclass(frozen=True, slots=True)
class CodexUsageProbeCommand:
    """Application command for one Codex usage evidence probe."""

    include_rate_limit_reset: bool = False


@dataclass(frozen=True, slots=True)
class CodexUsageEvidence:
    """Bounded, application-safe usage and quota evidence from the backend."""

    values: Mapping[str, SafeUsageEvidenceValue]

    def __init__(self, values: Mapping[str, SafeUsageEvidenceValue]) -> None:
        for key, value in values.items():
            if not isinstance(key, str):
                msg = "usage evidence keys must be strings"
                raise TypeError(msg)
            if not _is_safe_usage_evidence_value(value):
                msg = f"usage evidence value for {key!r} must be a bounded scalar"
                raise TypeError(msg)
        object.__setattr__(self, "values", MappingProxyType(dict(values)))


@dataclass(frozen=True, slots=True)
class CodexUsageResult:
    """Normalized, application-safe result of a Codex usage evidence probe."""

    status: CodexUsageStatus
    evidence: CodexUsageEvidence | None = None
    observations: tuple[CodexTransportObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status is CodexUsageStatus.SUCCESS and self.evidence is None:
            msg = "successful Codex usage results must include evidence"
            raise ValueError(msg)
        if self.status is not CodexUsageStatus.SUCCESS and self.evidence is not None:
            msg = "non-success Codex usage results must not include evidence"
            raise ValueError(msg)

    @property
    def succeeded(self) -> bool:
        """Return whether usage evidence was retrieved successfully."""
        return self.status is CodexUsageStatus.SUCCESS


def _is_safe_usage_evidence_value(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)
