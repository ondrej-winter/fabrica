"""Tests for provider-agnostic usage and cost evidence DTO contracts."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.shared_kernel.model_usage import (
    DEFAULT_MAX_MODEL_USAGE_OBSERVATION_MESSAGE_CHARS,
    DEFAULT_MAX_MODEL_USAGE_OBSERVATION_METADATA_KEY_CHARS,
    DEFAULT_MAX_MODEL_USAGE_OBSERVATION_METADATA_STRING_VALUE_CHARS,
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

EXPECTED_INPUT_TOKENS = 10
EXPECTED_QUOTA_LIMIT = 100


def test_usage_evidence_vocabularies_match_v1_contract() -> None:
    assert {status.value for status in ModelUsageCollectionStatus} == {
        "collected",
        "partially_collected",
        "unavailable",
        "unsupported",
        "failed",
    }
    assert {confidence.value for confidence in ModelUsageEvidenceConfidence} == {
        "observed",
        "extracted",
        "inferred",
        "manual",
        "estimated",
        "unknown",
    }
    assert {source.value for source in ModelUsageEvidenceSource} == {
        "response_payload",
        "stream_event",
        "response_header",
        "usage_endpoint",
        "manual_observation",
        "source_code_observation",
    }
    assert {status.value for status in ModelPricingStatus} == {
        "unknown",
        "not_available",
        "subscription_included",
        "unsupported",
    }


def test_token_evidence_preserves_absent_values_and_rejects_negative_counts() -> None:
    tokens = ModelTokenUsageEvidence(input_tokens=EXPECTED_INPUT_TOKENS, output_tokens=0)

    assert tokens.input_tokens == EXPECTED_INPUT_TOKENS
    assert tokens.output_tokens == 0
    assert tokens.total_tokens is None
    assert tokens.cached_input_tokens is None
    assert tokens.reasoning_tokens is None

    with pytest.raises(ValueError, match="input_tokens"):
        ModelTokenUsageEvidence(input_tokens=-1)
    with pytest.raises(ValueError, match="reasoning_tokens"):
        ModelTokenUsageEvidence(reasoning_tokens=-1)


def test_quota_evidence_preserves_optional_fields_and_rejects_negative_values() -> None:
    quota = ModelQuotaEvidence(limit=EXPECTED_QUOTA_LIMIT, remaining=0, reset_at="2026-08-05T18:00:00Z")

    assert quota.limit == EXPECTED_QUOTA_LIMIT
    assert quota.remaining == 0
    assert quota.reset_at == "2026-08-05T18:00:00Z"
    assert quota.window_seconds is None

    with pytest.raises(ValueError, match="remaining"):
        ModelQuotaEvidence(remaining=-1)
    with pytest.raises(ValueError, match="window_seconds"):
        ModelQuotaEvidence(window_seconds=-1)
    with pytest.raises(ValueError, match="reset_at"):
        ModelQuotaEvidence(reset_at="")


def test_usage_observation_metadata_is_safe_copied_and_immutable() -> None:
    metadata: dict[str, SafeModelUsageObservationValue] = {
        "category": "partial",
        "token_count": EXPECTED_INPUT_TOKENS,
    }
    observation = ModelUsageObservation(message="provider returned partial usage", metadata=metadata)

    metadata["category"] = "mutated"

    assert observation.metadata["category"] == "partial"
    assert observation.metadata["token_count"] == EXPECTED_INPUT_TOKENS
    with pytest.raises(TypeError):
        cast("dict[str, object]", observation.metadata)["category"] = "changed"


def test_usage_observation_accepts_scalar_metadata_at_documented_bounds() -> None:
    metadata_key = "k" * DEFAULT_MAX_MODEL_USAGE_OBSERVATION_METADATA_KEY_CHARS
    metadata_value = "v" * DEFAULT_MAX_MODEL_USAGE_OBSERVATION_METADATA_STRING_VALUE_CHARS

    observation = ModelUsageObservation(
        message="m" * DEFAULT_MAX_MODEL_USAGE_OBSERVATION_MESSAGE_CHARS,
        metadata={
            metadata_key: metadata_value,
            "integer": 1,
            "float": 1.5,
            "boolean": True,
            "none": None,
        },
    )

    assert observation.message == "m" * DEFAULT_MAX_MODEL_USAGE_OBSERVATION_MESSAGE_CHARS
    assert observation.metadata[metadata_key] == metadata_value
    assert dict(observation.metadata) == {
        metadata_key: metadata_value,
        "integer": 1,
        "float": 1.5,
        "boolean": True,
        "none": None,
    }


def test_usage_observation_rejects_invalid_metadata_and_unbounded_messages() -> None:
    unsafe_key_metadata = cast("dict[str, SafeModelUsageObservationValue]", {1: "unsafe"})
    unsafe_nested_metadata = cast("dict[str, SafeModelUsageObservationValue]", {"raw": {"nested": "payload"}})

    with pytest.raises(TypeError, match="keys must be strings"):
        ModelUsageObservation(message="unsafe", metadata=unsafe_key_metadata)
    with pytest.raises(ValueError, match="keys must not be empty"):
        ModelUsageObservation(message="unsafe", metadata={"": "unsafe"})
    with pytest.raises(ValueError, match="metadata key exceeds"):
        ModelUsageObservation(
            message="unsafe",
            metadata={"k" * (DEFAULT_MAX_MODEL_USAGE_OBSERVATION_METADATA_KEY_CHARS + 1): "unsafe"},
        )
    with pytest.raises(TypeError, match="bounded scalar"):
        ModelUsageObservation(message="unsafe", metadata=unsafe_nested_metadata)
    with pytest.raises(ValueError, match=r"string value.*exceeds"):
        ModelUsageObservation(
            message="unsafe",
            metadata={"safe_key": "v" * (DEFAULT_MAX_MODEL_USAGE_OBSERVATION_METADATA_STRING_VALUE_CHARS + 1)},
        )
    with pytest.raises(ValueError, match="message must not be empty"):
        ModelUsageObservation(message="")
    with pytest.raises(ValueError, match="safe usage observation bound"):
        ModelUsageObservation(message="x" * (DEFAULT_MAX_MODEL_USAGE_OBSERVATION_MESSAGE_CHARS + 1))


def test_usage_evidence_carries_provider_model_tokens_quota_and_observations() -> None:
    tokens = ModelTokenUsageEvidence(input_tokens=12, output_tokens=8, total_tokens=20)
    quota = ModelQuotaEvidence(limit=100, remaining=80)
    observation = ModelUsageObservation(message="usage extracted from response payload")
    evidence = ModelUsageEvidence(
        provider="synthetic",
        model="model-a",
        status=ModelUsageCollectionStatus.COLLECTED,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.EXTRACTED,
        tokens=tokens,
        quota=quota,
        observations=(observation,),
    )

    assert evidence.provider == "synthetic"
    assert evidence.model == "model-a"
    assert evidence.tokens == tokens
    assert evidence.quota == quota
    assert evidence.observations == (observation,)

    with pytest.raises(ValueError, match="provider"):
        ModelUsageEvidence(
            provider="",
            status=ModelUsageCollectionStatus.COLLECTED,
            source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
            confidence=ModelUsageEvidenceConfidence.EXTRACTED,
        )


def test_cost_evidence_allows_the_accepted_non_monetary_pricing_states() -> None:
    for pricing_status in (
        ModelPricingStatus.UNKNOWN,
        ModelPricingStatus.NOT_AVAILABLE,
        ModelPricingStatus.SUBSCRIPTION_INCLUDED,
        ModelPricingStatus.UNSUPPORTED,
    ):
        assert (
            ModelCostEvidence(
                pricing_status=pricing_status,
                source=ModelUsageEvidenceSource.USAGE_ENDPOINT,
                confidence=ModelUsageEvidenceConfidence.UNKNOWN,
            ).pricing_status
            is pricing_status
        )


def test_usage_and_cost_evidence_are_immutable_boundary_values() -> None:
    usage_evidence = ModelUsageEvidence(
        provider="synthetic",
        status=ModelUsageCollectionStatus.UNAVAILABLE,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.UNKNOWN,
    )
    cost_evidence = ModelCostEvidence(
        pricing_status=ModelPricingStatus.SUBSCRIPTION_INCLUDED,
        source=ModelUsageEvidenceSource.MANUAL_OBSERVATION,
        confidence=ModelUsageEvidenceConfidence.MANUAL,
    )

    with pytest.raises(FrozenInstanceError):
        usage_evidence.provider = "changed"  # ty: ignore[invalid-assignment]
    with pytest.raises(FrozenInstanceError):
        cost_evidence.pricing_status = ModelPricingStatus.UNKNOWN  # ty: ignore[invalid-assignment]
