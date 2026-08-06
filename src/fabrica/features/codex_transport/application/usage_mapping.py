"""Map safe Codex usage facts into provider-agnostic evidence DTOs."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from fabrica.features.codex_transport.application.dtos.transport import CodexTransportStatus
from fabrica.features.codex_transport.application.dtos.usage import CodexUsageResult
from fabrica.shared_kernel.model_usage import (
    ModelCostEvidence,
    ModelPricingStatus,
    ModelQuotaEvidence,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    ModelUsageObservation,
    SafeModelUsageObservationValue,
)

CODEX_PROVIDER = "codex"
_COMPLETE_QUOTA_FIELD_COUNT = 4
_SAFE_USAGE_OBSERVATION_KEYS = frozenset(
    {
        "plan",
        "plan_type",
        "tier",
        "usage_percent",
        "quota_percent",
        "rate_limit_header_count",
        "rate_limit_header_names",
    },
)


@dataclass(frozen=True, slots=True)
class CodexCompletionUsageFacts:
    """Safe, bounded token facts extracted from a Codex completion response."""

    source: ModelUsageEvidenceSource
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        _validate_optional_non_negative_int(self.input_tokens, field_name="input_tokens")
        _validate_optional_non_negative_int(self.output_tokens, field_name="output_tokens")
        _validate_optional_non_negative_int(self.total_tokens, field_name="total_tokens")
        _validate_optional_non_negative_int(self.cached_input_tokens, field_name="cached_input_tokens")
        _validate_optional_non_negative_int(self.reasoning_tokens, field_name="reasoning_tokens")
        if self.model is not None and not self.model:
            msg = "model must not be empty when provided"
            raise ValueError(msg)

    @property
    def has_token_counts(self) -> bool:
        """Return whether any token category was safely extracted."""
        return any(
            count is not None
            for count in (
                self.input_tokens,
                self.output_tokens,
                self.total_tokens,
                self.cached_input_tokens,
                self.reasoning_tokens,
            )
        )


@dataclass(frozen=True, slots=True)
class CodexGenericEvidence:
    """Generic usage and cost evidence derived from Codex-safe facts."""

    usage_evidence: tuple[ModelUsageEvidence, ...] = field(default_factory=tuple)
    cost_evidence: tuple[ModelCostEvidence, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "usage_evidence", tuple(self.usage_evidence))
        object.__setattr__(self, "cost_evidence", tuple(self.cost_evidence))


def map_codex_completion_evidence(
    *,
    status: CodexTransportStatus,
    usage_facts: CodexCompletionUsageFacts | None = None,
) -> CodexGenericEvidence:
    """Map a Codex completion outcome into generic usage and cost evidence."""
    source = usage_facts.source if usage_facts is not None else ModelUsageEvidenceSource.RESPONSE_PAYLOAD
    return CodexGenericEvidence(
        usage_evidence=(
            _usage_evidence(
                status=status,
                source=source,
                usage_facts=usage_facts,
            ),
        ),
        cost_evidence=(
            _cost_evidence(
                status=status,
                source=source,
            ),
        ),
    )


def map_codex_usage_endpoint_evidence(result: CodexUsageResult) -> CodexGenericEvidence:
    """Map a Codex usage endpoint result into generic usage and cost evidence."""
    return CodexGenericEvidence(
        usage_evidence=(_usage_endpoint_evidence(result),),
        cost_evidence=(_usage_endpoint_cost_evidence(result.status),),
    )


def _usage_endpoint_evidence(result: CodexUsageResult) -> ModelUsageEvidence:
    quota = _quota_evidence(result)
    collection_status = _usage_endpoint_collection_status(status=result.status, quota=quota)
    return ModelUsageEvidence(
        provider=CODEX_PROVIDER,
        status=collection_status,
        source=ModelUsageEvidenceSource.USAGE_ENDPOINT,
        confidence=(
            ModelUsageEvidenceConfidence.EXTRACTED
            if result.evidence is not None
            else ModelUsageEvidenceConfidence.UNKNOWN
        ),
        quota=quota,
        observations=(
            _usage_endpoint_observation(
                status=result.status,
                collection_status=collection_status,
                evidence_values=result.evidence.values if result.evidence is not None else None,
                quota=quota,
            ),
        ),
    )


def _usage_endpoint_cost_evidence(status: CodexTransportStatus) -> ModelCostEvidence:
    return ModelCostEvidence(
        pricing_status=ModelPricingStatus.NOT_AVAILABLE,
        source=ModelUsageEvidenceSource.USAGE_ENDPOINT,
        confidence=ModelUsageEvidenceConfidence.UNKNOWN,
        observations=(
            ModelUsageObservation(
                message="Codex usage endpoint pricing evidence is not available for subscription-backed usage",
                metadata={"provider": CODEX_PROVIDER, "codex_usage_status": status.value},
            ),
        ),
    )


def _quota_evidence(result: CodexUsageResult) -> ModelQuotaEvidence | None:
    if result.evidence is None:
        return None
    values = result.evidence.values
    quota = ModelQuotaEvidence(
        limit=_safe_non_negative_int(values.get("limit")),
        remaining=_safe_non_negative_int(values.get("remaining")),
        reset_at=_safe_non_empty_text(values.get("reset_at")),
        window_seconds=_safe_non_negative_int(values.get("window_seconds")),
    )
    if any(
        value is not None
        for value in (
            quota.limit,
            quota.remaining,
            quota.reset_at,
            quota.window_seconds,
        )
    ):
        return quota
    return None


def _usage_endpoint_collection_status(
    *,
    status: CodexTransportStatus,
    quota: ModelQuotaEvidence | None,
) -> ModelUsageCollectionStatus:
    if status in {
        CodexTransportStatus.AUTHENTICATION_FAILED,
        CodexTransportStatus.CREDENTIAL_ERROR,
        CodexTransportStatus.TRANSPORT_ERROR,
    }:
        return ModelUsageCollectionStatus.FAILED
    if status is not CodexTransportStatus.SUCCESS:
        return ModelUsageCollectionStatus.UNAVAILABLE
    if quota is None:
        return ModelUsageCollectionStatus.UNAVAILABLE
    if _quota_field_count(quota) == _COMPLETE_QUOTA_FIELD_COUNT:
        return ModelUsageCollectionStatus.COLLECTED
    return ModelUsageCollectionStatus.PARTIALLY_COLLECTED


def _quota_field_count(quota: ModelQuotaEvidence) -> int:
    return sum(
        value is not None
        for value in (
            quota.limit,
            quota.remaining,
            quota.reset_at,
            quota.window_seconds,
        )
    )


def _usage_endpoint_observation(
    *,
    status: CodexTransportStatus,
    collection_status: ModelUsageCollectionStatus,
    evidence_values: object,
    quota: ModelQuotaEvidence | None,
) -> ModelUsageObservation:
    metadata: dict[str, SafeModelUsageObservationValue] = {
        "provider": CODEX_PROVIDER,
        "codex_usage_status": status.value,
        "collection_status": collection_status.value,
    }
    if quota is not None:
        metadata["quota_field_count"] = _quota_field_count(quota)
    if isinstance(evidence_values, Mapping):
        metadata.update(_safe_usage_endpoint_observation_metadata(cast("Mapping[object, object]", evidence_values)))
    return ModelUsageObservation(
        message=_usage_endpoint_observation_message(
            status=status,
            collection_status=collection_status,
            quota=quota,
        ),
        metadata=metadata,
    )


def _safe_usage_endpoint_observation_metadata(
    evidence_values: Mapping[object, object],
) -> dict[str, SafeModelUsageObservationValue]:
    return {
        key: cast("SafeModelUsageObservationValue", value)
        for key, value in evidence_values.items()
        if isinstance(key, str) and key in _SAFE_USAGE_OBSERVATION_KEYS and _is_safe_observation_value(value)
    }


def _usage_endpoint_observation_message(
    *,
    status: CodexTransportStatus,
    collection_status: ModelUsageCollectionStatus,
    quota: ModelQuotaEvidence | None,
) -> str:
    if quota is not None:
        return "Codex usage endpoint quota or rate-limit evidence was extracted"
    if status is CodexTransportStatus.SUCCESS:
        return "Codex usage endpoint did not include usable quota or rate-limit evidence"
    if collection_status is ModelUsageCollectionStatus.FAILED:
        return "Codex usage endpoint evidence collection failed"
    return "Codex usage endpoint quota or rate-limit evidence was unavailable"


def _safe_non_negative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _safe_non_empty_text(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _is_safe_observation_value(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _usage_evidence(
    *,
    status: CodexTransportStatus,
    source: ModelUsageEvidenceSource,
    usage_facts: CodexCompletionUsageFacts | None,
) -> ModelUsageEvidence:
    collection_status = _usage_collection_status(status=status, usage_facts=usage_facts)
    observations = (_usage_observation(status=status, collection_status=collection_status, usage_facts=usage_facts),)
    return ModelUsageEvidence(
        provider=CODEX_PROVIDER,
        status=collection_status,
        source=source,
        confidence=(
            ModelUsageEvidenceConfidence.EXTRACTED if usage_facts is not None else ModelUsageEvidenceConfidence.UNKNOWN
        ),
        model=usage_facts.model if usage_facts is not None else None,
        tokens=ModelTokenUsageEvidence(
            input_tokens=usage_facts.input_tokens if usage_facts is not None else None,
            output_tokens=usage_facts.output_tokens if usage_facts is not None else None,
            total_tokens=usage_facts.total_tokens if usage_facts is not None else None,
            cached_input_tokens=usage_facts.cached_input_tokens if usage_facts is not None else None,
            reasoning_tokens=usage_facts.reasoning_tokens if usage_facts is not None else None,
        ),
        observations=observations,
    )


def _cost_evidence(*, status: CodexTransportStatus, source: ModelUsageEvidenceSource) -> ModelCostEvidence:
    if status is CodexTransportStatus.SUCCESS:
        pricing_status = ModelPricingStatus.UNKNOWN
        confidence = ModelUsageEvidenceConfidence.UNKNOWN
        message = "Codex completion pricing is unknown for subscription-backed usage"
    else:
        pricing_status = ModelPricingStatus.NOT_AVAILABLE
        confidence = ModelUsageEvidenceConfidence.UNKNOWN
        message = "Codex completion pricing evidence is not available for this outcome"
    return ModelCostEvidence(
        pricing_status=pricing_status,
        source=source,
        confidence=confidence,
        observations=(
            ModelUsageObservation(
                message=message,
                metadata={"provider": CODEX_PROVIDER, "codex_status": status.value},
            ),
        ),
    )


def _usage_collection_status(
    *,
    status: CodexTransportStatus,
    usage_facts: CodexCompletionUsageFacts | None,
) -> ModelUsageCollectionStatus:
    if status is not CodexTransportStatus.SUCCESS:
        if status in {
            CodexTransportStatus.AUTHENTICATION_FAILED,
            CodexTransportStatus.CREDENTIAL_ERROR,
            CodexTransportStatus.TRANSPORT_ERROR,
        }:
            return ModelUsageCollectionStatus.FAILED
        return ModelUsageCollectionStatus.UNAVAILABLE
    if usage_facts is None or not usage_facts.has_token_counts:
        return ModelUsageCollectionStatus.UNAVAILABLE
    if (
        usage_facts.input_tokens is not None
        and usage_facts.output_tokens is not None
        and usage_facts.total_tokens is not None
    ):
        return ModelUsageCollectionStatus.COLLECTED
    return ModelUsageCollectionStatus.PARTIALLY_COLLECTED


def _usage_observation(
    *,
    status: CodexTransportStatus,
    collection_status: ModelUsageCollectionStatus,
    usage_facts: CodexCompletionUsageFacts | None,
) -> ModelUsageObservation:
    if usage_facts is not None and usage_facts.has_token_counts:
        message = "Codex completion usage token evidence was extracted"
    elif status is CodexTransportStatus.SUCCESS:
        message = "Codex completion response did not include usable token evidence"
    else:
        message = "Codex completion usage evidence was unavailable for this outcome"
    return ModelUsageObservation(
        message=message,
        metadata={
            "provider": CODEX_PROVIDER,
            "codex_status": status.value,
            "collection_status": collection_status.value,
        },
    )


def _validate_optional_non_negative_int(value: int | None, *, field_name: str) -> None:
    if value is not None and value < 0:
        msg = f"{field_name} must not be negative"
        raise ValueError(msg)
