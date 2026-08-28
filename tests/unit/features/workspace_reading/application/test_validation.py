"""Tests for pure workspace-reading range validation."""

import pytest

from fabrica.features.workspace_reading.application.validation import normalize_text_line_range


@pytest.mark.parametrize(
    ("start_line", "end_line", "expected_start", "expected_end"),
    [
        (None, None, 1, None),
        (4, None, 4, None),
        (None, 4, 1, 4),
        (4, 9, 4, 9),
    ],
)
def test_normalize_text_line_range_applies_canonical_defaults(
    start_line: int | None, end_line: int | None, expected_start: int, expected_end: int | None
) -> None:
    result = normalize_text_line_range(start_line, end_line)

    assert result.start_line == expected_start
    assert result.end_line == expected_end


@pytest.mark.parametrize(
    ("start_line", "end_line", "message"),
    [
        (0, None, "one-based"),
        (None, 0, "one-based"),
        (-1, None, "one-based"),
        (True, None, "one-based"),
        (3, 2, "less than or equal"),
    ],
)
def test_normalize_text_line_range_rejects_invalid_bounds(
    start_line: int | None, end_line: int | None, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        normalize_text_line_range(start_line, end_line)
