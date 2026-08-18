"""Model evidence output helpers for the product CLI shell."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

from fabrica.adapters.inbound.cli.rendering import bound_text, format_metadata, write_line

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
    """Write requested model usage and pricing evidence after command output.

    Empty requested sections are rendered as unavailable so callers can
    distinguish “the user asked for evidence but none was collected” from “the
    user did not request this evidence section.” Observation messages are bounded
    to one safe CLI output line.
    """
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
    """Format one model usage evidence record as stable CLI fields."""
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
    """Format one model cost evidence record as stable CLI fields."""
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
    """Format only token evidence fields that were collected."""
    return present_fields(
        evidence.tokens,
        ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"),
    )


def present_fields(value: object, names: tuple[str, ...]) -> list[str]:
    """Format named object attributes whose values are not ``None``."""
    return [f"{name}={field_value}" for name in names if (field_value := getattr(value, name)) is not None]


def format_observation_messages(observations: tuple[ModelUsageObservation, ...]) -> list[str]:
    """Format bounded model evidence observation messages for CLI output."""
    return [format_observation_message(observation) for observation in observations]


def format_observation_message(observation: ModelUsageObservation) -> str:
    """Format one bounded model evidence observation and its safe metadata."""
    metadata = format_metadata(observation.metadata)
    suffix = f" {metadata}" if metadata else ""
    return f"observation={bound_text(observation.message)!r}{suffix}"


__all__ = ["write_model_evidence_report"]
