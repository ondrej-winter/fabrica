"""Tests for Codex generic usage and cost evidence mapping."""

import pytest

from fabrica.features.codex_transport.application.dtos import (
    CodexTransportStatus,
    CodexUsageEvidence,
    CodexUsageResult,
)
from fabrica.features.codex_transport.application.mappers import (
    CodexCompletionUsageFacts,
    map_codex_completion_evidence,
    map_codex_usage_endpoint_evidence,
)
from fabrica.shared_kernel.model_usage import (
    ModelPricingStatus,
    ModelUsageCollectionStatus,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
)

COMPLETE_INPUT_TOKENS = 12
COMPLETE_OUTPUT_TOKENS = 5
COMPLETE_TOTAL_TOKENS = 17
COMPLETE_CACHED_INPUT_TOKENS = 3
COMPLETE_REASONING_TOKENS = 2
PARTIAL_OUTPUT_TOKENS = 5
USAGE_LIMIT = 100
USAGE_REMAINING = 75
USAGE_PERCENT = 25
USAGE_WINDOW_SECONDS = 3600


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


def test_map_codex_usage_endpoint_evidence_maps_safe_quota_fields() -> None:
    evidence = map_codex_usage_endpoint_evidence(
        CodexUsageResult(
            status=CodexTransportStatus.SUCCESS,
            evidence=CodexUsageEvidence(
                {
                    "limit": USAGE_LIMIT,
                    "remaining": USAGE_REMAINING,
                    "reset_at": "2026-08-05T20:00:00Z",
                    "window_seconds": USAGE_WINDOW_SECONDS,
                    "plan_type": "synthetic-pro",
                    "usage_percent": USAGE_PERCENT,
                },
            ),
        ),
    )

    usage = evidence.usage_evidence[0]
    cost = evidence.cost_evidence[0]

    assert usage.provider == "codex"
    assert usage.status is ModelUsageCollectionStatus.COLLECTED
    assert usage.source is ModelUsageEvidenceSource.USAGE_ENDPOINT
    assert usage.confidence is ModelUsageEvidenceConfidence.EXTRACTED
    assert usage.quota is not None
    assert usage.quota.limit == USAGE_LIMIT
    assert usage.quota.remaining == USAGE_REMAINING
    assert usage.quota.reset_at == "2026-08-05T20:00:00Z"
    assert usage.quota.window_seconds == USAGE_WINDOW_SECONDS
    assert usage.tokens.total_tokens is None
    assert usage.observations[0].metadata["plan_type"] == "synthetic-pro"
    assert usage.observations[0].metadata["usage_percent"] == USAGE_PERCENT
    assert cost.pricing_status is ModelPricingStatus.NOT_AVAILABLE
    assert cost.source is ModelUsageEvidenceSource.USAGE_ENDPOINT


def test_map_codex_usage_endpoint_evidence_maps_partial_quota_without_coercion() -> None:
    evidence = map_codex_usage_endpoint_evidence(
        CodexUsageResult(
            status=CodexTransportStatus.SUCCESS,
            evidence=CodexUsageEvidence(
                {
                    "remaining": USAGE_REMAINING,
                    "limit": "100",
                    "window_seconds": -1,
                    "reset_at": "",
                },
            ),
        ),
    )

    usage = evidence.usage_evidence[0]

    assert usage.status is ModelUsageCollectionStatus.PARTIALLY_COLLECTED
    assert usage.quota is not None
    assert usage.quota.limit is None
    assert usage.quota.remaining == USAGE_REMAINING
    assert usage.quota.reset_at is None
    assert usage.quota.window_seconds is None


def test_map_codex_usage_endpoint_evidence_reports_success_without_quota_as_unavailable() -> None:
    evidence = map_codex_usage_endpoint_evidence(
        CodexUsageResult(
            status=CodexTransportStatus.SUCCESS,
            evidence=CodexUsageEvidence({"plan_type": "synthetic-pro"}),
        ),
    )

    usage = evidence.usage_evidence[0]

    assert usage.status is ModelUsageCollectionStatus.UNAVAILABLE
    assert usage.quota is None
    assert usage.confidence is ModelUsageEvidenceConfidence.EXTRACTED
    assert usage.observations[0].metadata["plan_type"] == "synthetic-pro"


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
def test_map_codex_usage_endpoint_evidence_maps_non_success_statuses(
    status: CodexTransportStatus,
    expected_collection_status: ModelUsageCollectionStatus,
) -> None:
    evidence = map_codex_usage_endpoint_evidence(CodexUsageResult(status=status))

    usage = evidence.usage_evidence[0]
    cost = evidence.cost_evidence[0]

    assert usage.status is expected_collection_status
    assert usage.source is ModelUsageEvidenceSource.USAGE_ENDPOINT
    assert usage.quota is None
    assert cost.pricing_status is ModelPricingStatus.NOT_AVAILABLE


def test_map_codex_usage_endpoint_evidence_does_not_expose_unsafe_values() -> None:
    evidence = map_codex_usage_endpoint_evidence(
        CodexUsageResult(
            status=CodexTransportStatus.SUCCESS,
            evidence=CodexUsageEvidence(
                {
                    "remaining": USAGE_REMAINING,
                    "account_id": "synthetic-account",
                    "access_token": "synthetic-access-token",
                },
            ),
        ),
    )

    assert "synthetic-account" not in str(evidence)
    assert "synthetic-access-token" not in str(evidence)
