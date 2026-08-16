"""Tests for product CLI output formatting."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from fabrica.adapters.inbound.cli.model_evidence import write_model_evidence_report
from fabrica.adapters.inbound.cli.rendering import (
    MAX_OUTPUT_LINE_CHARS,
    TRUNCATED_TEXT_MARKER,
    bound_text,
    format_metadata,
    write_line,
    write_text,
)
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
)


def test_bound_text_truncates_long_cli_lines() -> None:
    bounded = bound_text("x" * (MAX_OUTPUT_LINE_CHARS + 1))

    assert len(bounded) == MAX_OUTPUT_LINE_CHARS
    assert bounded == f"{'x' * (MAX_OUTPUT_LINE_CHARS - len(TRUNCATED_TEXT_MARKER))}{TRUNCATED_TEXT_MARKER}"


def test_bound_text_escapes_line_breaks() -> None:
    assert bound_text("hello\r\nworld") == r"hello\r\nworld"


def test_write_line_always_writes_one_logical_line() -> None:
    stdout = StringIO()

    write_line(stdout, "hello\nworld")

    assert stdout.getvalue() == r"hello\nworld" "\n"


def test_format_metadata_sorts_and_bounds_values() -> None:
    metadata = {"z": "last", "a": "x" * (MAX_OUTPUT_LINE_CHARS + 1)}

    formatted = format_metadata(metadata)

    assert len(formatted) == MAX_OUTPUT_LINE_CHARS
    assert formatted.startswith("a=")
    assert formatted.endswith(TRUNCATED_TEXT_MARKER)


def test_write_text_terminates_output_when_missing_newline() -> None:
    stdout = StringIO()

    write_text(stdout, "hello")

    assert stdout.getvalue() == "hello\n"


def test_write_model_evidence_report_formats_requested_usage_and_pricing() -> None:
    stdout = StringIO()

    write_model_evidence_report(
        usage_evidence=(
            ModelUsageEvidence(
                provider="codex",
                status=ModelUsageCollectionStatus.COLLECTED,
                source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
                confidence=ModelUsageEvidenceConfidence.OBSERVED,
                model="gpt-5.1",
                tokens=ModelTokenUsageEvidence(input_tokens=12, output_tokens=7, total_tokens=19),
                quota=ModelQuotaEvidence(limit=100, remaining=81, reset_at="2026-08-14T16:00:00Z"),
                observations=(ModelUsageObservation("from response"),),
            ),
        ),
        cost_evidence=(
            ModelCostEvidence(
                pricing_status=ModelPricingStatus.PUBLIC_PRICE_ESTIMATE,
                source=ModelUsageEvidenceSource.MANUAL_OBSERVATION,
                confidence=ModelUsageEvidenceConfidence.ESTIMATED,
                estimated_amount=Decimal("0.03"),
                currency="USD",
                observations=(ModelUsageObservation("estimated from public table"),),
            ),
        ),
        stdout=stdout,
        include_usage=True,
        include_prices=True,
    )

    assert stdout.getvalue() == (
        "Usage evidence:\n"
        "- provider=codex status=collected source=response_payload confidence=observed model=gpt-5.1 "
        "input_tokens=12 output_tokens=7 total_tokens=19 limit=100 remaining=81 "
        "reset_at=2026-08-14T16:00:00Z observation='from response'\n"
        "Pricing evidence:\n"
        "- status=public_price_estimate source=manual_observation confidence=estimated estimated_amount=0.03 "
        "currency=USD observation='estimated from public table'\n"
    )


def test_write_model_evidence_report_marks_requested_empty_sections_unavailable() -> None:
    stdout = StringIO()

    write_model_evidence_report(
        usage_evidence=(),
        cost_evidence=(),
        stdout=stdout,
        include_usage=True,
        include_prices=True,
    )

    assert stdout.getvalue() == "Usage evidence:\n- unavailable\nPricing evidence:\n- unavailable\n"
