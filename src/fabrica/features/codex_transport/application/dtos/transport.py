"""Transport command, result, observation, and usage DTOs."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from fabrica.shared_kernel.model_usage import ModelCostEvidence, ModelUsageEvidence

SafeObservationValue = str | int | float | bool | None
SafeUsageEvidenceValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class CodexTransportObservation:
    """Redacted diagnostic information for Codex transport interactions.

    The ``metadata`` mapping is safe-by-construction: callers must provide only
    redacted, bounded values such as status codes, error categories, counts, or
    short non-secret labels. Raw headers, tokens, cookies, request bodies, and
    response bodies do not belong in this DTO.
    """

    message: str
    metadata: Mapping[str, SafeObservationValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key, value in self.metadata.items():
            if not isinstance(key, str):
                msg = "observation metadata keys must be strings"
                raise TypeError(msg)
            if not _is_safe_observation_value(value):
                msg = f"observation metadata value for {key!r} must be a bounded scalar"
                raise TypeError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


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
class CodexToolDefinition:
    """Provider-neutral tool declaration accepted by the Codex transport boundary."""

    name: str
    description: str
    argument_schema: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.description:
            msg = "Codex tool definitions require a name and description"
            raise ValueError(msg)
        object.__setattr__(self, "argument_schema", MappingProxyType(dict(self.argument_schema)))


@dataclass(frozen=True, slots=True)
class CodexToolResult:
    """Bounded normalized result correlated to one prior model tool call."""

    call_id: str
    tool_name: str
    result_text: str

    def __post_init__(self) -> None:
        if not self.call_id or not self.tool_name:
            msg = "Codex tool results require a call ID and tool name"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CodexToolTurnCommand:
    """Application command for one client-managed Codex tool-aware turn."""

    prompt: str
    tools: tuple[CodexToolDefinition, ...] = field(default_factory=tuple)
    tool_results: tuple[CodexToolResult, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_prompt(self.prompt)
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "tool_results", tuple(self.tool_results))


@dataclass(frozen=True, slots=True)
class CodexToolCall:
    """One normalized Codex tool call with a stable backend-provided identifier."""

    call_id: str
    tool_name: str
    arguments_json: str

    def __post_init__(self) -> None:
        if not self.call_id or not self.tool_name or not self.arguments_json:
            msg = "Codex tool calls require a call ID, tool name, and JSON arguments"
            raise ValueError(msg)


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


@dataclass(frozen=True, slots=True)
class CodexToolTurnResult:
    """Terminal normalized result of one Codex tool-aware turn."""

    status: CodexTransportStatus
    output_text: str | None = None
    tool_calls: tuple[CodexToolCall, ...] = field(default_factory=tuple)
    observations: tuple[CodexTransportObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status is CodexTransportStatus.SUCCESS:
            if (self.output_text is None) == (not self.tool_calls):
                msg = "successful Codex tool turns require final text or tool calls, but not both"
                raise ValueError(msg)
        elif self.output_text is not None or self.tool_calls:
            msg = "non-success Codex tool turns must not include output"
            raise ValueError(msg)
        call_ids = tuple(call.call_id for call in self.tool_calls)
        if len(call_ids) != len(set(call_ids)):
            msg = "Codex tool turns must not contain duplicate call IDs"
            raise ValueError(msg)
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        object.__setattr__(self, "observations", tuple(self.observations))


def _validate_prompt(prompt: str) -> None:
    if not prompt.strip():
        msg = "Codex prompts must not be empty or whitespace-only"
        raise ValueError(msg)


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

    status: CodexTransportStatus
    evidence: CodexUsageEvidence | None = None
    observations: tuple[CodexTransportObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status is CodexTransportStatus.SUCCESS and self.evidence is None:
            msg = "successful Codex usage results must include evidence"
            raise ValueError(msg)
        if self.status is not CodexTransportStatus.SUCCESS and self.evidence is not None:
            msg = "non-success Codex usage results must not include evidence"
            raise ValueError(msg)

    @property
    def succeeded(self) -> bool:
        """Return whether usage evidence was retrieved successfully."""
        return self.status is CodexTransportStatus.SUCCESS


def _is_safe_observation_value(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _is_safe_usage_evidence_value(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)
