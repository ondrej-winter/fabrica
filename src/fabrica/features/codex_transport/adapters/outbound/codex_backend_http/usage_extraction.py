"""Extract safe usage endpoint evidence from Codex response payloads."""

from collections.abc import Mapping
from typing import cast

from fabrica.features.codex_transport.application.dtos import SafeUsageEvidenceValue


def extract_usage_evidence(json_body: object, headers: Mapping[str, str]) -> dict[str, SafeUsageEvidenceValue]:
    """Extract allowlisted usage evidence from a usage endpoint response."""
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
