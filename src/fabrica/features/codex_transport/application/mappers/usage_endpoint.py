"""Map Codex usage endpoint results into provider-agnostic evidence."""

from collections.abc import Mapping

from fabrica.features.codex_transport.application.dtos import CodexTransportStatus, CodexUsageResult
from fabrica.features.codex_transport.application.mappers.generic_usage_evidence import (
    CODEX_PROVIDER,
    CODEX_USAGE_ENDPOINT_PRICING_OBSERVATION_KEYS,
    CODEX_USAGE_ENDPOINT_USAGE_OBSERVATION_KEYS,
    CodexGenericEvidence,
    safe_codex_observation_metadata,
)
from fabrica.shared_kernel.model_usage import (
    ModelCostEvidence,
    ModelPricingStatus,
    ModelQuotaEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    ModelUsageObservation,
)

_COMPLETE_QUOTA_FIELD_COUNT = 4


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
                metadata=safe_codex_observation_metadata(
                    {"provider": CODEX_PROVIDER, "codex_usage_status": status.value},
                    allowed_keys=CODEX_USAGE_ENDPOINT_PRICING_OBSERVATION_KEYS,
                ),
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
    metadata: dict[str, object] = {
        "provider": CODEX_PROVIDER,
        "codex_usage_status": status.value,
        "collection_status": collection_status.value,
    }
    if quota is not None:
        metadata["quota_field_count"] = _quota_field_count(quota)
    if isinstance(evidence_values, Mapping):
        metadata.update(evidence_values)
    return ModelUsageObservation(
        message=_usage_endpoint_observation_message(
            status=status,
            collection_status=collection_status,
            quota=quota,
        ),
        metadata=safe_codex_observation_metadata(
            metadata,
            allowed_keys=CODEX_USAGE_ENDPOINT_USAGE_OBSERVATION_KEYS,
        ),
    )


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


__all__ = ["map_codex_usage_endpoint_evidence"]
