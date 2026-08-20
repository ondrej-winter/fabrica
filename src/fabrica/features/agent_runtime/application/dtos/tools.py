"""Application DTOs for bounded tool-loop runtime orchestration."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

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
SAFE_TOOL_IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")
type ToolArgumentSchemaValue = (
    str | int | float | bool | tuple[ToolArgumentSchemaValue, ...] | Mapping[str, ToolArgumentSchemaValue] | None
)


class ToolCallResultStatus(StrEnum):
    """Normalized outcomes for one requested tool invocation."""

    SUCCESS = "success"
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


@dataclass(frozen=True, slots=True)
class ToolLoopLimits:
    """Bounds applied to one application-owned tool loop."""

    max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS
    max_tool_calls_per_turn: int = DEFAULT_MAX_TOOL_CALLS_PER_TURN
    max_tool_result_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS

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
class ToolDefinition:
    """Backend-neutral description of an explicitly available tool."""

    name: str
    description: str
    argument_schema: Mapping[str, ToolArgumentSchemaValue] = field(default_factory=dict)

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
    arguments: Mapping[str, SafeRuntimeMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_tool_identifier(self.call_id, field_name="tool call id", max_chars=MAX_TOOL_CALL_ID_CHARS)
        _validate_tool_identifier(self.tool_name, field_name="tool name", max_chars=MAX_TOOL_NAME_CHARS)
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    """Application-safe result for one tool invocation."""

    call_id: str
    tool_name: str
    status: ToolCallResultStatus
    result_text: str | None = None
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
        object.__setattr__(self, "observations", tuple(self.observations))

    def bounded(self, limits: ToolLoopLimits) -> "ToolCallResult":
        """Return a copy whose result text fits the configured loop bound."""
        if self.result_text is None or len(self.result_text) <= limits.max_tool_result_chars:
            return self
        return ToolCallResult(
            call_id=self.call_id,
            tool_name=self.tool_name,
            status=self.status,
            result_text=self.result_text[: limits.max_tool_result_chars],
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
