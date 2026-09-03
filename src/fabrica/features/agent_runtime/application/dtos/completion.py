"""Completion records and outcomes for terminal agent runs."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType

from fabrica.features.agent_runtime.application.dtos.runtime import SafeRuntimeMetadataValue
from fabrica.features.agent_runtime.application.dtos.tools import ToolBatchPolicy, ToolDefinition

MAX_COMPLETION_SUMMARY_CHARS = 12_000
MAX_COMPLETION_IDENTIFIER_CHARS = 120
SHA256_DIGEST_CHARS = 71
DEFAULT_COMPLETION_SUBMIT_TIMEOUT_SECONDS = 15.0
RUN_ID_CONTEXT_KEY = "agent_runtime.run_id"
SUBMIT_AND_EXIT_TOOL_NAME = "submit_and_exit"
SUBMIT_AND_EXIT_TOOL_DESCRIPTION = """Finish the current task and terminate the agent run.

Call this only after all useful work is complete or when the task cannot proceed further.

Before submitting, review the original request, ensure all requested changes are present, and perform appropriate
verification where possible. Inspect verification results before claiming verification succeeded.

Use outcome to state whether the task was completed, partially completed, or blocked. Use verification to state
whether correctness was actually checked.

The summary is the final user-facing response. Clearly state what was done, verification performed, and any
remaining limitation.

This is a terminal tool. Do not call it together with other tool calls."""


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


class CompletionRunState(StrEnum):
    """Lifecycle states for one completion-aware agent run."""

    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class CompletionSubmissionStatus(StrEnum):
    """Application outcomes for a completion submission attempt."""

    ACCEPTED = "accepted"
    ALREADY_ACCEPTED = "already_accepted"


class CompletionErrorCode(StrEnum):
    """Stable application errors for terminal completion submission."""

    COMPLETION_NOT_ALLOWED = "COMPLETION_NOT_ALLOWED"
    COMPLETION_GUARD_FAILED = "COMPLETION_GUARD_FAILED"
    VERIFICATION_REQUIREMENT_NOT_MET = "VERIFICATION_REQUIREMENT_NOT_MET"
    RUN_ALREADY_COMPLETED = "RUN_ALREADY_COMPLETED"
    IDEMPOTENCY_KEY_CONFLICT = "IDEMPOTENCY_KEY_CONFLICT"
    SUBMIT_CANCELLED = "SUBMIT_CANCELLED"
    SUBMIT_TIMEOUT = "SUBMIT_TIMEOUT"
    PERSISTENCE_ERROR = "PERSISTENCE_ERROR"
    INTERNAL_COMPLETION_ERROR = "INTERNAL_COMPLETION_ERROR"


@dataclass(frozen=True, slots=True)
class CompletionSubmission:
    """Validated model-facing payload for one terminal completion submission."""

    outcome: CompletionOutcome
    summary: str
    verification: CompletionVerification

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, CompletionOutcome):
            msg = "completion outcome must be a known completion outcome"
            raise TypeError(msg)
        if not isinstance(self.summary, str) or not self.summary or len(self.summary) > MAX_COMPLETION_SUMMARY_CHARS:
            msg = "completion summary must contain 1 to 12000 characters"
            raise ValueError(msg)
        if not isinstance(self.verification, CompletionVerification):
            msg = "completion verification must be a known completion verification state"
            raise TypeError(msg)


SUBMIT_AND_EXIT_TOOL_DEFINITION = ToolDefinition(
    name=SUBMIT_AND_EXIT_TOOL_NAME,
    description=SUBMIT_AND_EXIT_TOOL_DESCRIPTION,
    argument_schema={
        "type": "object",
        "properties": {
            "outcome": {"type": "string", "enum": tuple(outcome.value for outcome in CompletionOutcome)},
            "summary": {"type": "string", "minLength": 1, "maxLength": MAX_COMPLETION_SUMMARY_CHARS},
            "verification": {
                "type": "string",
                "enum": tuple(verification.value for verification in CompletionVerification),
            },
        },
        "required": ("outcome", "summary", "verification"),
        "additionalProperties": False,
    },
    batch_policy=ToolBatchPolicy.REQUIRE_SOLO,
)


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


@dataclass(frozen=True, slots=True)
class SubmitRunCompletionCommand:
    """Application command for one validated terminal submission."""

    run_id: str
    tool_call_id: str
    submission: CompletionSubmission
    metadata: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_identifier(self.run_id, field_name="run id")
        _validate_identifier(self.tool_call_id, field_name="tool call id")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SubmitRunCompletionResult:
    """Accepted durable completion result for one terminal submission."""

    status: CompletionSubmissionStatus
    record: CompletionRecord


def completion_submission_digest(submission: CompletionSubmission) -> str:
    """Return a stable SHA-256 digest for a validated terminal submission."""
    payload = {
        "outcome": submission.outcome.value,
        "summary": submission.summary,
        "verification": submission.verification.value,
    }
    canonical_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"sha256:{sha256(canonical_json.encode()).hexdigest()}"


def _validate_identifier(value: str, *, field_name: str) -> None:
    if not value or len(value) > MAX_COMPLETION_IDENTIFIER_CHARS or value != value.strip() or "/" in value:
        msg = f"{field_name} must be a bounded non-empty identifier"
        raise ValueError(msg)


__all__ = [
    "DEFAULT_COMPLETION_SUBMIT_TIMEOUT_SECONDS",
    "MAX_COMPLETION_IDENTIFIER_CHARS",
    "MAX_COMPLETION_SUMMARY_CHARS",
    "RUN_ID_CONTEXT_KEY",
    "SHA256_DIGEST_CHARS",
    "SUBMIT_AND_EXIT_TOOL_DEFINITION",
    "SUBMIT_AND_EXIT_TOOL_DESCRIPTION",
    "SUBMIT_AND_EXIT_TOOL_NAME",
    "CompletionCommitResult",
    "CompletionCommitStatus",
    "CompletionErrorCode",
    "CompletionOutcome",
    "CompletionRecord",
    "CompletionRunState",
    "CompletionSubmission",
    "CompletionSubmissionStatus",
    "CompletionVerification",
    "SubmitRunCompletionCommand",
    "SubmitRunCompletionResult",
    "completion_submission_digest",
]
