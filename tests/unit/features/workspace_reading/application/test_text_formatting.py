"""Tests for pure numbered text formatting and pagination."""

from collections.abc import Callable

import pytest

from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits
from fabrica.features.workspace_reading.application.text_formatting import FormattedTextRead, format_text_lines
from fabrica.features.workspace_reading.application.validation import normalize_text_line_range

SECOND_LINE = 2
THIRD_LINE = 3


@pytest.mark.parametrize(
    ("line_range", "expected_content"),
    [
        ((None, None), "1 | first\n2 | second\n3 | third"),
        ((2, None), "2 | second\n3 | third"),
        ((None, 2), "1 | first\n2 | second"),
        ((2, 2), "2 | second"),
    ],
)
def test_format_text_lines_renders_inclusive_normalized_ranges(
    line_range: tuple[int | None, int | None], expected_content: str
) -> None:
    result = format_text_lines(
        ("first", "second", "third"),
        line_range=normalize_text_line_range(*line_range),
        limits=ReadFilesLimits(),
    )

    assert result.content == expected_content
    assert result.complete is True
    assert result.next_start_line is None


def test_format_text_lines_marks_truncated_lines_without_paginating_a_complete_read() -> None:
    result = format_text_lines(
        ("abcdef",),
        line_range=normalize_text_line_range(None, None),
        limits=ReadFilesLimits(max_line_chars=3),
    )

    assert result.content == "1 | abc … [line truncated]"
    assert result.complete is True
    assert result.truncated_lines == (1,)


def test_format_text_lines_stops_before_the_first_line_that_would_exceed_the_output_cap() -> None:
    result = format_text_lines(
        ("first", "second", "third"),
        line_range=normalize_text_line_range(None, None),
        limits=ReadFilesLimits(max_output_chars_per_file=20),
    )

    assert result.content == "1 | first\n2 | second"
    assert result.end_line == SECOND_LINE
    assert result.complete is False
    assert result.next_start_line == THIRD_LINE


def test_format_text_lines_reports_continuation_when_the_output_cap_cannot_fit_one_numbered_line() -> None:
    result = format_text_lines(
        ("first",),
        line_range=normalize_text_line_range(None, None),
        limits=ReadFilesLimits(max_output_chars_per_file=1),
    )

    assert result.content == ""
    assert result.complete is False
    assert result.next_start_line == 1


def test_format_text_lines_stops_at_the_line_cap_and_reports_the_next_unread_line() -> None:
    result = format_text_lines(
        ("first", "second", "third"),
        line_range=normalize_text_line_range(None, None),
        limits=ReadFilesLimits(max_read_lines=2),
    )

    assert result.content == "1 | first\n2 | second"
    assert result.complete is False
    assert result.next_start_line == THIRD_LINE


def test_format_text_lines_completes_an_explicit_range_without_reading_beyond_its_end() -> None:
    result = format_text_lines(
        ("first", "second", "third"),
        line_range=normalize_text_line_range(1, 2),
        limits=ReadFilesLimits(max_read_lines=2),
    )

    assert result.content == "1 | first\n2 | second"
    assert result.complete is True
    assert result.next_start_line is None


def test_format_text_lines_returns_empty_complete_output_when_the_range_starts_past_eof() -> None:
    result = format_text_lines(
        ("first",),
        line_range=normalize_text_line_range(2, None),
        limits=ReadFilesLimits(),
    )

    assert result.content == ""
    assert result.start_line is None
    assert result.end_line is None
    assert result.complete is True


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: FormattedTextRead(
                content="1 | first",
                start_line=1,
                end_line=1,
                complete=True,
                next_start_line=2,
                truncated_lines=(),
            ),
            "pagination metadata",
        ),
        (
            lambda: FormattedTextRead(
                content="",
                start_line=None,
                end_line=1,
                complete=True,
                next_start_line=None,
                truncated_lines=(),
            ),
            "empty output",
        ),
        (
            lambda: FormattedTextRead(
                content="1 | first",
                start_line=1,
                end_line=1,
                complete=False,
                next_start_line=3,
                truncated_lines=(),
            ),
            "next unread line",
        ),
        (
            lambda: FormattedTextRead(
                content="1 | first",
                start_line=1,
                end_line=1,
                complete=True,
                next_start_line=None,
                truncated_lines=(2,),
            ),
            "returned lines",
        ),
        (
            lambda: FormattedTextRead(
                content="1 | first\n2 | second",
                start_line=1,
                end_line=2,
                complete=True,
                next_start_line=None,
                truncated_lines=(2, 1),
            ),
            "ordered and unique",
        ),
    ],
)
def test_formatted_text_read_rejects_invalid_metadata(factory: Callable[[], FormattedTextRead], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()
