"""Provider-agnostic usage and cost evidence DTOs for model calls."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

DEFAULT_MAX_MODEL_USAGE_OBSERVATION_MESSAGE_CHARS = 240
MODEL_USAGE_CURRENCY_CODE_CHARS = 3

type SafeModelUsageObservationValue = str | int | float | bool | None


class ModelUsageCollectionStatus(StrEnum):
    """Provider-neutral usage evidence collection states."""

    COLLECTED = "collected"
    PARTIALLY_COLLECTED = "partially_collected"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class ModelUsageEvidenceSource(StrEnum):
    """Provider-neutral sources that can contribute usage or pricing evidence."""

    RESPONSE_PAYLOAD = "response_payload"
    STREAM_EVENT = "stream_event"
    RESPONSE_HEADER = "response_header"
    USAGE_ENDPOINT = "usage_endpoint"
    MANUAL_OBSERVATION = "manual_observation"
    SOURCE_CODE_OBSERVATION = "source_code_observation"


class ModelUsageEvidenceConfidence(StrEnum):
    """Provider-neutral confidence labels for usage and pricing evidence."""

    OBSERVED = "observed"
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    MANUAL = "manual"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class ModelPricingStatus(StrEnum):
    """Provider-neutral pricing evidence states."""

    UNKNOWN = "unknown"
    NOT_AVAILABLE = "not_available"
    SUBSCRIPTION_INCLUDED = "subscription_included"
    PUBLIC_PRICE_ESTIMATE = "public_price_estimate"
    MANUAL_ESTIMATE = "manual_estimate"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ModelTokenUsageEvidence:
    """Optional token counts reported by a model provider."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None

    def __post_init__(self) -> None:
        _validate_optional_non_negative_int(self.input_tokens, field_name="input_tokens")
        _validate_optional_non_negative_int(self.output_tokens, field_name="output_tokens")
        _validate_optional_non_negative_int(self.total_tokens, field_name="total_tokens")
        _validate_optional_non_negative_int(self.cached_input_tokens, field_name="cached_input_tokens")
        _validate_optional_non_negative_int(self.reasoning_tokens, field_name="reasoning_tokens")


@dataclass(frozen=True, slots=True)
class ModelQuotaEvidence:
    """Optional quota or rate-limit evidence reported by a model provider."""

    limit: int | None = None
    remaining: int | None = None
    reset_at: str | None = None
    window_seconds: int | None = None

    def __post_init__(self) -> None:
        _validate_optional_non_negative_int(self.limit, field_name="limit")
        _validate_optional_non_negative_int(self.remaining, field_name="remaining")
        _validate_optional_non_negative_int(self.window_seconds, field_name="window_seconds")
        if self.reset_at is not None and not self.reset_at:
            msg = "reset_at must not be empty when provided"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ModelUsageObservation:
    """Redacted, bounded scalar observation attached to usage or cost evidence."""

    message: str
    metadata: Mapping[str, SafeModelUsageObservationValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.message:
            msg = "message must not be empty"
            raise ValueError(msg)
        if len(self.message) > DEFAULT_MAX_MODEL_USAGE_OBSERVATION_MESSAGE_CHARS:
            msg = "message exceeds the safe usage observation bound"
            raise ValueError(msg)
        copied_metadata: dict[str, SafeModelUsageObservationValue] = {}
        for key, value in self.metadata.items():
            if not isinstance(key, str):
                msg = "usage observation metadata keys must be strings"
                raise TypeError(msg)
            if not _is_safe_observation_value(value):
                msg = f"usage observation metadata value for {key!r} must be a bounded scalar"
                raise TypeError(msg)
            copied_metadata[key] = value
        object.__setattr__(self, "metadata", MappingProxyType(copied_metadata))


@dataclass(frozen=True, slots=True)
class ModelUsageEvidence:
    """Provider-agnostic usage evidence for one model call or usage probe."""

    provider: str
    status: ModelUsageCollectionStatus
    source: ModelUsageEvidenceSource
    confidence: ModelUsageEvidenceConfidence
    model: str | None = None
    tokens: ModelTokenUsageEvidence = field(default_factory=ModelTokenUsageEvidence)
    quota: ModelQuotaEvidence | None = None
    observations: tuple[ModelUsageObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_text(self.provider, field_name="provider")
        if self.model is not None:
            _validate_non_empty_text(self.model, field_name="model")
        object.__setattr__(self, "observations", tuple(self.observations))


@dataclass(frozen=True, slots=True)
class ModelCostEvidence:
    """Provider-agnostic pricing or cost evidence for one model call or usage probe."""

    pricing_status: ModelPricingStatus
    source: ModelUsageEvidenceSource
    confidence: ModelUsageEvidenceConfidence
    estimated_amount: Decimal | None = None
    currency: str | None = None
    observations: tuple[ModelUsageObservation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if (self.estimated_amount is None) != (self.currency is None):
            msg = "estimated_amount and currency must be provided together"
            raise ValueError(msg)
        if self.estimated_amount is not None:
            _validate_estimate(self.pricing_status, self.estimated_amount, self.currency)
        object.__setattr__(self, "observations", tuple(self.observations))


def _validate_optional_non_negative_int(value: int | None, *, field_name: str) -> None:
    if value is not None and value < 0:
        msg = f"{field_name} must not be negative"
        raise ValueError(msg)


def _validate_non_empty_text(value: str, *, field_name: str) -> None:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)


def _validate_estimate(pricing_status: ModelPricingStatus, estimated_amount: Decimal, currency: str | None) -> None:
    if pricing_status not in {ModelPricingStatus.PUBLIC_PRICE_ESTIMATE, ModelPricingStatus.MANUAL_ESTIMATE}:
        msg = "monetary estimates require an estimate pricing status"
        raise ValueError(msg)
    if estimated_amount < Decimal(0):
        msg = "estimated_amount must not be negative"
        raise ValueError(msg)
    if currency is None or currency != currency.upper() or len(currency) != MODEL_USAGE_CURRENCY_CODE_CHARS:
        msg = "currency must be a three-letter uppercase code"
        raise ValueError(msg)


def _is_safe_observation_value(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)
