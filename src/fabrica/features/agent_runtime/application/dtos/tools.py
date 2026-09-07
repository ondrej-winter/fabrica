"""Application DTOs for bounded tool-loop runtime orchestration."""

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from types import MappingProxyType
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos.runtime import (
    MAX_CONTEXT_TEXT_CHARS,
    RuntimeObservation,
    SafeRuntimeMetadataValue,
)

DEFAULT_MAX_TOOL_ITERATIONS = 4
DEFAULT_MAX_TOOL_CALLS_PER_TURN = 8
DEFAULT_MAX_TOOL_RESULT_CHARS = 4_000
MAX_TOOL_NAME_CHARS = 80
MAX_TOOL_CALL_ID_CHARS = 120
MAX_TOOL_DESCRIPTION_CHARS = 1_000
MAX_TOOL_ERROR_MESSAGE_CHARS = 1_000
MAX_TOOL_RESPONSE_TEXT_CHARS = 20_000
# Multipart content must carry one accepted read-file text result without
# truncating its independently bounded 48,000-character output.
MAX_TOOL_CONTENT_TEXT_CHARS = 48_000
MAX_TOOL_ARGUMENT_NESTING_DEPTH = 8
MAX_TOOL_ARGUMENT_MAPPING_ENTRIES = 100
MAX_TOOL_ARGUMENT_SEQUENCE_ENTRIES = 100
MAX_TOOL_ARGUMENT_STRING_CHARS = 20_000
# The workspace-editing public contract accepts a 256 KiB canonical patch body.
# This exception remains deliberately scoped to one top-level argument of one
# explicitly named tool; all other argument strings retain the generic bound.
APPLY_PATCH_TOOL_NAME = "apply_patch"
APPLY_PATCH_INPUT_ARGUMENT_NAME = "input"
MAX_APPLY_PATCH_INPUT_CHARS = 262_144
# A registered tool may return one textual structured-result part plus one binary
# image part for each member of a 20-file batch.
MAX_TOOL_CONTENT_PARTS = 40
MAX_TOOL_IMAGE_BYTES = 10_000_000
SAFE_TOOL_IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")
type ToolArgumentSchemaValue = (
    str | int | float | bool | tuple[ToolArgumentSchemaValue, ...] | Mapping[str, ToolArgumentSchemaValue] | None
)
type ToolArgumentValue = (
    str | int | float | bool | tuple[ToolArgumentValue, ...] | Mapping[str, ToolArgumentValue] | None
)
type ToolLoopTerminalHook = Callable[[Mapping[str, object]], Awaitable[None]]


class ToolMutationGuarantee(StrEnum):
    """Mutation guarantee carried by typed registered-tool outcomes."""

    NO_MUTATION = "no_mutation"
    COMMITTED = "committed"
    REVERSIBLE_EFFECTS_RETAINED = "reversible_effects_retained"
    PARTIAL_OR_UNCERTAIN_MUTATION = "partial_or_uncertain_mutation"


class ToolOutcomeStatus(StrEnum):
    """Typed registered-tool outcome statuses before model-channel adaptation."""

    SUCCESS = "success"
    REJECTED = "rejected"
    TOOL_FAILURE = "tool_failure"
    FATAL = "fatal"


class ToolExecutionRuntimeDisposition(StrEnum):
    """Runtime loop disposition requested by a typed registered-tool outcome."""

    CONTINUE_MODEL = "continue_model"
    STOP_RUNTIME = "stop_runtime"


class ToolBatchPolicy(StrEnum):
    """Whether a registered tool may share one model response with other calls."""

    ALLOW_MIXED = "allow_mixed"
    REQUIRE_SOLO = "require_solo"


@dataclass(frozen=True, slots=True)
class ToolTextContent:
    """Provider-neutral bounded text content returned by a registered tool."""

    text: str

    def __post_init__(self) -> None:
        if len(self.text) > MAX_TOOL_CONTENT_TEXT_CHARS:
            msg = "tool text content exceeds the safe response bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ToolImageContent:
    """Provider-neutral verified image bytes returned by a registered tool."""

    data: bytes
    media_type: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", bytes(self.data))
        if not self.data:
            msg = "tool image content must not be empty"
            raise ValueError(msg)
        if len(self.data) > MAX_TOOL_IMAGE_BYTES:
            msg = "tool image content exceeds the safe image bound"
            raise ValueError(msg)
        if self.media_type not in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
            msg = "tool image content media type is unsupported"
            raise ValueError(msg)


type ToolContentPart = ToolTextContent | ToolImageContent


class ToolCancellationSignal(Protocol):
    """Narrow cancellation signal exposed to async registered-tool handlers."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        ...

    async def wait_until_cancelled(self) -> None:
        """Wait until cancellation is requested."""
        ...


class ToolCallResultStatus(StrEnum):
    """Normalized outcomes for one requested tool invocation."""

    SUCCESS = "success"
    REJECTED = "rejected"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    TOOL_FAILURE = "tool_failure"
    TIMEOUT = "timeout"
    LIMIT_EXCEEDED = "limit_exceeded"
    ADAPTER_ERROR = "adapter_error"


class ToolLoopRunStatus(StrEnum):
    """Normalized outcomes for a bounded tool-loop run."""

    SUCCESS = "success"
    MODEL_ERROR = "model_error"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_TOOL_REQUEST = "invalid_tool_request"
    TOOL_FAILURE = "tool_failure"
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_LIMIT_EXCEEDED = "tool_limit_exceeded"
    TOOL_ADAPTER_ERROR = "tool_adapter_error"
    MAX_ITERATIONS_EXCEEDED = "max_iterations_exceeded"
    COMPLETION_TOOL_REQUIRED = "completion_tool_required"
    ACTIVE_SKILL_CONTEXT_OVERFLOW = "active_skill_context_overflow"
    ACTIVE_SKILL_CONTEXT_MALFORMED = "active_skill_context_malformed"


@dataclass(frozen=True, slots=True)
class ToolLoopLimits:
    """Bounds applied to one application-owned tool loop."""

    max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS
    max_tool_calls_per_turn: int = DEFAULT_MAX_TOOL_CALLS_PER_TURN
    max_tool_result_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS
    require_completion_tool: bool = False

    def __post_init__(self) -> None:
        if self.max_tool_iterations < 1:
            msg = "max_tool_iterations must be at least 1"
            raise ValueError(msg)
        if self.max_tool_calls_per_turn < 1:
            msg = "max_tool_calls_per_turn must be at least 1"
            raise ValueError(msg)
        if self.max_tool_result_chars < 1:
            msg = "max_tool_result_chars must be at least 1"
            raise ValueError(msg)
        if self.max_tool_result_chars > MAX_CONTEXT_TEXT_CHARS:
            msg = "max_tool_result_chars exceeds the local runtime context block bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ToolExecutionPhaseDeadline:
    """Timezone-aware deadline for one registered-tool execution phase."""

    phase: str
    deadline_at: datetime

    def __post_init__(self) -> None:
        _validate_tool_identifier(self.phase, field_name="tool execution phase", max_chars=MAX_TOOL_NAME_CHARS)
        if self.deadline_at.tzinfo is None or self.deadline_at.utcoffset() is None:
            msg = "tool execution phase deadline must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    """Runtime-owned context passed to async registered-tool handlers."""

    call_id: str
    argument_digest: str
    cancellation: ToolCancellationSignal
    phase_deadlines: tuple[ToolExecutionPhaseDeadline, ...] = field(default_factory=tuple)
    opaque_values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_tool_identifier(self.call_id, field_name="tool call id", max_chars=MAX_TOOL_CALL_ID_CHARS)
        _validate_tool_digest(self.argument_digest)
        phases = [deadline.phase for deadline in self.phase_deadlines]
        if len(set(phases)) != len(phases):
            msg = "tool execution phase deadlines must be unique by phase"
            raise ValueError(msg)
        object.__setattr__(self, "phase_deadlines", tuple(self.phase_deadlines))
        object.__setattr__(self, "opaque_values", MappingProxyType(dict(self.opaque_values)))

    def phase_deadline(self, phase: str) -> datetime | None:
        """Return the deadline for a named phase when one was provided."""
        for deadline in self.phase_deadlines:
            if deadline.phase == phase:
                return deadline.deadline_at
        return None


@dataclass(frozen=True, slots=True)
class RegisteredToolOutcome:
    """Typed outcome returned by async registered-tool handlers."""

    status: ToolOutcomeStatus
    mutation_guarantee: ToolMutationGuarantee
    runtime_disposition: ToolExecutionRuntimeDisposition = ToolExecutionRuntimeDisposition.CONTINUE_MODEL
    result_text: str | None = None
    content: tuple[ToolContentPart, ...] = field(default_factory=tuple)
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    details: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_tool_outcome_status_invariants(self)
        if self.error_code is not None:
            _validate_tool_identifier(
                self.error_code,
                field_name="tool outcome error code",
                max_chars=MAX_TOOL_NAME_CHARS,
            )
        if self.result_text is not None and len(self.result_text) > MAX_TOOL_RESPONSE_TEXT_CHARS:
            msg = "tool outcome result text exceeds the safe response bound"
            raise ValueError(msg)
        if self.error_message is not None and len(self.error_message) > MAX_TOOL_ERROR_MESSAGE_CHARS:
            msg = "tool outcome error message exceeds the safe error bound"
            raise ValueError(msg)
        _validate_tool_content(self.content)
        object.__setattr__(self, "content", tuple(self.content))
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))

    @classmethod
    def model_continue_success(
        cls,
        *,
        mutation_guarantee: ToolMutationGuarantee,
        result_text: str | None = None,
        content: tuple[ToolContentPart, ...] = (),
        details: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> RegisteredToolOutcome:
        """Create a successful outcome that lets the model loop continue."""
        return cls(
            status=ToolOutcomeStatus.SUCCESS,
            mutation_guarantee=mutation_guarantee,
            result_text=result_text,
            content=content,
            details=details or {},
        )

    @classmethod
    def recoverable_rejection(
        cls,
        *,
        error_code: str,
        error_message: str,
        details: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> RegisteredToolOutcome:
        """Create a recoverable no-mutation rejection shown to the model."""
        return cls(
            status=ToolOutcomeStatus.REJECTED,
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            error_code=error_code,
            error_message=error_message,
            retryable=True,
            details=details or {},
        )

    @classmethod
    def tool_failure(
        cls,
        *,
        error_code: str,
        error_message: str,
        details: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> RegisteredToolOutcome:
        """Create an ordinary non-fatal tool failure outcome."""
        return cls(
            status=ToolOutcomeStatus.TOOL_FAILURE,
            mutation_guarantee=ToolMutationGuarantee.NO_MUTATION,
            error_code=error_code,
            error_message=error_message,
            details=details or {},
        )

    @classmethod
    def fatal_runtime_stop(
        cls,
        *,
        error_code: str,
        mutation_guarantee: ToolMutationGuarantee,
        error_message: str,
        details: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> RegisteredToolOutcome:
        """Create a fatal outcome that stops the runtime loop."""
        return cls(
            status=ToolOutcomeStatus.FATAL,
            mutation_guarantee=mutation_guarantee,
            runtime_disposition=ToolExecutionRuntimeDisposition.STOP_RUNTIME,
            error_code=error_code,
            error_message=error_message,
            details=details or {},
        )

    def to_bounded_json(self, *, max_chars: int) -> str:
        """Serialize as compact JSON while preserving mandatory status fields."""
        if max_chars < 1:
            msg = "max_chars must be at least 1"
            raise ValueError(msg)

        full_payload = self._payload(include_optional=True)
        full_serialized = _compact_json(full_payload)
        if len(full_serialized) <= max_chars:
            return full_serialized

        mandatory_serialized = _compact_json(self._payload(include_optional=False))
        if len(mandatory_serialized) > max_chars:
            msg = "mandatory tool outcome fields exceed output bound"
            raise ValueError(msg)
        return mandatory_serialized

    def _payload(self, *, include_optional: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status.value,
            "success": self.status is ToolOutcomeStatus.SUCCESS,
            "mutation_guarantee": self.mutation_guarantee.value,
            "fatal": self.runtime_disposition is ToolExecutionRuntimeDisposition.STOP_RUNTIME,
        }
        if self.error_code is not None:
            payload["error"] = {
                "code": self.error_code,
                "retryable": self.retryable,
            }
        if include_optional:
            if self.result_text is not None:
                payload["result"] = self.result_text
            if self.error_message is not None:
                error = self._error_payload()
                error["message"] = self.error_message
                payload["error"] = error
            if self.details:
                payload["details"] = dict(self.details)
        return payload

    def _error_payload(self) -> dict[str, object]:
        if self.error_code is None:
            return {}
        return {"code": self.error_code, "retryable": self.retryable}


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Backend-neutral description of an explicitly available tool."""

    name: str
    description: str
    argument_schema: Mapping[str, ToolArgumentSchemaValue] = field(default_factory=dict)
    batch_policy: ToolBatchPolicy = ToolBatchPolicy.ALLOW_MIXED

    def __post_init__(self) -> None:
        _validate_tool_identifier(self.name, field_name="tool name", max_chars=MAX_TOOL_NAME_CHARS)
        if not self.description:
            msg = "tool description must not be empty"
            raise ValueError(msg)
        if len(self.description) > MAX_TOOL_DESCRIPTION_CHARS:
            msg = "tool description exceeds the safe description bound"
            raise ValueError(msg)
        object.__setattr__(self, "argument_schema", MappingProxyType(dict(self.argument_schema)))


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    """Normalized model request to invoke one explicitly available tool."""

    call_id: str
    tool_name: str
    arguments: Mapping[str, ToolArgumentValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_tool_identifier(self.call_id, field_name="tool call id", max_chars=MAX_TOOL_CALL_ID_CHARS)
        _validate_tool_identifier(self.tool_name, field_name="tool name", max_chars=MAX_TOOL_NAME_CHARS)
        object.__setattr__(self, "arguments", _normalize_tool_arguments(self.arguments, tool_name=self.tool_name))


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    """Application-safe result for one tool invocation."""

    call_id: str
    tool_name: str
    status: ToolCallResultStatus
    runtime_disposition: ToolExecutionRuntimeDisposition = ToolExecutionRuntimeDisposition.CONTINUE_MODEL
    result_text: str | None = None
    content: tuple[ToolContentPart, ...] = field(default_factory=tuple)
    error_message: str | None = None
    observations: tuple[RuntimeObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_tool_identifier(self.call_id, field_name="tool call id", max_chars=MAX_TOOL_CALL_ID_CHARS)
        _validate_tool_identifier(self.tool_name, field_name="tool name", max_chars=MAX_TOOL_NAME_CHARS)
        if self.result_text is not None and len(self.result_text) > MAX_TOOL_RESPONSE_TEXT_CHARS:
            msg = "tool result text exceeds the safe response bound"
            raise ValueError(msg)
        if self.error_message is not None and len(self.error_message) > MAX_TOOL_ERROR_MESSAGE_CHARS:
            msg = "tool error message exceeds the safe error bound"
            raise ValueError(msg)
        _validate_tool_content(self.content)
        object.__setattr__(self, "content", tuple(self.content))
        object.__setattr__(self, "observations", tuple(self.observations))

    def bounded(self, limits: ToolLoopLimits) -> ToolCallResult:
        """Return a copy whose result text fits the configured loop bound."""
        if self.result_text is None or len(self.result_text) <= limits.max_tool_result_chars:
            return self
        return ToolCallResult(
            call_id=self.call_id,
            tool_name=self.tool_name,
            status=self.status,
            runtime_disposition=self.runtime_disposition,
            result_text=self.result_text[: limits.max_tool_result_chars],
            content=self.content,
            error_message=self.error_message,
            observations=(
                *self.observations,
                RuntimeObservation(
                    message="tool result text was truncated",
                    metadata={"tool_name": self.tool_name, "max_chars": limits.max_tool_result_chars},
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class ToolAwareModelResponse:
    """Normalized model response containing final output or requested tool calls."""

    output_text: str | None = None
    tool_calls: tuple[ToolCallRequest, ...] = field(default_factory=tuple)
    observations: tuple[RuntimeObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.output_text is None and not self.tool_calls:
            msg = "model response must include output text or tool calls"
            raise ValueError(msg)
        if self.output_text is not None and self.tool_calls:
            msg = "model response must not include both output text and tool calls"
            raise ValueError(msg)
        if self.output_text is not None and len(self.output_text) > MAX_TOOL_RESPONSE_TEXT_CHARS:
            msg = "model output text exceeds the safe response bound"
            raise ValueError(msg)
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        object.__setattr__(self, "observations", tuple(self.observations))


@dataclass(frozen=True, slots=True)
class ToolLoopRunResult:
    """Normalized application-safe result for a bounded tool loop."""

    status: ToolLoopRunStatus
    output_text: str | None = None
    tool_results: tuple[ToolCallResult, ...] = field(default_factory=tuple)
    observations: tuple[RuntimeObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_results", tuple(self.tool_results))
        object.__setattr__(self, "observations", tuple(self.observations))

    @property
    def succeeded(self) -> bool:
        """Return whether the tool loop completed successfully."""
        return self.status is ToolLoopRunStatus.SUCCESS


def _validate_tool_identifier(value: str, *, field_name: str, max_chars: int) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if len(value) > max_chars:
        msg = f"{field_name} exceeds the safe identifier bound"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)
    if any(character not in SAFE_TOOL_IDENTIFIER_CHARS for character in value):
        msg = f"{field_name} contains unsupported characters"
        raise ValueError(msg)


def _validate_tool_outcome_status_invariants(outcome: RegisteredToolOutcome) -> None:
    if outcome.status is ToolOutcomeStatus.SUCCESS:
        _validate_success_outcome(outcome)
    elif outcome.status is ToolOutcomeStatus.REJECTED:
        _validate_rejected_outcome(outcome)
    elif outcome.status is ToolOutcomeStatus.FATAL:
        _validate_fatal_outcome(outcome)
    elif outcome.error_code is None:  # pragma: no cover - DTO invariants reject code-less TOOL_FAILURE outcomes first.
        msg = "tool failure outcomes must include an error code"
        raise ValueError(msg)


def _validate_success_outcome(outcome: RegisteredToolOutcome) -> None:
    if outcome.error_code is not None:
        msg = "success outcomes must not include an error code"
        raise ValueError(msg)
    if outcome.runtime_disposition not in {
        ToolExecutionRuntimeDisposition.CONTINUE_MODEL,
        ToolExecutionRuntimeDisposition.STOP_RUNTIME,
    }:
        msg = "success outcomes must have a known runtime disposition"
        raise ValueError(msg)


def _validate_rejected_outcome(outcome: RegisteredToolOutcome) -> None:
    if outcome.error_code is None:
        msg = "recoverable rejection outcomes must include an error code"
        raise ValueError(msg)
    if outcome.runtime_disposition is ToolExecutionRuntimeDisposition.STOP_RUNTIME:
        msg = "recoverable rejection outcomes must not stop the runtime"
        raise ValueError(msg)


def _validate_fatal_outcome(outcome: RegisteredToolOutcome) -> None:
    if outcome.error_code is None:
        msg = "fatal outcomes must include an error code"
        raise ValueError(msg)
    if outcome.runtime_disposition is not ToolExecutionRuntimeDisposition.STOP_RUNTIME:
        msg = "fatal outcomes must stop the runtime"
        raise ValueError(msg)


def canonical_tool_arguments_json(arguments: Mapping[str, ToolArgumentValue], *, tool_name: str | None = None) -> str:
    """Return deterministic compact JSON for normalized tool arguments."""
    return json.dumps(
        _json_serializable_tool_argument_value(_normalize_tool_arguments(arguments, tool_name=tool_name)),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_tool_arguments_digest(arguments: Mapping[str, ToolArgumentValue], *, tool_name: str | None = None) -> str:
    """Return a SHA-256 digest for canonical normalized tool arguments."""
    canonical_json = canonical_tool_arguments_json(arguments, tool_name=tool_name)
    return f"sha256:{sha256(canonical_json.encode('utf-8')).hexdigest()}"


def _compact_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _normalize_tool_arguments(
    arguments: Mapping[str, ToolArgumentValue], *, tool_name: str | None = None
) -> Mapping[str, ToolArgumentValue]:
    if not isinstance(arguments, Mapping):
        msg = "tool arguments must be a mapping"
        raise TypeError(msg)
    if len(arguments) > MAX_TOOL_ARGUMENT_MAPPING_ENTRIES:
        msg = "tool arguments exceed the safe mapping entry bound"
        raise ValueError(msg)
    normalized: dict[str, ToolArgumentValue] = {}
    for key, value in arguments.items():
        if not isinstance(key, str):
            msg = "tool argument keys must be strings"
            raise TypeError(msg)
        if len(key) > MAX_TOOL_ARGUMENT_STRING_CHARS:
            msg = "tool argument keys exceed the safe string bound"
            raise ValueError(msg)
        normalized[key] = _normalize_top_level_tool_argument_value(key, value, tool_name=tool_name)
    return MappingProxyType(normalized)


def _normalize_top_level_tool_argument_value(key: str, value: object, *, tool_name: str | None) -> ToolArgumentValue:
    if tool_name == APPLY_PATCH_TOOL_NAME and key == APPLY_PATCH_INPUT_ARGUMENT_NAME and isinstance(value, str):
        if len(value) > MAX_APPLY_PATCH_INPUT_CHARS:
            msg = "apply_patch input exceeds the accepted character limit"
            raise ValueError(msg)
        return value
    return _normalize_tool_argument_value(value, depth=1)


def _normalize_tool_argument_value(value: object, *, depth: int) -> ToolArgumentValue:
    if depth > MAX_TOOL_ARGUMENT_NESTING_DEPTH:
        msg = "tool arguments exceed the safe nesting depth"
        raise ValueError(msg)
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            msg = "tool argument numbers must be finite"
            raise ValueError(msg)
        return value
    if isinstance(value, str):
        if len(value) > MAX_TOOL_ARGUMENT_STRING_CHARS:
            msg = "tool argument strings exceed the safe string bound"
            raise ValueError(msg)
        return value
    if isinstance(value, Mapping):
        return _normalize_tool_arguments_nested(value, depth=depth)
    if isinstance(value, tuple):
        if len(value) > MAX_TOOL_ARGUMENT_SEQUENCE_ENTRIES:
            msg = "tool argument sequences exceed the safe entry bound"
            raise ValueError(msg)
        return tuple(_normalize_tool_argument_value(item, depth=depth + 1) for item in value)
    msg = "tool arguments must contain immutable JSON values"
    raise TypeError(msg)


def _normalize_tool_arguments_nested(
    arguments: Mapping[object, object], *, depth: int
) -> Mapping[str, ToolArgumentValue]:
    if len(arguments) > MAX_TOOL_ARGUMENT_MAPPING_ENTRIES:
        msg = "tool argument mappings exceed the safe entry bound"
        raise ValueError(msg)
    normalized: dict[str, ToolArgumentValue] = {}
    for key, value in arguments.items():
        if not isinstance(key, str):
            msg = "tool argument keys must be strings"
            raise TypeError(msg)
        if len(key) > MAX_TOOL_ARGUMENT_STRING_CHARS:
            msg = "tool argument keys exceed the safe string bound"
            raise ValueError(msg)
        normalized[key] = _normalize_tool_argument_value(value, depth=depth + 1)
    return MappingProxyType(normalized)


def _json_serializable_tool_argument_value(value: ToolArgumentValue) -> object:
    if isinstance(value, Mapping):
        return {key: _json_serializable_tool_argument_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_serializable_tool_argument_value(item) for item in value]
    return value


def _validate_tool_content(content: tuple[ToolContentPart, ...]) -> None:
    if len(content) > MAX_TOOL_CONTENT_PARTS:
        msg = "tool content exceeds the safe part bound"
        raise ValueError(msg)
    if any(not isinstance(part, ToolTextContent | ToolImageContent) for part in content):
        msg = "tool content must contain provider-neutral text or image parts"
        raise TypeError(msg)


def _validate_tool_digest(value: str) -> None:
    if not value.startswith("sha256:") or len(value) != len("sha256:") + 64:
        msg = "tool argument digest must be a sha256 digest"
        raise ValueError(msg)
    digest = value.removeprefix("sha256:")
    if any(character not in "0123456789abcdef" for character in digest):
        msg = "tool argument digest must use lowercase hexadecimal"
        raise ValueError(msg)
