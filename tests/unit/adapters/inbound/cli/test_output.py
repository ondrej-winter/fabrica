"""Tests for product CLI output formatting."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from fabrica.adapters.inbound.cli.model_evidence import write_model_evidence_report
from fabrica.adapters.inbound.cli.rendering import (
    MAX_OUTPUT_LINE_CHARS,
    TRUNCATED_TEXT_MARKER,
    bound_multiline_text,
    bound_text,
    format_metadata,
    terminal_safe_text,
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


def test_bound_text_preserves_text_at_exact_line_bound() -> None:
    assert bound_text("x" * MAX_OUTPUT_LINE_CHARS) == "x" * MAX_OUTPUT_LINE_CHARS


def test_bound_text_escapes_line_breaks() -> None:
    assert bound_text("hello\r\nworld") == r"hello\r\nworld"


def test_bound_text_escapes_terminal_control_sequences() -> None:
    assert bound_text("plain\x1b[31mred\x1b[0m\x07") == r"plain\x1b[31mred\x1b[0m\x07"


def test_bound_text_escapes_c1_controls_and_del() -> None:
    assert bound_text("status\x85next\x9b31m\x7f") == r"status\x85next\x9b31m\x7f"


def test_bound_text_preserves_safe_printable_text() -> None:
    assert bound_text("safe text: provider=codex model=gpt-5") == "safe text: provider=codex model=gpt-5"


def test_bound_text_escapes_before_truncating_control_sequences() -> None:
    safe_prefix = "x" * (MAX_OUTPUT_LINE_CHARS - len(TRUNCATED_TEXT_MARKER))

    bounded = bound_text(f"{safe_prefix}abcdefghijk\x1b")

    assert len(bounded) == MAX_OUTPUT_LINE_CHARS
    assert bounded == f"{safe_prefix}{TRUNCATED_TEXT_MARKER}"


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


def test_format_metadata_returns_empty_text_for_empty_metadata() -> None:
    assert format_metadata({}) == ""


def test_format_metadata_escapes_untrusted_terminal_controls() -> None:
    assert format_metadata({"message": "bad\x1b[2J\x07"}) == r"message=bad\x1b[2J\x07"


def test_write_text_terminates_output_when_missing_newline() -> None:
    stdout = StringIO()

    write_text(stdout, "hello")

    assert stdout.getvalue() == "hello\n"


def test_write_text_preserves_existing_trailing_newline() -> None:
    stdout = StringIO()

    write_text(stdout, "hello\n")

    assert stdout.getvalue() == "hello\n"


def test_bound_multiline_text_preserves_newlines_and_escapes_terminal_controls() -> None:
    assert bound_multiline_text("line 1\nline 2\x1b[2J") == "line 1\nline 2\\x1b[2J"


def test_terminal_safe_text_escapes_controls_without_truncating() -> None:
    long_text = f"{'x' * (MAX_OUTPUT_LINE_CHARS + 10)}\x1b[2J"

    safe_text = terminal_safe_text(long_text)

    assert safe_text == f"{'x' * (MAX_OUTPUT_LINE_CHARS + 10)}\\x1b[2J"


def test_write_text_escapes_terminal_controls_from_untrusted_output() -> None:
    stdout = StringIO()

    write_text(stdout, "raw\x1b[31mred\x1b[0m")

    assert stdout.getvalue() == r"raw\x1b[31mred\x1b[0m" "\n"


def test_format_metadata_limits_field_count() -> None:
    formatted = format_metadata({f"field_{index:02}": index for index in range(60)})

    assert "field_00=0" in formatted
    assert "field_49=49" in formatted
    assert "field_50=50" not in formatted
    assert "metadata_fields_truncated=true" in formatted


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
                observations=(ModelUsageObservation("from response", metadata={"collection_status": "collected"}),),
            ),
        ),
        cost_evidence=(
            ModelCostEvidence(
                pricing_status=ModelPricingStatus.PUBLIC_PRICE_ESTIMATE,
                source=ModelUsageEvidenceSource.MANUAL_OBSERVATION,
                confidence=ModelUsageEvidenceConfidence.ESTIMATED,
                estimated_amount=Decimal("0.03"),
                currency="USD",
                observations=(ModelUsageObservation("estimated from public table", metadata={"provider": "codex"}),),
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
        "reset_at=2026-08-14T16:00:00Z observation='from response' collection_status=collected\n"
        "Pricing evidence:\n"
        "- status=public_price_estimate source=manual_observation confidence=estimated estimated_amount=0.03 "
        "currency=USD observation='estimated from public table' provider=codex\n"
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


def test_write_model_evidence_report_escapes_observation_terminal_controls() -> None:
    stdout = StringIO()

    write_model_evidence_report(
        usage_evidence=(
            ModelUsageEvidence(
                provider="codex",
                status=ModelUsageCollectionStatus.COLLECTED,
                source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
                confidence=ModelUsageEvidenceConfidence.OBSERVED,
                observations=(ModelUsageObservation("bad\x1b[2J\x07"),),
            ),
        ),
        cost_evidence=(),
        stdout=stdout,
        include_usage=True,
        include_prices=False,
    )

    assert r"observation='bad\\x1b[2J\\x07'" in stdout.getvalue()
    assert "\x1b" not in stdout.getvalue()
    assert "\x07" not in stdout.getvalue()
