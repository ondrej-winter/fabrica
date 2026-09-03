"""Completion records and outcomes for terminal agent runs."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType

from fabrica.features.agent_runtime.application.dtos.runtime import SafeRuntimeMetadataValue

MAX_COMPLETION_SUMMARY_CHARS = 12_000
MAX_COMPLETION_IDENTIFIER_CHARS = 120
SHA256_DIGEST_CHARS = 71
RUN_ID_CONTEXT_KEY = "agent_runtime.run_id"


class CompletionOutcome(StrEnum):
    """Declared terminal outcome for an accepted completion record."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class CompletionVerification(StrEnum):
    """Verification state declared independently from terminal outcome."""

    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    NOT_APPLICABLE = "not_applicable"


class CompletionCommitStatus(StrEnum):
    """Result of atomically committing one terminal completion record."""

    COMMITTED = "committed"
    ALREADY_COMPLETED = "already_completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CompletionRecord:
    """Immutable, durably accepted terminal record for one agent run."""

    run_id: str
    tool_call_id: str
    payload_digest: str
    outcome: CompletionOutcome
    summary: str
    verification: CompletionVerification
    committed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_identifier(self.run_id, field_name="run id")
        _validate_identifier(self.tool_call_id, field_name="tool call id")
        if len(self.payload_digest) != SHA256_DIGEST_CHARS or not self.payload_digest.startswith("sha256:"):
            msg = "completion payload digest must be a sha256 digest"
            raise ValueError(msg)
        if not self.summary or len(self.summary) > MAX_COMPLETION_SUMMARY_CHARS:
            msg = "completion summary must contain 1 to 12000 characters"
            raise ValueError(msg)
        if self.committed_at.tzinfo is None or self.committed_at.utcoffset() is None:
            msg = "completion timestamp must be timezone-aware"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CompletionCommitResult:
    """Typed atomic completion-commit result without infrastructure details."""

    status: CompletionCommitStatus
    record: CompletionRecord | None = None

    def __post_init__(self) -> None:
        if self.status is CompletionCommitStatus.CANCELLED and self.record is not None:
            msg = "cancelled completion commits must not carry a completion record"
            raise ValueError(msg)
        if self.status is not CompletionCommitStatus.CANCELLED and self.record is None:
            msg = "accepted completion commits must carry a completion record"
            raise ValueError(msg)


def _validate_identifier(value: str, *, field_name: str) -> None:
    if not value or len(value) > MAX_COMPLETION_IDENTIFIER_CHARS or value != value.strip() or "/" in value:
        msg = f"{field_name} must be a bounded non-empty identifier"
        raise ValueError(msg)


__all__ = [
    "MAX_COMPLETION_IDENTIFIER_CHARS",
    "MAX_COMPLETION_SUMMARY_CHARS",
    "RUN_ID_CONTEXT_KEY",
    "SHA256_DIGEST_CHARS",
    "CompletionCommitResult",
    "CompletionCommitStatus",
    "CompletionOutcome",
    "CompletionRecord",
    "CompletionVerification",
]
