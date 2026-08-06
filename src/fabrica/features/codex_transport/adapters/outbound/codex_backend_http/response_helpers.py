"""Shared helpers for Codex HTTP response classification and observations."""

from collections.abc import Mapping, Sequence

AUTHENTICATION_STATUS_CODES = frozenset({401, 403})
RATE_LIMIT_STATUS_CODE = 429
MAX_ERROR_TYPE_LENGTH = 80

_SUCCESS_STATUS_CODE_LOWER_BOUND = 200
_SUCCESS_STATUS_CODE_UPPER_BOUND = 300


def is_success_status_code(status_code: int) -> bool:
    """Return whether an HTTP status code is in the 2xx range."""
    return _SUCCESS_STATUS_CODE_LOWER_BOUND <= status_code < _SUCCESS_STATUS_CODE_UPPER_BOUND


def has_rate_limit_signal(headers: Mapping[str, str]) -> bool:
    """Return whether response headers contain a known rate-limit signal."""
    return any(_is_rate_limit_header(name=name, value=value) for name, value in headers.items())


def is_edge_challenge_response(headers: Mapping[str, str]) -> bool:
    """Return whether edge middleware challenged rather than served the request."""
    normalized_headers = {name.lower(): value.strip().lower() for name, value in headers.items()}
    return normalized_headers.get("cf-mitigated") == "challenge"


def body_contains_token(value: object, token: str) -> bool:
    """Return whether a nested response body contains a case-insensitive token."""
    if isinstance(value, Mapping):
        return any(body_contains_token(nested_value, token) for nested_value in value.values())
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return any(body_contains_token(nested_value, token) for nested_value in value)
    if isinstance(value, str):
        return token in value.lower()
    return False


def response_shape(json_body: object) -> str:
    """Return a bounded label for the observed response body shape."""
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


def extract_error_type(json_body: object) -> str | None:
    """Extract a bounded upstream error type or code when safely available."""
    error_value = _extract_error_field(json_body, "type") or _extract_error_field(json_body, "code")
    return bounded(error_value, MAX_ERROR_TYPE_LENGTH) if error_value is not None else None


def bounded(value: str, max_length: int) -> str:
    """Return text truncated to a maximum display length."""
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
