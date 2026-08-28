"""Tests for backend-neutral workspace search locations."""

from collections.abc import Callable

import pytest

from fabrica.features.workspace_searching.application.dtos import SearchLocation

EXPECTED_LINE = 2
EXPECTED_COLUMN_BYTE_OFFSET = 3
INVALID_LOCATION_MESSAGE = "must"


def test_search_location_accepts_a_valid_unhydrated_backend_match() -> None:
    location = SearchLocation(
        path="src/example.py",
        line=EXPECTED_LINE,
        column_byte_offset=EXPECTED_COLUMN_BYTE_OFFSET,
        matched_text="match",
    )

    assert location.path == "src/example.py"
    assert location.line == EXPECTED_LINE
    assert location.column_byte_offset == EXPECTED_COLUMN_BYTE_OFFSET
    assert location.matched_text == "match"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SearchLocation(path=".", line=1, column_byte_offset=0, matched_text="match"),
        lambda: SearchLocation(path="../outside.py", line=1, column_byte_offset=0, matched_text="match"),
        lambda: SearchLocation(path="src/example.py", line=0, column_byte_offset=0, matched_text="match"),
        lambda: SearchLocation(path="src/example.py", line=1, column_byte_offset=-1, matched_text="match"),
        lambda: SearchLocation(path="src/example.py", line=1, column_byte_offset=0, matched_text=""),
    ],
)
def test_search_location_rejects_invalid_backend_locations(factory: Callable[[], SearchLocation]) -> None:
    with pytest.raises(ValueError, match=INVALID_LOCATION_MESSAGE):
        factory()
