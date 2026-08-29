"""Tests for backend-neutral source-context hydration."""

import pytest

from fabrica.features.workspace_searching.application.context_hydration import hydrate_search_locations
from fabrica.features.workspace_searching.application.dtos import SearchLimits, SearchLocation

EXPECTED_UNICODE_COLUMN = 3


def test_hydrate_search_locations_normalizes_crlf_unicode_columns_and_context() -> None:
    locations = (SearchLocation(path="src/example.py", line=3, column_byte_offset=5, matched_text="match"),)

    matches = hydrate_search_locations(
        locations,
        {"src/example.py": "first\r\n\r\n😀abc\r\n    after\r\nfinal\r\n"},
        limits=SearchLimits(context_lines=2),
    )

    assert len(matches) == 1
    assert matches[0].column == EXPECTED_UNICODE_COLUMN
    assert matches[0].text == "😀abc"
    assert matches[0].before[0].text == "first"
    assert matches[0].before[1].text == ""
    assert matches[0].after[0].text == "    after"
    assert matches[0].after[1].text == "final"


def test_hydrate_search_locations_sorts_and_collapses_multiple_submatches_on_one_line() -> None:
    locations = (
        SearchLocation(path="src/z.py", line=1, column_byte_offset=2, matched_text="z"),
        SearchLocation(path="src/a.py", line=1, column_byte_offset=4, matched_text="a"),
        SearchLocation(path="src/a.py", line=1, column_byte_offset=4, matched_text="a"),
    )

    matches = hydrate_search_locations(
        locations,
        {"src/a.py": "😀abc\n", "src/z.py": "abz\n"},
        limits=SearchLimits(),
    )

    assert [(match.path, match.line, match.column) for match in matches] == [("src/a.py", 1, 2), ("src/z.py", 1, 3)]


def test_hydrate_search_locations_marks_matching_and_context_lines_as_truncated() -> None:
    locations = (SearchLocation(path="src/example.py", line=2, column_byte_offset=0, matched_text="b"),)

    matches = hydrate_search_locations(
        locations,
        {"src/example.py": "aaaa\nbbbb\ncccc\n"},
        limits=SearchLimits(context_lines=1, max_line_chars=2),
    )

    assert matches[0].text == "bb … [line truncated]"
    assert matches[0].text_truncated is True
    assert matches[0].before[0].text_truncated is True
    assert matches[0].after[0].text_truncated is True


@pytest.mark.parametrize(
    ("location", "source_text", "message"),
    [
        (
            SearchLocation(path="src/example.py", line=2, column_byte_offset=0, matched_text="match"),
            "only line\n",
            "outside source text",
        ),
        (
            SearchLocation(path="src/example.py", line=1, column_byte_offset=1, matched_text="match"),
            "😀abc\n",
            "Unicode character boundary",
        ),
    ],
)
def test_hydrate_search_locations_rejects_inconsistent_backend_locations(
    location: SearchLocation,
    source_text: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        hydrate_search_locations((location,), {"src/example.py": source_text}, limits=SearchLimits())
