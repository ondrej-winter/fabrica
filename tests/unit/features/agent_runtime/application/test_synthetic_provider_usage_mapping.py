"""Synthetic second-provider validation for generic usage evidence DTOs."""

from dataclasses import dataclass
from decimal import Decimal

from fabrica.features.agent_runtime.application.dtos import (
    ModelCostEvidence,
    ModelPricingStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    ModelUsageObservation,
)

SYNTHETIC_OPENAI_PROVIDER = "openai"
SYNTHETIC_OPENAI_MODEL = "gpt-synthetic-1"
SYNTHETIC_PROMPT_TOKENS = 120
SYNTHETIC_COMPLETION_TOKENS = 30
SYNTHETIC_TOTAL_TOKENS = 150


@dataclass(frozen=True, slots=True)
class SyntheticOpenAIStyleUsage:
    """Conventional API-style usage fields from a synthetic provider response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class SyntheticOpenAIStylePriceEstimate:
    """Public-price estimate fixture used to validate generic cost evidence."""

    amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class SyntheticOpenAIStyleResponse:
    """Test-local provider response shape with no production integration role."""

    model: str
    usage: SyntheticOpenAIStyleUsage
    public_price_estimate: SyntheticOpenAIStylePriceEstimate | None = None


def test_synthetic_openai_style_response_maps_tokens_into_generic_usage_evidence() -> None:
    response = SyntheticOpenAIStyleResponse(
        model=SYNTHETIC_OPENAI_MODEL,
        usage=SyntheticOpenAIStyleUsage(
            prompt_tokens=SYNTHETIC_PROMPT_TOKENS,
            completion_tokens=SYNTHETIC_COMPLETION_TOKENS,
            total_tokens=SYNTHETIC_TOTAL_TOKENS,
        ),
    )

    usage_evidence = _map_synthetic_openai_style_usage(response)

    assert usage_evidence == ModelUsageEvidence(
        provider=SYNTHETIC_OPENAI_PROVIDER,
        model=SYNTHETIC_OPENAI_MODEL,
        status=ModelUsageCollectionStatus.COLLECTED,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.EXTRACTED,
        tokens=ModelTokenUsageEvidence(
            input_tokens=SYNTHETIC_PROMPT_TOKENS,
            output_tokens=SYNTHETIC_COMPLETION_TOKENS,
            total_tokens=SYNTHETIC_TOTAL_TOKENS,
        ),
        observations=(ModelUsageObservation(message="synthetic OpenAI-style usage extracted from response payload"),),
    )


def test_synthetic_openai_style_public_price_estimate_maps_to_generic_cost_evidence() -> None:
    response = SyntheticOpenAIStyleResponse(
        model=SYNTHETIC_OPENAI_MODEL,
        usage=SyntheticOpenAIStyleUsage(
            prompt_tokens=SYNTHETIC_PROMPT_TOKENS,
            completion_tokens=SYNTHETIC_COMPLETION_TOKENS,
            total_tokens=SYNTHETIC_TOTAL_TOKENS,
        ),
        public_price_estimate=SyntheticOpenAIStylePriceEstimate(amount=Decimal("0.0045"), currency="USD"),
    )

    cost_evidence = _map_synthetic_openai_style_cost(response)

    assert cost_evidence == (
        ModelCostEvidence(
            pricing_status=ModelPricingStatus.PUBLIC_PRICE_ESTIMATE,
            estimated_amount=Decimal("0.0045"),
            currency="USD",
            source=ModelUsageEvidenceSource.SOURCE_CODE_OBSERVATION,
            confidence=ModelUsageEvidenceConfidence.ESTIMATED,
            observations=(ModelUsageObservation(message="synthetic public-price estimate from fixture"),),
        ),
    )


def test_synthetic_openai_style_usage_remains_valid_without_cost_evidence() -> None:
    response = SyntheticOpenAIStyleResponse(
        model=SYNTHETIC_OPENAI_MODEL,
        usage=SyntheticOpenAIStyleUsage(
            prompt_tokens=SYNTHETIC_PROMPT_TOKENS,
            completion_tokens=SYNTHETIC_COMPLETION_TOKENS,
            total_tokens=SYNTHETIC_TOTAL_TOKENS,
        ),
    )

    usage_evidence = _map_synthetic_openai_style_usage(response)
    cost_evidence = _map_synthetic_openai_style_cost(response)

    assert usage_evidence.provider == SYNTHETIC_OPENAI_PROVIDER
    assert usage_evidence.tokens.input_tokens == SYNTHETIC_PROMPT_TOKENS
    assert cost_evidence == ()


def _map_synthetic_openai_style_usage(response: SyntheticOpenAIStyleResponse) -> ModelUsageEvidence:
    return ModelUsageEvidence(
        provider=SYNTHETIC_OPENAI_PROVIDER,
        model=response.model,
        status=ModelUsageCollectionStatus.COLLECTED,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.EXTRACTED,
        tokens=ModelTokenUsageEvidence(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        ),
        observations=(ModelUsageObservation(message="synthetic OpenAI-style usage extracted from response payload"),),
    )


def _map_synthetic_openai_style_cost(response: SyntheticOpenAIStyleResponse) -> tuple[ModelCostEvidence, ...]:
    if response.public_price_estimate is None:
        return ()

    return (
        ModelCostEvidence(
            pricing_status=ModelPricingStatus.PUBLIC_PRICE_ESTIMATE,
            estimated_amount=response.public_price_estimate.amount,
            currency=response.public_price_estimate.currency,
            source=ModelUsageEvidenceSource.SOURCE_CODE_OBSERVATION,
            confidence=ModelUsageEvidenceConfidence.ESTIMATED,
            observations=(ModelUsageObservation(message="synthetic public-price estimate from fixture"),),
        ),
    )
