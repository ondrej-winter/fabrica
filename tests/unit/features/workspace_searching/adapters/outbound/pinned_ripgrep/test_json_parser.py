"""Tests for incremental ripgrep JSON-lines parsing."""

import pytest

from fabrica.features.workspace_searching.adapters.outbound.pinned_ripgrep.json_parser import (
    RipgrepJsonEventError,
    parse_ripgrep_json_event,
    parse_ripgrep_json_events,
)

EXPECTED_LINE = 7
EXPECTED_COLUMN_BYTE_OFFSET = 4


def test_parse_ripgrep_json_events_yields_one_location_for_each_matching_line() -> None:
    events = (
        '{"type":"begin","data":{"path":{"text":"src/example.py"}}}',
        '{"type":"match","data":{"path":{"text":"src/example.py"},"line_number":7,"submatches":[{"match":{"text":"User"},"start":4,"end":8}]}}',
        '{"type":"summary","data":{}}',
    )

    locations = tuple(parse_ripgrep_json_events(events))

    assert len(locations) == 1
    assert locations[0].path == "src/example.py"
    assert locations[0].line == EXPECTED_LINE
    assert locations[0].column_byte_offset == EXPECTED_COLUMN_BYTE_OFFSET
    assert locations[0].matched_text == "User"


def test_parse_ripgrep_json_event_uses_only_the_first_match_on_a_matching_line() -> None:
    location = parse_ripgrep_json_event(
        '{"type":"match","data":{"path":{"text":"src/example.py"},"line_number":1,"submatches":[{"match":{"text":"first"},"start":1,"end":6},{"match":{"text":"second"},"start":10,"end":16}]}}'
    )

    assert location is not None
    assert location.column_byte_offset == 1
    assert location.matched_text == "first"


def test_parse_ripgrep_json_event_ignores_non_match_events() -> None:
    assert parse_ripgrep_json_event('{"type":"summary","data":{}}') is None


@pytest.mark.parametrize(
    "event",
    [
        "not json",
        "[]",
        '{"type":"match","data":{}}',
        '{"type":"match","data":{"path":{"text":"src/example.py"},"line_number":0,"submatches":[]}}',
        '{"type":"match","data":{"path":{"text":"src/example.py"},"line_number":1,"submatches":[{}]}}',
        '{"type":"match","data":{"path":{"base64":"YQ=="},"line_number":1,"submatches":[{"match":{"text":"a"},"start":0,"end":1}]}}',
    ],
)
def test_parse_ripgrep_json_event_rejects_malformed_or_non_utf8_match_events(event: str) -> None:
    with pytest.raises(RipgrepJsonEventError):
        parse_ripgrep_json_event(event)
