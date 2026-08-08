"""Redact secret-bearing diagnostics produced by Codex outbound adapters."""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from fabrica.features.codex_transport.application.dtos import SafeObservationValue

DiagnosticValue = SafeObservationValue | Mapping[str, "DiagnosticValue"] | tuple["DiagnosticValue", ...]

REDACTED_VALUE = "<redacted>"
_MAX_STRING_LENGTH = 160
_TRUNCATED_SUFFIX = "…<truncated>"

_SENSITIVE_KEY_PARTS = frozenset(
    {
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "idtoken",
        "password",
        "refreshtoken",
        "secret",
        "session",
        "token",
    }
)
_SENSITIVE_EXACT_KEYS = frozenset(
    {
        "accountid",
        "chatgptaccountid",
        "email",
        "setcookie",
        "userid",
        "username",
    }
)
_AUTH_PREFIXES = ("bearer ", "basic ")


def redact_mapping(mapping: Mapping[str, object]) -> Mapping[str, DiagnosticValue]:
    """Return immutable, shape-preserving diagnostic data with secrets redacted.

    Args:
        mapping: Diagnostic values from adapter-owned request, response, or
            exception data.

    Returns:
        A recursively redacted immutable mapping. The input mapping and nested
        containers are not mutated. Nested mappings and sequences are preserved
        for local diagnostics, so use ``redact_metadata`` when producing
        ``CodexTransportObservation.metadata``.

    """
    return MappingProxyType({key: redact_value(value, key=key) for key, value in mapping.items()})


def redact_metadata(mapping: Mapping[str, object]) -> Mapping[str, SafeObservationValue]:
    """Return immutable scalar metadata safe for Codex transport observations.

    ``CodexTransportObservation.metadata`` accepts only bounded scalar values.
    This API applies the redaction policy and summarizes nested containers so
    callers cannot accidentally leak raw request, response, or header shapes
    through application-layer observations.
    """
    return MappingProxyType({key: redact_metadata_value(value, key=key) for key, value in mapping.items()})


def redact_value(value: object, *, key: str | None = None) -> DiagnosticValue:
    """Return a shape-preserving diagnostic-safe representation of a value.

    Values under sensitive keys are replaced entirely. Nested mappings and
    sequences are copied recursively so callers can safely pass mutable source
    payloads without accidental exposure or mutation.
    """
    if key is not None and _is_sensitive_key(key):
        return REDACTED_VALUE
    return _redact_non_sensitive_value(value)


def redact_metadata_value(value: object, *, key: str | None = None) -> SafeObservationValue:
    """Return a scalar value safe for ``CodexTransportObservation.metadata``.

    Values under sensitive keys are redacted. Nested mappings and sequences are
    summarized instead of preserved because observation metadata is intentionally
    limited to scalar values.
    """
    if key is not None and _is_sensitive_key(key):
        return REDACTED_VALUE
    return _redact_non_sensitive_metadata_value(value)


def _redact_non_sensitive_value(value: object) -> DiagnosticValue:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                str(nested_key): redact_value(nested_value, key=str(nested_key))
                for nested_key, nested_value in value.items()
            }
        )

    if isinstance(value, str):
        return _redact_string(value)

    if isinstance(value, bytes):
        return f"<bytes length={len(value)}>"

    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(redact_value(item) for item in value)

    if isinstance(value, bool | int | float | type(None)):
        return value

    return f"<{type(value).__name__}>"


def _redact_non_sensitive_metadata_value(value: object) -> SafeObservationValue:
    if isinstance(value, Mapping):
        return f"<mapping length={len(value)}>"

    if isinstance(value, str):
        return _redact_string(value)

    if isinstance(value, bytes):
        return f"<bytes length={len(value)}>"

    if isinstance(value, Sequence) and not isinstance(value, str):
        return f"<sequence length={len(value)}>"

    if isinstance(value, bool | int | float | type(None)):
        return value

    return f"<{type(value).__name__}>"


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in _SENSITIVE_EXACT_KEYS or any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _normalize_key(key: str) -> str:
    return "".join(character for character in key.lower() if character.isalnum())


def _redact_string(value: str) -> str:
    if value.lower().startswith(_AUTH_PREFIXES):
        return REDACTED_VALUE
    if len(value) > _MAX_STRING_LENGTH:
        return f"{value[: _MAX_STRING_LENGTH - len(_TRUNCATED_SUFFIX)]}{_TRUNCATED_SUFFIX}"
    return value
