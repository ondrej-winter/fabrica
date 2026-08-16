"""Model evidence output for the product CLI adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

from fabrica.adapters.inbound.cli.rendering import bound_text, write_line

if TYPE_CHECKING:
    from fabrica.shared_kernel.model_usage import (
        ModelCostEvidence,
        ModelUsageEvidence,
        ModelUsageObservation,
    )


def write_model_evidence_report(
    *,
    usage_evidence: tuple[ModelUsageEvidence, ...],
    cost_evidence: tuple[ModelCostEvidence, ...],
    stdout: TextIO,
    include_usage: bool,
    include_prices: bool,
) -> None:
    """Write requested model usage and pricing evidence after command output."""
    if include_usage:
        write_line(stdout, "Usage evidence:")
        if usage_evidence:
            for evidence in usage_evidence:
                write_line(stdout, f"- {format_usage_evidence(evidence)}")
        else:
            write_line(stdout, "- unavailable")

    if include_prices:
        write_line(stdout, "Pricing evidence:")
        if cost_evidence:
            for evidence in cost_evidence:
                write_line(stdout, f"- {format_cost_evidence(evidence)}")
        else:
            write_line(stdout, "- unavailable")


def format_usage_evidence(evidence: ModelUsageEvidence) -> str:
    """Format one model usage evidence record for CLI output."""
    fields = [
        f"provider={evidence.provider}",
        f"status={evidence.status.value}",
        f"source={evidence.source.value}",
        f"confidence={evidence.confidence.value}",
    ]
    if evidence.model is not None:
        fields.append(f"model={evidence.model}")
    fields.extend(format_token_fields(evidence))
    if evidence.quota is not None:
        fields.extend(present_fields(evidence.quota, ("limit", "remaining", "reset_at", "window_seconds")))
    fields.extend(format_observation_messages(evidence.observations))
    return " ".join(fields)


def format_cost_evidence(evidence: ModelCostEvidence) -> str:
    """Format one model cost evidence record for CLI output."""
    fields = [
        f"status={evidence.pricing_status.value}",
        f"source={evidence.source.value}",
        f"confidence={evidence.confidence.value}",
    ]
    if evidence.estimated_amount is not None and evidence.currency is not None:
        fields.append(f"estimated_amount={evidence.estimated_amount}")
        fields.append(f"currency={evidence.currency}")
    fields.extend(format_observation_messages(evidence.observations))
    return " ".join(fields)


def format_token_fields(evidence: ModelUsageEvidence) -> list[str]:
    """Format present token evidence fields."""
    return present_fields(
        evidence.tokens,
        ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"),
    )


def present_fields(value: object, names: tuple[str, ...]) -> list[str]:
    """Format object attributes that have present values."""
    return [f"{name}={field_value}" for name in names if (field_value := getattr(value, name)) is not None]


def format_observation_messages(observations: tuple[ModelUsageObservation, ...]) -> list[str]:
    """Format model evidence observation messages safely."""
    return [f"observation={bound_text(observation.message)!r}" for observation in observations]


__all__ = ["write_model_evidence_report"]
