"""Map Codex backend HTTP outcomes to application result contracts.

The mapper is the trust boundary for untyped third-party response data. It
classifies status codes, edge challenges, quota/rate-limit signals, success
response shapes, and transport exceptions into bounded, secret-safe application
DTOs. Success extraction accepts both JSON responses and the stream-backed SSE
shape currently used by the Codex responses endpoint.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from fabrica.features.codex_transport.application.dtos import (
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
    CodexUsageEvidence,
    CodexUsageResult,
    CodexUsageStatus,
    SafeUsageEvidenceValue,
)

_AUTHENTICATION_STATUS_CODES = frozenset({401, 403})
_RATE_LIMIT_STATUS_CODE = 429
_SUCCESS_STATUS_CODE_LOWER_BOUND = 200
_SUCCESS_STATUS_CODE_UPPER_BOUND = 300
_MAX_ERROR_TYPE_LENGTH = 80


@dataclass(frozen=True, slots=True)
class CodexBackendResponse:
    """Adapter-owned HTTP response shape for deterministic response mapping."""

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
        return _result(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            message="Codex backend request was blocked by edge challenge mitigation",
            response=response,
            category="edge_challenge",
        )

    if response.status_code in _AUTHENTICATION_STATUS_CODES:
        return _result(
            status=CodexTransportStatus.AUTHENTICATION_FAILED,
            message="Codex backend rejected credentials",
            response=response,
            category="authentication",
        )

    if _is_quota_exceeded_response(response):
        return _result(
            status=CodexTransportStatus.QUOTA_EXCEEDED,
            message="Codex backend quota was exceeded",
            response=response,
            category="quota",
        )

    if response.status_code == _RATE_LIMIT_STATUS_CODE or _has_rate_limit_signal(response.headers):
        return _result(
            status=CodexTransportStatus.RATE_LIMITED,
            message="Codex backend request was rate limited",
            response=response,
            category="rate_limit",
        )

    if _is_success_status_code(response.status_code):
        return _map_success_response(response)

    return _result(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        message="Codex backend returned an unsuccessful response",
        response=response,
        category="backend_error",
    )


def _map_success_response(response: CodexBackendResponse) -> CodexTransportResult:
    output_text = _extract_output_text(response.json_body)
    if output_text is None:
        return _result(
            status=CodexTransportStatus.BACKEND_SHAPE_MISMATCH,
            message="Codex backend response shape was unexpected",
            response=response,
            category="shape_mismatch",
        )
    return _result(
        status=CodexTransportStatus.SUCCESS,
        message="Codex backend returned expected response shape",
        response=response,
        category="success",
        output_text=output_text,
    )


def map_codex_backend_transport_error(err: BaseException) -> CodexTransportResult:
    """Map a client/network exception into a secret-safe transport error result."""
    return CodexTransportResult(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        observations=(
            CodexTransportObservation(
                message="Codex backend request failed before a response was received",
                metadata={
                    "category": "client_error",
                    "error_type": _bounded(type(err).__name__, _MAX_ERROR_TYPE_LENGTH),
                },
            ),
        ),
    )


def map_codex_usage_response(response: CodexUsageResponse) -> CodexUsageResult:
    """Map a usage response into safe status and allowlisted usage evidence."""
    if _is_edge_challenge_response(response.headers):
        return _usage_result(
            status=CodexUsageStatus.TRANSPORT_ERROR,
            message="Codex usage request was blocked by edge challenge mitigation",
            response=response,
            category="edge_challenge",
        )

    if response.status_code in _AUTHENTICATION_STATUS_CODES:
        return _usage_result(
            status=CodexUsageStatus.AUTHENTICATION_FAILED,
            message="Codex usage endpoint rejected credentials",
            response=response,
            category="authentication",
        )

    if _is_usage_quota_exceeded_response(response):
        return _usage_result(
            status=CodexUsageStatus.QUOTA_EXCEEDED,
            message="Codex usage endpoint reported quota exhaustion",
            response=response,
            category="quota",
        )

    if response.status_code == _RATE_LIMIT_STATUS_CODE or _has_rate_limit_signal(response.headers):
        return _usage_result(
            status=CodexUsageStatus.RATE_LIMITED,
            message="Codex usage endpoint was rate limited",
            response=response,
            category="rate_limit",
        )

    if _is_success_status_code(response.status_code):
        return _map_usage_success_response(response)

    return _usage_result(
        status=CodexUsageStatus.TRANSPORT_ERROR,
        message="Codex usage endpoint returned an unsuccessful response",
        response=response,
        category="backend_error",
    )


def map_codex_usage_transport_error(err: BaseException) -> CodexUsageResult:
    """Map a usage client/network exception into a secret-safe result."""
    return CodexUsageResult(
        status=CodexUsageStatus.TRANSPORT_ERROR,
        observations=(
            CodexTransportObservation(
                message="Codex usage request failed before a response was received",
                metadata={
                    "category": "client_error",
                    "error_type": _bounded(type(err).__name__, _MAX_ERROR_TYPE_LENGTH),
                },
            ),
        ),
    )


def _result(
    *,
    status: CodexTransportStatus,
    message: str,
    response: CodexBackendResponse,
    category: str,
    output_text: str | None = None,
) -> CodexTransportResult:
    return CodexTransportResult(
        status=status,
        output_text=output_text,
        observations=(
            CodexTransportObservation(
                message=message,
                metadata={
                    "http_status": response.status_code,
                    "category": category,
                    "header_count": len(response.headers),
                    "response_shape": _response_shape(response.json_body),
                    "error_type": _extract_error_type(response.json_body),
                },
            ),
        ),
    )


def _map_usage_success_response(response: CodexUsageResponse) -> CodexUsageResult:
    evidence_values = _extract_usage_evidence(response.json_body, response.headers)
    if not evidence_values:
        return _usage_result(
            status=CodexUsageStatus.BACKEND_SHAPE_MISMATCH,
            message="Codex usage response shape was unexpected",
            response=response,
            category="shape_mismatch",
        )
    return _usage_result(
        status=CodexUsageStatus.SUCCESS,
        message="Codex usage evidence was retrieved",
        response=response,
        category="success",
        evidence=CodexUsageEvidence(evidence_values),
    )


def _usage_result(
    *,
    status: CodexUsageStatus,
    message: str,
    response: CodexUsageResponse,
    category: str,
    evidence: CodexUsageEvidence | None = None,
) -> CodexUsageResult:
    return CodexUsageResult(
        status=status,
        evidence=evidence,
        observations=(
            CodexTransportObservation(
                message=message,
                metadata={
                    "http_status": response.status_code,
                    "category": category,
                    "header_count": len(response.headers),
                    "response_shape": _response_shape(response.json_body),
                    "error_type": _extract_error_type(response.json_body),
                },
            ),
        ),
    )


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


def _is_usage_quota_exceeded_response(response: CodexUsageResponse) -> bool:
    return response.status_code == _RATE_LIMIT_STATUS_CODE and _body_contains_token(response.json_body, "quota")


def _is_success_status_code(status_code: int) -> bool:
    return _SUCCESS_STATUS_CODE_LOWER_BOUND <= status_code < _SUCCESS_STATUS_CODE_UPPER_BOUND


def _extract_output_text(json_body: object) -> str | None:
    if isinstance(json_body, str):
        return _extract_output_text_from_event_stream(json_body)
    if not isinstance(json_body, Mapping):
        return None

    return _extract_output_text_from_mapping(cast("Mapping[object, object]", json_body))


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


def _extract_output_text_from_event_stream(response_text: str) -> str | None:
    extracted_parts: list[str] = []
    done_text: str | None = None
    for line in response_text.splitlines():
        if not line.startswith("data:"):
            continue
        event_data = line.removeprefix("data:").strip()
        if event_data in {"", "[DONE]"}:
            continue
        try:
            payload = json.loads(event_data)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            event_type = payload.get("type")
            text = payload.get("text")
            delta = payload.get("delta")
            if event_type == "response.output_text.done" and isinstance(text, str):
                done_text = text
                continue
            if event_type == "response.output_text.delta" and isinstance(delta, str):
                extracted_parts.append(delta)
                continue
            output_text = _extract_output_text(payload)
            if output_text is not None and not extracted_parts:
                extracted_parts.append(output_text)
    if not extracted_parts:
        return done_text
    return "".join(extracted_parts)


def _is_quota_exceeded_response(response: CodexBackendResponse) -> bool:
    return response.status_code == _RATE_LIMIT_STATUS_CODE and _body_contains_token(response.json_body, "quota")


def _has_rate_limit_signal(headers: Mapping[str, str]) -> bool:
    return any(_is_rate_limit_header(name=name, value=value) for name, value in headers.items())


def _is_rate_limit_header(*, name: str, value: str) -> bool:
    normalized_name = name.lower()
    normalized_value = value.strip().lower()
    if "rate" not in normalized_name and "ratelimit" not in normalized_name:
        return False
    return normalized_value in {"0", "true", "exceeded", "limited"} or "limit" in normalized_value


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
    return _bounded(error_value, _MAX_ERROR_TYPE_LENGTH) if error_value is not None else None


def _extract_error_field(json_body: object, field_name: str) -> str | None:
    if not isinstance(json_body, Mapping):
        return None
    error = json_body.get("error")
    if isinstance(error, Mapping):
        value = error.get(field_name)
        return value if isinstance(value, str) else None
    value = json_body.get(field_name)
    return value if isinstance(value, str) else None


def _bounded(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 1]}…"
