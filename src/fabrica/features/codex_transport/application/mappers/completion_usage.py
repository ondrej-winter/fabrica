"""Map Codex completion usage facts into provider-agnostic evidence."""

from dataclasses import dataclass

from fabrica.features.codex_transport.application.dtos import CodexTransportStatus
from fabrica.features.codex_transport.application.mappers.generic_usage_evidence import (
    CODEX_PROVIDER,
    CodexGenericEvidence,
)
from fabrica.shared_kernel.model_usage import (
    ModelCostEvidence,
    ModelPricingStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    ModelUsageObservation,
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


__all__ = ["CodexCompletionUsageFacts", "map_codex_completion_evidence"]
