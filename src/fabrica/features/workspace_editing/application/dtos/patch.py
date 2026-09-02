"""Immutable DTOs for the apply-patch application boundary."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

DEFAULT_MAX_PATCH_INPUT_CHARS = 262_144
DEFAULT_MAX_PATCH_OUTPUT_CHARS = 4_000
MAX_PATCH_PATH_CHARS = 4_096
MAX_PATCH_DIGEST_CHARS = len("sha256:") + 64
MAX_PATCH_ERROR_CODE_CHARS = 80
MAX_PATCH_ERROR_MESSAGE_CHARS = 1_000
MAX_PATCH_EXCERPT_CHARS = 500

SafePatchMetadataValue = str | int | float | bool | None


class PatchActionKind(StrEnum):
    """Model-authored operations inside one apply-patch request."""

    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"


class PatchHunkLineKind(StrEnum):
    """Tagged line kinds parsed from an update hunk."""

    CONTEXT = "context"
    DELETE = "delete"
    INSERT = "insert"


class PatchMatchQuality(StrEnum):
    """How a parsed hunk matched an immutable source snapshot."""

    EXACT = "exact"
    TRAILING_WHITESPACE = "trailing_whitespace"


class PatchResultStatus(StrEnum):
    """Terminal statuses for one apply-patch call."""

    COMMITTED = "committed"
    REJECTED = "rejected"
    COMMIT_FAILED_ROLLED_BACK = "commit_failed_rolled_back"
    PARTIAL_COMMIT = "partial_commit"
    ROLLBACK_FAILED = "rollback_failed"
    INDETERMINATE_COMMIT_STATE = "indeterminate_commit_state"
    RECOVERY_REQUIRED = "recovery_required"


class PatchMutationGuarantee(StrEnum):
    """Mutation guarantees reported to the runtime and user."""

    NO_MUTATION = "no_mutation"
    COMMITTED = "committed"
    REVERSIBLE_EFFECTS_RETAINED = "reversible_effects_retained"
    PARTIAL_OR_UNCERTAIN_MUTATION = "partial_or_uncertain_mutation"


class PatchRuntimeMapping(StrEnum):
    """Runtime disposition category for a patch result or error."""

    SUCCESS = "success"
    REJECTED = "rejected"
    TOOL_FAILURE = "tool_failure"
    ADAPTER_ERROR = "adapter_error"
    FATAL = "fatal"


class PatchErrorPhase(StrEnum):
    """Lifecycle phase that produced a patch error."""

    PARSING = "parsing"
    DECODING = "decoding"
    MATCHING = "matching"
    PLANNING = "planning"
    POLICY = "policy"
    APPROVAL = "approval"
    CAPABILITY = "capability"
    SNAPSHOT = "snapshot"
    PREPARATION = "preparation"
    STAGING = "staging"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    CLEANUP = "cleanup"
    RECOVERY = "recovery"


class PatchExecutionPhase(StrEnum):
    """Runtime-controlled checkpoints in the apply-patch lifecycle."""

    LEASE = "lease"
    PLANNING = "planning"
    APPROVAL = "approval"
    STAGING = "staging"
    COMMIT = "commit"
    ROLLBACK = "rollback"


class PatchCancellationSignal(Protocol):
    """Runtime cancellation state observed at patch lifecycle checkpoints."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether the current patch call has been cancelled."""
        ...


@dataclass(frozen=True, slots=True)
class PatchExecutionContext:
    """Runtime-owned cancellation and phase-deadline controls for one patch call."""

    cancellation: PatchCancellationSignal
    phase_deadlines: Mapping[PatchExecutionPhase, datetime] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_deadlines = dict(self.phase_deadlines)
        for phase, deadline in normalized_deadlines.items():
            if not isinstance(phase, PatchExecutionPhase):
                msg = "patch execution deadlines must use patch execution phases"
                raise TypeError(msg)
            if deadline.tzinfo is None or deadline.utcoffset() is None:
                msg = "patch execution phase deadlines must be timezone-aware"
                raise ValueError(msg)
        object.__setattr__(self, "phase_deadlines", MappingProxyType(normalized_deadlines))

    def deadline_for(self, phase: PatchExecutionPhase) -> datetime | None:
        """Return the deadline for a patch lifecycle phase when the host supplied one."""
        return self.phase_deadlines.get(phase)


class PatchDirectoryPlannedEffect(StrEnum):
    """Derived directory effects planned from Add and Move destinations."""

    CREATE_DIRECTORY = "create_directory"


class PatchDirectoryOutcomeState(StrEnum):
    """Final state for a planned directory effect."""

    CREATED = "created"
    REMOVED = "removed"
    RETAINED_EXTERNAL_CONTENT = "retained_external_content"
    REMOVAL_UNCERTAIN = "removal_uncertain"
    NOT_CREATED = "not_created"


class PatchPathOutcomeState(StrEnum):
    """Final state for a planned file path operation."""

    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    UNCHANGED = "unchanged"
    UNKNOWN = "unknown"


class PatchCommitOperation(StrEnum):
    """Deterministic commit operation categories for an immutable patch plan."""

    CREATE_DIRECTORY = "create_directory"
    WRITE_FILE = "write_file"
    DELETE_FILE = "delete_file"
    MOVE_FILE = "move_file"


@dataclass(frozen=True, slots=True)
class PatchLimits:
    """Bounds applied while accepting and serializing one patch request."""

    max_input_chars: int = DEFAULT_MAX_PATCH_INPUT_CHARS
    max_output_chars: int = DEFAULT_MAX_PATCH_OUTPUT_CHARS

    def __post_init__(self) -> None:
        if self.max_input_chars < 1:
            msg = "max_input_chars must be at least 1"
            raise ValueError(msg)
        if self.max_output_chars < 1:
            msg = "max_output_chars must be at least 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PatchHunkLine:
    """One parsed hunk line after removing the protocol prefix."""

    kind: PatchHunkLineKind
    text: str


@dataclass(frozen=True, slots=True)
class PatchHunk:
    """Immutable parsed hunk with optional anchor semantics."""

    index: int
    lines: tuple[PatchHunkLine, ...] = field(default_factory=tuple)
    anchor: str | None = None
    insert_relative_to_anchor: str | None = None
    assert_eof: bool = False
    match_quality: PatchMatchQuality | None = None

    def __post_init__(self) -> None:
        if self.index < 1:
            msg = "hunk index must be one-based"
            raise ValueError(msg)
        if self.insert_relative_to_anchor not in {None, "before", "after"}:
            msg = "insert_relative_to_anchor must be before, after, or None"
            raise ValueError(msg)
        object.__setattr__(self, "lines", tuple(self.lines))


@dataclass(frozen=True, slots=True)
class PatchAction:
    """One model-authored action parsed from an apply-patch body."""

    index: int
    kind: PatchActionKind
    path: str
    destination_path: str | None = None
    hunks: tuple[PatchHunk, ...] = field(default_factory=tuple)
    added_lines: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.index < 0:
            msg = "action index must not be negative"
            raise ValueError(msg)
        _validate_workspace_relative_path(self.path, field_name="path")
        if self.destination_path is not None:
            _validate_workspace_relative_path(self.destination_path, field_name="destination_path")
        if self.kind is PatchActionKind.MOVE and self.destination_path is None:
            msg = "move actions must include a destination_path"
            raise ValueError(msg)
        if self.kind is not PatchActionKind.MOVE and self.destination_path is not None:
            msg = "only move actions may include a destination_path"
            raise ValueError(msg)
        object.__setattr__(self, "hunks", tuple(self.hunks))
        object.__setattr__(self, "added_lines", tuple(self.added_lines))


@dataclass(frozen=True, slots=True)
class PatchPathEvidence:
    """Sanitized evidence for a file path snapshot or terminal state."""

    path: str
    exists: bool
    content_digest: str | None = None
    identity_digest: str | None = None
    metadata: Mapping[str, SafePatchMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")
        if self.content_digest is not None:
            _validate_digest(self.content_digest, field_name="content_digest")
        if self.identity_digest is not None:
            _validate_digest(self.identity_digest, field_name="identity_digest")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PatchDirectoryOutcome:
    """Reported outcome for one planned derived directory effect."""

    path: str
    planned_effect: PatchDirectoryPlannedEffect
    final_state: PatchDirectoryOutcomeState
    reason: str | None = None
    identity_digest: str | None = None

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")
        if self.identity_digest is not None:
            _validate_digest(self.identity_digest, field_name="identity_digest")


@dataclass(frozen=True, slots=True)
class PatchPathOutcome:
    """Reported outcome for one planned file action."""

    path: str
    planned_operation: PatchActionKind
    final_state: PatchPathOutcomeState
    destination_path: str | None = None
    evidence: PatchPathEvidence | None = None

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")
        if self.destination_path is not None:
            _validate_workspace_relative_path(self.destination_path, field_name="destination_path")


@dataclass(frozen=True, slots=True)
class PatchCommitStep:
    """One deterministic commit schedule step derived from a patch plan."""

    operation: PatchCommitOperation
    path: str
    action_index: int | None = None
    destination_path: str | None = None

    def __post_init__(self) -> None:
        _validate_workspace_relative_path(self.path, field_name="path")
        if self.action_index is not None and self.action_index < 0:
            msg = "action_index must not be negative"
            raise ValueError(msg)
        if self.destination_path is not None:
            _validate_workspace_relative_path(self.destination_path, field_name="destination_path")


@dataclass(frozen=True, slots=True)
class PatchApprovalPreview:
    """Bounded user-facing summary that must be approved before mutation."""

    text: str
    truncated: bool = False

    def __post_init__(self) -> None:
        if self.truncated:
            msg = "truncated apply-patch previews cannot be approved"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PatchChangeSummary:
    """Compact result summary for one planned or committed file action."""

    index: int
    operation: PatchActionKind
    path: str
    destination_path: str | None = None
    hunks: int = 0
    match_quality: PatchMatchQuality | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            msg = "change index must not be negative"
            raise ValueError(msg)
        _validate_workspace_relative_path(self.path, field_name="path")
        if self.destination_path is not None:
            _validate_workspace_relative_path(self.destination_path, field_name="destination_path")
        if self.hunks < 0:
            msg = "hunks must not be negative"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PatchPlan:
    """Immutable approved patch plan summary before filesystem commit."""

    plan_digest: str
    actions: tuple[PatchAction, ...] = field(default_factory=tuple)
    changes: tuple[PatchChangeSummary, ...] = field(default_factory=tuple)
    created_directories: tuple[PatchDirectoryOutcome, ...] = field(default_factory=tuple)
    path_evidence: tuple[PatchPathEvidence, ...] = field(default_factory=tuple)
    commit_steps: tuple[PatchCommitStep, ...] = field(default_factory=tuple)
    approval_preview: PatchApprovalPreview | None = None

    def __post_init__(self) -> None:
        _validate_digest(self.plan_digest, field_name="plan_digest")
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "changes", tuple(self.changes))
        object.__setattr__(self, "created_directories", tuple(self.created_directories))
        object.__setattr__(self, "path_evidence", tuple(self.path_evidence))
        object.__setattr__(self, "commit_steps", tuple(self.commit_steps))


@dataclass(frozen=True, slots=True)
class PatchError:
    """Structured, bounded patch error payload."""

    code: str
    phase: PatchErrorPhase
    retryable: bool
    mutation_guarantee: PatchMutationGuarantee
    runtime_mapping: PatchRuntimeMapping
    message: str | None = None
    metadata: Mapping[str, SafePatchMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_error_code(self.code)
        if self.message is not None and len(self.message) > MAX_PATCH_ERROR_MESSAGE_CHARS:
            msg = "patch error message exceeds the safe error bound"
            raise ValueError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PatchResult:
    """Application-safe result for one apply-patch call."""

    status: PatchResultStatus
    mutation_guarantee: PatchMutationGuarantee
    plan_digest: str | None = None
    changes: tuple[PatchChangeSummary, ...] = field(default_factory=tuple)
    created_directories: tuple[PatchDirectoryOutcome, ...] = field(default_factory=tuple)
    directory_outcomes: tuple[PatchDirectoryOutcome, ...] = field(default_factory=tuple)
    path_outcomes: tuple[PatchPathOutcome, ...] = field(default_factory=tuple)
    error: PatchError | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_result_invariants(self)
        if self.plan_digest is not None:
            _validate_digest(self.plan_digest, field_name="plan_digest")
        object.__setattr__(self, "changes", tuple(self.changes))
        object.__setattr__(self, "created_directories", tuple(self.created_directories))
        object.__setattr__(self, "directory_outcomes", tuple(self.directory_outcomes))
        object.__setattr__(self, "path_outcomes", tuple(self.path_outcomes))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    @property
    def succeeded(self) -> bool:
        """Return whether the patch committed successfully."""
        return self.status is PatchResultStatus.COMMITTED

    def to_bounded_json(self, *, max_chars: int = DEFAULT_MAX_PATCH_OUTPUT_CHARS) -> str:
        """Serialize as compact JSON while preserving mandatory result fields."""
        if max_chars < 1:
            msg = "max_chars must be at least 1"
            raise ValueError(msg)
        full_serialized = canonical_patch_result_json(self, include_optional=True)
        if len(full_serialized) <= max_chars:
            return full_serialized
        mandatory_serialized = canonical_patch_result_json(self, include_optional=False)
        if len(mandatory_serialized) > max_chars:
            msg = "mandatory patch result fields exceed output bound"
            raise ValueError(msg)
        return mandatory_serialized


def canonical_patch_result_json(result: PatchResult, *, include_optional: bool = True) -> str:
    """Return deterministic compact JSON for a patch result DTO."""
    return json.dumps(_result_payload(result, include_optional=include_optional), sort_keys=True, separators=(",", ":"))


def _result_payload(result: PatchResult, *, include_optional: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "mutation_guarantee": result.mutation_guarantee.value,
        "status": result.status.value,
        "success": result.succeeded,
    }
    if result.error is not None:
        payload["error"] = _error_payload(result.error, include_optional=include_optional)
    if include_optional:
        if result.plan_digest is not None:
            payload["plan_digest"] = result.plan_digest
        if result.changes:
            payload["changes"] = [_change_payload(change) for change in result.changes]
        if result.created_directories:
            payload["created_directories"] = [_directory_payload(item) for item in result.created_directories]
        if result.directory_outcomes:
            payload["directory_outcomes"] = [_directory_payload(item) for item in result.directory_outcomes]
        if result.path_outcomes:
            payload["path_outcomes"] = [_path_outcome_payload(item) for item in result.path_outcomes]
        if result.warnings:
            payload["warnings"] = list(result.warnings)
    return payload


def _error_payload(error: PatchError, *, include_optional: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": error.code,
        "phase": error.phase.value,
        "retryable": error.retryable,
    }
    if include_optional:
        if error.message is not None:
            payload["message"] = error.message
        payload.update(dict(error.metadata))
    return payload


def _change_payload(change: PatchChangeSummary) -> dict[str, object]:
    payload: dict[str, object] = {"index": change.index, "operation": change.operation.value, "path": change.path}
    if change.destination_path is not None:
        payload["destination_path"] = change.destination_path
    if change.hunks:
        payload["hunks"] = change.hunks
    if change.match_quality is not None:
        payload["match_quality"] = change.match_quality.value
    return payload


def _directory_payload(outcome: PatchDirectoryOutcome) -> dict[str, object]:
    payload: dict[str, object] = {
        "final_state": outcome.final_state.value,
        "path": outcome.path,
        "planned_effect": outcome.planned_effect.value,
    }
    if outcome.reason is not None:
        payload["reason"] = outcome.reason
    if outcome.identity_digest is not None:
        payload["identity_digest"] = outcome.identity_digest
    return payload


def _path_outcome_payload(outcome: PatchPathOutcome) -> dict[str, object]:
    payload: dict[str, object] = {
        "final_state": outcome.final_state.value,
        "path": outcome.path,
        "planned_operation": outcome.planned_operation.value,
    }
    if outcome.destination_path is not None:
        payload["destination_path"] = outcome.destination_path
    if outcome.evidence is not None:
        payload["evidence"] = _path_evidence_payload(outcome.evidence)
    return payload


def _path_evidence_payload(evidence: PatchPathEvidence) -> dict[str, object]:
    payload: dict[str, object] = {"exists": evidence.exists, "path": evidence.path}
    if evidence.content_digest is not None:
        payload["content_digest"] = evidence.content_digest
    if evidence.identity_digest is not None:
        payload["identity_digest"] = evidence.identity_digest
    if evidence.metadata:
        payload["metadata"] = dict(evidence.metadata)
    return payload


def _validate_result_invariants(result: PatchResult) -> None:
    if result.status is PatchResultStatus.COMMITTED:
        if result.mutation_guarantee is not PatchMutationGuarantee.COMMITTED:
            msg = "committed results must carry the committed mutation guarantee"
            raise ValueError(msg)
        if result.error is not None:
            msg = "committed results must not include an error"
            raise ValueError(msg)
        return
    if result.error is None:
        msg = "non-committed results must include an error"
        raise ValueError(msg)
    if result.error.mutation_guarantee is not result.mutation_guarantee:
        msg = "result mutation guarantee must match the error table entry"
        raise ValueError(msg)


def _validate_workspace_relative_path(value: str, *, field_name: str) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if len(value) > MAX_PATCH_PATH_CHARS:
        msg = f"{field_name} exceeds the safe path bound"
        raise ValueError(msg)
    if value.startswith("/") or value in {".", ".."} or ".." in value.split("/"):
        msg = f"{field_name} must be workspace-relative and non-escaping"
        raise ValueError(msg)


def _validate_digest(value: str, *, field_name: str) -> None:
    if not value.startswith("sha256:") or len(value) != MAX_PATCH_DIGEST_CHARS:
        msg = f"{field_name} must be a sha256 digest"
        raise ValueError(msg)
    if any(character not in "0123456789abcdef" for character in value.removeprefix("sha256:")):
        msg = f"{field_name} must use lowercase hexadecimal"
        raise ValueError(msg)


def _validate_error_code(value: str) -> None:
    if not value:
        msg = "patch error code must not be empty"
        raise ValueError(msg)
    if len(value) > MAX_PATCH_ERROR_CODE_CHARS:
        msg = "patch error code exceeds the safe identifier bound"
        raise ValueError(msg)
    if value != value.upper() or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in value):
        msg = "patch error code must be an upper snake case identifier"
        raise ValueError(msg)
