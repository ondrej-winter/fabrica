"""Shared Codex-only generic-evidence metadata policy and mapper DTOs."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from fabrica.shared_kernel.model_usage import (
    DEFAULT_MAX_MODEL_USAGE_OBSERVATION_METADATA_STRING_VALUE_CHARS,
    ModelCostEvidence,
    ModelUsageEvidence,
    SafeModelUsageObservationValue,
)

CODEX_PROVIDER = "codex"
CODEX_COMPLETION_USAGE_OBSERVATION_KEYS = frozenset({"provider", "codex_status", "collection_status"})
CODEX_COMPLETION_PRICING_OBSERVATION_KEYS = frozenset({"provider", "codex_status"})
CODEX_USAGE_ENDPOINT_USAGE_OBSERVATION_KEYS = frozenset(
    {
        "provider",
        "codex_usage_status",
        "collection_status",
        "quota_field_count",
        "plan",
        "plan_type",
        "tier",
        "usage_percent",
        "quota_percent",
        "rate_limit_header_count",
        "rate_limit_header_names",
    },
)
CODEX_USAGE_ENDPOINT_PRICING_OBSERVATION_KEYS = frozenset({"provider", "codex_usage_status"})


@dataclass(frozen=True, slots=True)
class CodexGenericEvidence:
    """Generic usage and cost evidence derived from Codex-safe facts."""

    usage_evidence: tuple[ModelUsageEvidence, ...] = field(default_factory=tuple)
    cost_evidence: tuple[ModelCostEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "usage_evidence", tuple(self.usage_evidence))
        object.__setattr__(self, "cost_evidence", tuple(self.cost_evidence))


def safe_codex_observation_metadata(
    values: Mapping[str, object],
    *,
    allowed_keys: frozenset[str],
) -> dict[str, SafeModelUsageObservationValue]:
    """Return allowlisted, bounded scalar metadata safe for generic evidence."""
    return {
        key: cast("SafeModelUsageObservationValue", value)
        for key, value in values.items()
        if key in allowed_keys and _is_safe_observation_value(value) and _is_bounded_string(value)
    }


def _is_safe_observation_value(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _is_bounded_string(value: object) -> bool:
    return not isinstance(value, str) or len(value) <= DEFAULT_MAX_MODEL_USAGE_OBSERVATION_METADATA_STRING_VALUE_CHARS


__all__ = [
    "CODEX_COMPLETION_PRICING_OBSERVATION_KEYS",
    "CODEX_COMPLETION_USAGE_OBSERVATION_KEYS",
    "CODEX_PROVIDER",
    "CODEX_USAGE_ENDPOINT_PRICING_OBSERVATION_KEYS",
    "CODEX_USAGE_ENDPOINT_USAGE_OBSERVATION_KEYS",
    "CodexGenericEvidence",
    "safe_codex_observation_metadata",
]
