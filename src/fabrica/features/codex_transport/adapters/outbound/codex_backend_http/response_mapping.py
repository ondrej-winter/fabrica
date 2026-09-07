"""Map Codex backend HTTP outcomes to application result contracts."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from fabrica.features.codex_transport.application.dtos import (
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
    CodexUsageEvidence,
    CodexUsageResult,
    SafeUsageEvidenceValue,
)
from fabrica.features.codex_transport.application.mappers import (
    CodexCompletionUsageFacts,
    map_codex_completion_evidence,
)
from fabrica.shared_kernel.model_usage import ModelUsageEvidenceSource

AUTHENTICATION_STATUS_CODES = frozenset({401, 403})
RATE_LIMIT_STATUS_CODE = 429
MAX_ERROR_TYPE_LENGTH = 80

_SUCCESS_STATUS_CODE_LOWER_BOUND = 200
_SUCCESS_STATUS_CODE_UPPER_BOUND = 300


@dataclass(frozen=True, slots=True)
class CodexBackendResponse:
    """Adapter-owned HTTP response shape for deterministic completion mapping."""

    status_code: int
    headers: Mapping[str, str]
    json_body: object

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True, slots=True)
class CodexUsageResponse:
    """Adapter-owned HTTP response shape for deterministic usage mapping."""

    status_code: int
    headers: Mapping[str, str]
    json_body: object

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


def map_codex_backend_response(response: CodexBackendResponse) -> CodexTransportResult:
    """Map a completion response into the normalized application result contract."""
    if _is_edge_challenge_response(response.headers):
        return _completion_result(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            response=response,
            outcome=("Codex backend request was blocked by edge challenge mitigation", "edge_challenge"),
        )
    if response.status_code in AUTHENTICATION_STATUS_CODES:
        return _completion_result(
            status=CodexTransportStatus.AUTHENTICATION_FAILED,
            response=response,
            outcome=("Codex backend rejected credentials", "authentication"),
        )
    if _is_completion_quota_exceeded_response(response):
        return _completion_result(
            status=CodexTransportStatus.QUOTA_EXCEEDED,
            response=response,
            outcome=("Codex backend quota was exceeded", "quota"),
        )
    if response.status_code == RATE_LIMIT_STATUS_CODE or _has_rate_limit_signal(response.headers):
        return _completion_result(
            status=CodexTransportStatus.RATE_LIMITED,
            response=response,
            outcome=("Codex backend request was rate limited", "rate_limit"),
        )
    if _is_success_status_code(response.status_code):
        return _map_success_response(response)
    return _completion_result(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        response=response,
        outcome=("Codex backend returned an unsuccessful response", "backend_error"),
    )


def map_codex_backend_transport_error(error_type: str) -> CodexTransportResult:
    """Map a client/network exception into a secret-safe transport error result."""
    return CodexTransportResult(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        observations=(
            CodexTransportObservation(
                message="Codex backend request failed before a response was received",
                metadata={
                    "category": "client_error",
                    "error_type": _bounded(error_type, MAX_ERROR_TYPE_LENGTH),
                },
            ),
        ),
    )


def map_codex_usage_response(response: CodexUsageResponse) -> CodexUsageResult:
    """Map a usage response into safe status and allowlisted usage evidence."""
    if _is_edge_challenge_response(response.headers):
        return _usage_result(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            message="Codex usage request was blocked by edge challenge mitigation",
            response=response,
            category="edge_challenge",
        )
    if response.status_code in AUTHENTICATION_STATUS_CODES:
        return _usage_result(
            status=CodexTransportStatus.AUTHENTICATION_FAILED,
            message="Codex usage endpoint rejected credentials",
            response=response,
            category="authentication",
        )
    if _is_usage_quota_exceeded_response(response):
        return _usage_result(
            status=CodexTransportStatus.QUOTA_EXCEEDED,
            message="Codex usage endpoint reported quota exhaustion",
            response=response,
            category="quota",
        )
    if response.status_code == RATE_LIMIT_STATUS_CODE or _has_rate_limit_signal(response.headers):
        return _usage_result(
            status=CodexTransportStatus.RATE_LIMITED,
            message="Codex usage endpoint was rate limited",
            response=response,
            category="rate_limit",
        )
    if _is_success_status_code(response.status_code):
        return _map_usage_success_response(response)
    return _usage_result(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        message="Codex usage endpoint returned an unsuccessful response",
        response=response,
        category="backend_error",
    )


def map_codex_usage_transport_error(error_type: str) -> CodexUsageResult:
    """Map a usage client/network exception into a secret-safe result."""
    return CodexUsageResult(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        observations=(
            CodexTransportObservation(
                message="Codex usage request failed before a response was received",
                metadata={
                    "category": "client_error",
                    "error_type": _bounded(error_type, MAX_ERROR_TYPE_LENGTH),
                },
            ),
        ),
    )


def _map_success_response(response: CodexBackendResponse) -> CodexTransportResult:
    response_body = response.json_body
    if isinstance(response_body, str):
        return _map_event_stream_response(response, response_body)
    output_text = _extract_output_text(response_body)
    if output_text is None:
        return _completion_result(
            status=CodexTransportStatus.BACKEND_SHAPE_MISMATCH,
            response=response,
            outcome=("Codex backend response shape was unexpected", "shape_mismatch"),
        )
    return _completion_result(
        status=CodexTransportStatus.SUCCESS,
        response=response,
        outcome=("Codex backend returned expected response shape", "success"),
        output_text=output_text,
        usage_facts=_extract_completion_usage_facts(response_body),
    )


def _map_event_stream_response(response: CodexBackendResponse, response_text: str) -> CodexTransportResult:
    stream_outcome = _parse_completion_event_stream(response_text)
    if stream_outcome.status is CodexTransportStatus.SUCCESS:
        return _completion_result(
            status=stream_outcome.status,
            response=response,
            outcome=("Codex backend stream completed with final output", "success"),
            output_text=stream_outcome.output_text,
            usage_facts=stream_outcome.usage_facts,
        )
    return _completion_result(
        status=stream_outcome.status,
        response=response,
        outcome=(stream_outcome.message, stream_outcome.category),
    )


@dataclass(frozen=True, slots=True)
class _CompletionEventStreamOutcome:
    """Internal normalized outcome of parsing one fully delivered SSE response."""

    status: CodexTransportStatus
    message: str
    category: str
    output_text: str | None = None
    usage_facts: CodexCompletionUsageFacts | None = None


@dataclass(slots=True)
class _CompletionEventStreamState:
    """Internal state retained until a stream proves terminal completion."""

    terminal_payload: Mapping[object, object] | None = None
    output_text_deltas: list[str] = field(default_factory=list)
    completed_output_text: str | None = None


_KNOWN_NONTERMINAL_EVENT_TYPES = frozenset(
    {
        "response.created",
        "response.in_progress",
        "response.output_text.delta",
        "response.output_text.done",
        "response.output_item.added",
        "response.output_item.done",
        "response.content_part.added",
        "response.content_part.done",
    }
)
_TERMINAL_SUCCESS_EVENT_TYPE = "response.completed"
_TERMINAL_ERROR_EVENT_TYPES = frozenset({"response.failed", "error"})


def _parse_completion_event_stream(response_text: str) -> _CompletionEventStreamOutcome:
    try:
        frames = _parse_sse_frames(response_text)
    except ValueError:
        return _event_stream_shape_mismatch()

    state = _CompletionEventStreamState()
    for event_name, event_data in frames:
        frame_outcome = _classify_completion_event_frame(event_name=event_name, event_data=event_data)
        if frame_outcome is None:
            continue
        if isinstance(frame_outcome, _CompletionEventStreamOutcome):
            return frame_outcome
        state_outcome = _record_completion_event_payload(state, frame_outcome)
        if state_outcome is not None:
            return state_outcome

    if state.terminal_payload is None:
        return _CompletionEventStreamOutcome(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            message="Codex backend stream ended before terminal completion",
            category="incomplete_stream",
        )

    return _completion_event_stream_success(state, state.terminal_payload)


def _record_completion_event_payload(
    state: _CompletionEventStreamState,
    payload: Mapping[object, object],
) -> _CompletionEventStreamOutcome | None:
    payload_type = payload["type"]
    if payload_type == _TERMINAL_SUCCESS_EVENT_TYPE:
        if state.terminal_payload is not None:
            return _event_stream_shape_mismatch()
        state.terminal_payload = payload
        return None
    if state.terminal_payload is not None:
        return _event_stream_shape_mismatch()
    if payload_type == "response.output_text.delta":
        return _record_output_text_delta(state, payload)
    if payload_type == "response.output_text.done":
        return _record_output_text_done(state, payload)
    return None


def _record_output_text_delta(
    state: _CompletionEventStreamState,
    payload: Mapping[object, object],
) -> _CompletionEventStreamOutcome | None:
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return _event_stream_shape_mismatch()
    state.output_text_deltas.append(delta)
    return None


def _record_output_text_done(
    state: _CompletionEventStreamState,
    payload: Mapping[object, object],
) -> _CompletionEventStreamOutcome | None:
    text = payload.get("text")
    if not isinstance(text, str):
        return _event_stream_shape_mismatch()
    state.completed_output_text = text
    return None


def _completion_event_stream_success(
    state: _CompletionEventStreamState,
    terminal_payload: Mapping[object, object],
) -> _CompletionEventStreamOutcome:
    if not isinstance(terminal_payload.get("response"), Mapping):
        return _event_stream_shape_mismatch()

    output_text = _extract_output_text_from_mapping(terminal_payload)
    if output_text is None:
        output_text = state.completed_output_text or "".join(state.output_text_deltas)
    if output_text is None or not output_text.strip():
        return _event_stream_shape_mismatch()
    return _CompletionEventStreamOutcome(
        status=CodexTransportStatus.SUCCESS,
        message="Codex backend stream completed with final output",
        category="success",
        output_text=output_text,
        usage_facts=_extract_completion_usage_facts_from_mapping(
            terminal_payload,
            source=ModelUsageEvidenceSource.STREAM_EVENT,
        ),
    )


def _classify_completion_event_frame(
    *, event_name: str | None, event_data: str
) -> Mapping[object, object] | _CompletionEventStreamOutcome | None:
    if event_data in {"", "[DONE]"}:
        outcome: Mapping[object, object] | _CompletionEventStreamOutcome | None = (
            None if event_name is None else _event_stream_shape_mismatch()
        )
    else:
        outcome = _classify_nonempty_completion_event_frame(event_name=event_name, event_data=event_data)
    return outcome


def _classify_nonempty_completion_event_frame(
    *, event_name: str | None, event_data: str
) -> Mapping[object, object] | _CompletionEventStreamOutcome | None:
    try:
        payload = json.loads(event_data)
    except json.JSONDecodeError:
        return _event_stream_shape_mismatch()
    if not isinstance(payload, Mapping) or not isinstance(event_name, str):
        return _event_stream_shape_mismatch()
    payload_mapping = cast("Mapping[object, object]", payload)
    payload_type = payload_mapping.get("type")
    if not isinstance(payload_type, str) or payload_type != event_name:
        return _event_stream_shape_mismatch()
    return _classify_completion_payload(payload_type=payload_type, payload=payload_mapping)


def _classify_completion_payload(
    *, payload_type: str, payload: Mapping[object, object]
) -> Mapping[object, object] | _CompletionEventStreamOutcome | None:
    if payload_type in _KNOWN_NONTERMINAL_EVENT_TYPES:
        return payload
    if payload_type == _TERMINAL_SUCCESS_EVENT_TYPE:
        return payload
    if payload_type in _TERMINAL_ERROR_EVENT_TYPES:
        return _CompletionEventStreamOutcome(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            message="Codex backend stream reported a terminal error",
            category="backend_error",
        )
    return _event_stream_shape_mismatch()


def _parse_sse_frames(response_text: str) -> tuple[tuple[str | None, str], ...]:
    frames: list[tuple[str | None, str]] = []
    fields: list[str] = []
    for line in response_text.splitlines():
        if not line:
            _append_sse_frame(frames=frames, fields=fields)
            fields = []
            continue
        if line.startswith(":"):
            continue
        fields.append(line)
    _append_sse_frame(frames=frames, fields=fields)
    return tuple(frames)


def _append_sse_frame(*, frames: list[tuple[str | None, str]], fields: list[str]) -> None:
    if not fields:
        return
    event_name: str | None = None
    data_lines: list[str] = []
    for sse_field in fields:
        name, separator, value = sse_field.partition(":")
        if not separator or name not in {"event", "data"}:
            msg = "unsupported SSE field"
            raise ValueError(msg)
        value = value.removeprefix(" ")
        if name == "event":
            if event_name is not None:
                msg = "multiple SSE event fields"
                raise ValueError(msg)
            event_name = value
        else:
            data_lines.append(value)
    frames.append((event_name, "\n".join(data_lines)))


def _event_stream_shape_mismatch() -> _CompletionEventStreamOutcome:
    return _CompletionEventStreamOutcome(
        status=CodexTransportStatus.BACKEND_SHAPE_MISMATCH,
        message="Codex backend stream shape was unexpected",
        category="shape_mismatch",
    )


def _completion_result(
    *,
    status: CodexTransportStatus,
    response: CodexBackendResponse,
    outcome: tuple[str, str],
    output_text: str | None = None,
    usage_facts: CodexCompletionUsageFacts | None = None,
) -> CodexTransportResult:
    message, category = outcome
    generic_evidence = map_codex_completion_evidence(status=status, usage_facts=usage_facts)
    return CodexTransportResult(
        status=status,
        output_text=output_text,
        observations=(_response_observation(message=message, category=category, response=response),),
        usage_evidence=generic_evidence.usage_evidence,
        cost_evidence=generic_evidence.cost_evidence,
    )


def _map_usage_success_response(response: CodexUsageResponse) -> CodexUsageResult:
    evidence_values = _extract_usage_evidence(response.json_body, response.headers)
    if not evidence_values:
        return _usage_result(
            status=CodexTransportStatus.BACKEND_SHAPE_MISMATCH,
            message="Codex usage response shape was unexpected",
            response=response,
            category="shape_mismatch",
        )
    return _usage_result(
        status=CodexTransportStatus.SUCCESS,
        message="Codex usage evidence was retrieved",
        response=response,
        category="success",
        evidence=CodexUsageEvidence(evidence_values),
    )


def _usage_result(
    *,
    status: CodexTransportStatus,
    message: str,
    response: CodexUsageResponse,
    category: str,
    evidence: CodexUsageEvidence | None = None,
) -> CodexUsageResult:
    return CodexUsageResult(
        status=status,
        evidence=evidence,
        observations=(_response_observation(message=message, category=category, response=response),),
    )


def _response_observation(
    *,
    message: str,
    category: str,
    response: CodexBackendResponse | CodexUsageResponse,
) -> CodexTransportObservation:
    return CodexTransportObservation(
        message=message,
        metadata={
            "http_status": response.status_code,
            "category": category,
            "header_count": len(response.headers),
            "response_shape": _response_shape(response.json_body),
            "error_type": _extract_error_type(response.json_body),
        },
    )


def _is_completion_quota_exceeded_response(response: CodexBackendResponse) -> bool:
    return response.status_code == RATE_LIMIT_STATUS_CODE and _body_contains_token(response.json_body, "quota")


def _is_usage_quota_exceeded_response(response: CodexUsageResponse) -> bool:
    return response.status_code == RATE_LIMIT_STATUS_CODE and _body_contains_token(response.json_body, "quota")


def _is_success_status_code(status_code: int) -> bool:
    return _SUCCESS_STATUS_CODE_LOWER_BOUND <= status_code < _SUCCESS_STATUS_CODE_UPPER_BOUND


def _has_rate_limit_signal(headers: Mapping[str, str]) -> bool:
    return any(_is_rate_limit_header(name=name, value=value) for name, value in headers.items())


def _is_edge_challenge_response(headers: Mapping[str, str]) -> bool:
    normalized_headers = {name.lower(): value.strip().lower() for name, value in headers.items()}
    return normalized_headers.get("cf-mitigated") == "challenge"


def _body_contains_token(value: object, token: str) -> bool:
    if isinstance(value, Mapping):
        return any(_body_contains_token(nested_value, token) for nested_value in value.values())
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return any(_body_contains_token(nested_value, token) for nested_value in value)
    if isinstance(value, str):
        return token in value.lower()
    return False


def _response_shape(json_body: object) -> str:
    shape = type(json_body).__name__
    if isinstance(json_body, str) and "data:" in json_body:
        shape = "event_stream"
    elif isinstance(json_body, Mapping):
        keys = {str(key) for key in json_body}
        if "output_text" in keys:
            shape = "responses_output_text"
        elif "output" in keys:
            shape = "responses_output"
        elif "error" in keys:
            shape = "error"
        else:
            shape = "mapping"
    elif isinstance(json_body, Sequence) and not isinstance(json_body, str | bytes):
        shape = "sequence"
    return shape


def _extract_error_type(json_body: object) -> str | None:
    error_value = _extract_error_field(json_body, "type") or _extract_error_field(json_body, "code")
    return _bounded(error_value, MAX_ERROR_TYPE_LENGTH) if error_value is not None else None


def _bounded(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 1]}…"


def _is_rate_limit_header(*, name: str, value: str) -> bool:
    normalized_name = name.lower()
    normalized_value = value.strip().lower()
    if "rate" not in normalized_name and "ratelimit" not in normalized_name:
        return False
    return normalized_value in {"0", "true", "exceeded", "limited"} or "limit" in normalized_value


def _extract_error_field(json_body: object, field_name: str) -> str | None:
    if not isinstance(json_body, Mapping):
        return None
    error = json_body.get("error")
    if isinstance(error, Mapping):
        value = error.get(field_name)
        return value if isinstance(value, str) else None
    value = json_body.get(field_name)
    return value if isinstance(value, str) else None


def _extract_output_text(json_body: object) -> str | None:
    if not isinstance(json_body, Mapping):
        return None
    return _extract_output_text_from_mapping(cast("Mapping[object, object]", json_body))


def _extract_completion_usage_facts(json_body: object) -> CodexCompletionUsageFacts | None:
    if not isinstance(json_body, Mapping):  # pragma: no cover - successful output extraction above requires a mapping.
        return None
    return _extract_completion_usage_facts_from_mapping(
        cast("Mapping[object, object]", json_body),
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
    )


def _extract_completion_usage_facts_from_mapping(
    json_body: Mapping[object, object],
    *,
    source: ModelUsageEvidenceSource,
) -> CodexCompletionUsageFacts | None:
    usage = _usage_mapping_from_response_shape(json_body)
    candidate = usage if usage is not None else json_body
    details = _first_mapping(candidate.get("input_token_details"), candidate.get("prompt_tokens_details"))
    output_details = _first_mapping(candidate.get("output_token_details"), candidate.get("completion_tokens_details"))
    facts = CodexCompletionUsageFacts(
        source=source,
        input_tokens=_optional_non_negative_int(candidate.get("input_tokens"), candidate.get("prompt_tokens")),
        output_tokens=_optional_non_negative_int(candidate.get("output_tokens"), candidate.get("completion_tokens")),
        total_tokens=_optional_non_negative_int(candidate.get("total_tokens")),
        cached_input_tokens=_optional_non_negative_int(
            candidate.get("cached_input_tokens"),
            details.get("cached_tokens") if details is not None else None,
        ),
        reasoning_tokens=_optional_non_negative_int(
            candidate.get("reasoning_tokens"),
            output_details.get("reasoning_tokens") if output_details is not None else None,
        ),
        model=_safe_model(candidate.get("model"), json_body.get("model")),
    )
    return facts if facts.has_token_counts else None


def _extract_output_text_from_mapping(json_body: Mapping[object, object]) -> str | None:
    direct_output = json_body.get("output_text")
    if isinstance(direct_output, str) and direct_output:
        return direct_output
    content_output = _extract_output_text_from_content(json_body.get("content"))
    if content_output is not None:
        return content_output
    nested_output = _extract_output_text_from_nested_mapping(json_body)
    if nested_output is not None:
        return nested_output
    output = json_body.get("output")
    if not isinstance(output, Sequence) or isinstance(output, str | bytes):
        return None
    return _extract_output_text_from_output_items(output)


def _extract_output_text_from_content(content: object) -> str | None:
    extracted_parts: list[str] = []
    _append_content_texts(extracted_parts=extracted_parts, content=content)
    return "".join(extracted_parts) if extracted_parts else None


def _extract_output_text_from_nested_mapping(json_body: Mapping[object, object]) -> str | None:
    for nested_key in ("response", "item", "part"):
        nested_output = json_body.get(nested_key)
        if isinstance(nested_output, Mapping):
            extracted_output = _extract_output_text_from_mapping(cast("Mapping[object, object]", nested_output))
            if extracted_output is not None:
                return extracted_output
    return None


def _extract_output_text_from_output_items(output: Sequence[object]) -> str | None:
    extracted_parts: list[str] = []
    for output_item in output:
        if isinstance(output_item, Mapping):
            _append_content_texts(extracted_parts=extracted_parts, content=output_item.get("content"))
    return "".join(extracted_parts) if extracted_parts else None


def _append_content_texts(*, extracted_parts: list[str], content: object) -> None:
    if not isinstance(content, Sequence) or isinstance(content, str | bytes):
        return
    for content_item in content:
        if not isinstance(content_item, Mapping):
            continue
        text = content_item.get("text")
        if isinstance(text, str):
            extracted_parts.append(text)


def _usage_mapping_from_response_shape(json_body: Mapping[object, object]) -> Mapping[object, object] | None:
    usage = _first_mapping(json_body.get("usage"))
    if usage is not None:
        return usage
    for nested_key in ("response", "item", "part"):
        nested_value = json_body.get(nested_key)
        if isinstance(nested_value, Mapping):
            nested_usage = _usage_mapping_from_response_shape(cast("Mapping[object, object]", nested_value))
            if nested_usage is not None:
                return nested_usage
    return None


def _first_mapping(*values: object) -> Mapping[object, object] | None:
    for value in values:
        if isinstance(value, Mapping):
            return cast("Mapping[object, object]", value)
    return None


def _optional_non_negative_int(*values: object) -> int | None:
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _safe_model(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return _bounded(value, 120)
    return None


def _extract_usage_evidence(json_body: object, headers: Mapping[str, str]) -> dict[str, SafeUsageEvidenceValue]:
    evidence = _extract_usage_mapping_evidence(json_body)
    rate_limit_header_names = tuple(
        sorted(
            name.lower()
            for name, value in headers.items()
            if name.lower().startswith("x-codex-") and _is_safe_scalar(value)
        )
    )
    if rate_limit_header_names:
        evidence["rate_limit_header_count"] = len(rate_limit_header_names)
        evidence["rate_limit_header_names"] = ",".join(rate_limit_header_names)
    return evidence


def _extract_usage_mapping_evidence(json_body: object) -> dict[str, SafeUsageEvidenceValue]:
    if not isinstance(json_body, Mapping):
        return {}

    evidence: dict[str, SafeUsageEvidenceValue] = {}
    source = cast("Mapping[object, object]", json_body)
    for key, value in source.items():
        key_text = str(key)
        if _is_safe_usage_key(key_text) and _is_safe_scalar(value):
            evidence[key_text] = cast("SafeUsageEvidenceValue", value)
    return evidence


def _is_safe_usage_key(key: str) -> bool:
    normalized_key = key.lower()
    if any(sensitive in normalized_key for sensitive in ("token", "secret", "cookie", "authorization", "account")):
        return False
    return any(term in normalized_key for term in ("limit", "quota", "usage", "remaining", "reset", "plan", "tier"))


def _is_safe_scalar(value: object) -> bool:
    return isinstance(value, str | int | float | bool) or value is None
