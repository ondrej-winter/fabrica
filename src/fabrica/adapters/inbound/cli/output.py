"""Feature-neutral output formatting for the product CLI shell."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fabrica.shared_kernel.model_usage import (
        ModelCostEvidence,
        ModelUsageEvidence,
        ModelUsageObservation,
    )

MAX_OUTPUT_LINE_CHARS = 4_000


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
                write_line(stdout, f"- {_format_usage_evidence(evidence)}")
        else:
            write_line(stdout, "- unavailable")

    if include_prices:
        write_line(stdout, "Pricing evidence:")
        if cost_evidence:
            for evidence in cost_evidence:
                write_line(stdout, f"- {_format_cost_evidence(evidence)}")
        else:
            write_line(stdout, "- unavailable")


def write_line(stream: TextIO, text: str) -> None:
    """Write one bounded text line to a CLI stream."""
    bounded = _bound_text(text)
    stream.write(bounded)
    if not bounded.endswith("\n"):
        stream.write("\n")


def format_metadata(metadata: Mapping[str, object]) -> str:
    """Format safe observation metadata as sorted key-value fields."""
    if not metadata:
        return ""
    return " ".join(f"{key}={_bound_text(str(value))}" for key, value in sorted(metadata.items()))


def _format_usage_evidence(evidence: ModelUsageEvidence) -> str:
    fields = [
        f"provider={evidence.provider}",
        f"status={evidence.status.value}",
        f"source={evidence.source.value}",
        f"confidence={evidence.confidence.value}",
    ]
    if evidence.model is not None:
        fields.append(f"model={evidence.model}")
    fields.extend(_format_token_fields(evidence))
    if evidence.quota is not None:
        fields.extend(_present_fields(evidence.quota, ("limit", "remaining", "reset_at", "window_seconds")))
    fields.extend(_format_observation_messages(evidence.observations))
    return " ".join(fields)


def _format_cost_evidence(evidence: ModelCostEvidence) -> str:
    fields = [
        f"status={evidence.pricing_status.value}",
        f"source={evidence.source.value}",
        f"confidence={evidence.confidence.value}",
    ]
    if evidence.estimated_amount is not None and evidence.currency is not None:
        fields.append(f"estimated_amount={evidence.estimated_amount}")
        fields.append(f"currency={evidence.currency}")
    fields.extend(_format_observation_messages(evidence.observations))
    return " ".join(fields)


def _format_token_fields(evidence: ModelUsageEvidence) -> list[str]:
    return _present_fields(
        evidence.tokens,
        ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"),
    )


def _present_fields(value: object, names: tuple[str, ...]) -> list[str]:
    return [f"{name}={field_value}" for name in names if (field_value := getattr(value, name)) is not None]


def _format_observation_messages(observations: tuple[ModelUsageObservation, ...]) -> list[str]:
    return [f"observation={_bound_text(observation.message)!r}" for observation in observations]


def _bound_text(text: str) -> str:
    if len(text) <= MAX_OUTPUT_LINE_CHARS:
        return text
    return f"{text[:MAX_OUTPUT_LINE_CHARS]}...<truncated>"
