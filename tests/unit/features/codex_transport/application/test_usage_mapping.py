"""Tests for Codex generic usage and cost evidence mapping."""

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    ModelPricingStatus,
    ModelUsageCollectionStatus,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
)
from fabrica.features.codex_transport.application.dtos import CodexTransportStatus
from fabrica.features.codex_transport.application.usage_mapping import (
    CodexCompletionUsageFacts,
    map_codex_completion_evidence,
)

COMPLETE_INPUT_TOKENS = 12
COMPLETE_OUTPUT_TOKENS = 5
COMPLETE_TOTAL_TOKENS = 17
COMPLETE_CACHED_INPUT_TOKENS = 3
COMPLETE_REASONING_TOKENS = 2
PARTIAL_OUTPUT_TOKENS = 5


def test_map_codex_completion_evidence_maps_complete_token_usage() -> None:
    evidence = map_codex_completion_evidence(
        status=CodexTransportStatus.SUCCESS,
        usage_facts=CodexCompletionUsageFacts(
            source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
            input_tokens=COMPLETE_INPUT_TOKENS,
            output_tokens=COMPLETE_OUTPUT_TOKENS,
            total_tokens=COMPLETE_TOTAL_TOKENS,
            cached_input_tokens=COMPLETE_CACHED_INPUT_TOKENS,
            reasoning_tokens=COMPLETE_REASONING_TOKENS,
            model="codex-mini",
        ),
    )

    usage = evidence.usage_evidence[0]
    cost = evidence.cost_evidence[0]

    assert usage.provider == "codex"
    assert usage.status is ModelUsageCollectionStatus.COLLECTED
    assert usage.source is ModelUsageEvidenceSource.RESPONSE_PAYLOAD
    assert usage.confidence is ModelUsageEvidenceConfidence.EXTRACTED
    assert usage.model == "codex-mini"
    assert usage.tokens.input_tokens == COMPLETE_INPUT_TOKENS
    assert usage.tokens.output_tokens == COMPLETE_OUTPUT_TOKENS
    assert usage.tokens.total_tokens == COMPLETE_TOTAL_TOKENS
    assert usage.tokens.cached_input_tokens == COMPLETE_CACHED_INPUT_TOKENS
    assert usage.tokens.reasoning_tokens == COMPLETE_REASONING_TOKENS
    assert cost.pricing_status is ModelPricingStatus.UNKNOWN
    assert cost.estimated_amount is None
    assert cost.currency is None


def test_map_codex_completion_evidence_maps_partial_usage_without_defaulting_missing_fields() -> None:
    evidence = map_codex_completion_evidence(
        status=CodexTransportStatus.SUCCESS,
        usage_facts=CodexCompletionUsageFacts(
            source=ModelUsageEvidenceSource.STREAM_EVENT,
            output_tokens=PARTIAL_OUTPUT_TOKENS,
        ),
    )

    usage = evidence.usage_evidence[0]

    assert usage.status is ModelUsageCollectionStatus.PARTIALLY_COLLECTED
    assert usage.source is ModelUsageEvidenceSource.STREAM_EVENT
    assert usage.tokens.input_tokens is None
    assert usage.tokens.output_tokens == PARTIAL_OUTPUT_TOKENS
    assert usage.tokens.total_tokens is None


def test_map_codex_completion_evidence_marks_success_without_usage_unavailable() -> None:
    evidence = map_codex_completion_evidence(status=CodexTransportStatus.SUCCESS)

    usage = evidence.usage_evidence[0]

    assert usage.status is ModelUsageCollectionStatus.UNAVAILABLE
    assert usage.tokens.input_tokens is None
    assert usage.confidence is ModelUsageEvidenceConfidence.UNKNOWN
    assert usage.observations[0].metadata["collection_status"] == "unavailable"


@pytest.mark.parametrize(
    ("status", "expected_collection_status"),
    [
        (CodexTransportStatus.AUTHENTICATION_FAILED, ModelUsageCollectionStatus.FAILED),
        (CodexTransportStatus.CREDENTIAL_ERROR, ModelUsageCollectionStatus.FAILED),
        (CodexTransportStatus.TRANSPORT_ERROR, ModelUsageCollectionStatus.FAILED),
        (CodexTransportStatus.RATE_LIMITED, ModelUsageCollectionStatus.UNAVAILABLE),
        (CodexTransportStatus.QUOTA_EXCEEDED, ModelUsageCollectionStatus.UNAVAILABLE),
        (CodexTransportStatus.BACKEND_SHAPE_MISMATCH, ModelUsageCollectionStatus.UNAVAILABLE),
    ],
)
def test_map_codex_completion_evidence_maps_non_success_statuses(
    status: CodexTransportStatus,
    expected_collection_status: ModelUsageCollectionStatus,
) -> None:
    evidence = map_codex_completion_evidence(status=status)

    usage = evidence.usage_evidence[0]
    cost = evidence.cost_evidence[0]

    assert usage.status is expected_collection_status
    assert usage.tokens.total_tokens is None
    assert cost.pricing_status is ModelPricingStatus.NOT_AVAILABLE
    assert cost.estimated_amount is None


def test_codex_completion_usage_facts_reject_negative_token_counts() -> None:
    with pytest.raises(ValueError, match="input_tokens must not be negative"):
        CodexCompletionUsageFacts(
            source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
            input_tokens=-1,
        )
