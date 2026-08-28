"""Tests for workspace-searching application DTO contracts."""

from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.workspace_searching.application.dtos import (
    DEFAULT_CONTEXT_LINES,
    DEFAULT_MAX_LINE_CHARS,
    DEFAULT_MAX_OUTPUT_PER_QUERY,
    DEFAULT_MAX_OUTPUT_PER_TOOL_CALL,
    DEFAULT_MAX_PARALLEL_SEARCHES,
    DEFAULT_MAX_QUERIES_PER_CALL,
    DEFAULT_MAX_RESULTS_PER_QUERY,
    DEFAULT_MAX_SEARCH_FILE_BYTES,
    DEFAULT_PER_QUERY_TIMEOUT_SECONDS,
    DEFAULT_TOOL_TIMEOUT_SECONDS,
    SearchCodebaseCommand,
    SearchCodebaseResult,
    SearchContextLine,
    SearchError,
    SearchErrorCode,
    SearchLimits,
    SearchMatch,
    SearchQuery,
    SearchQueryFailure,
    SearchQuerySuccess,
)

EXPECTED_CONTEXT_LINES = 2
EXPECTED_MAX_LINE_CHARS = 2_000
EXPECTED_MAX_RESULTS_PER_QUERY = 100
EXPECTED_MAX_OUTPUT_CHARS = 48_000
EXPECTED_MAX_QUERIES_PER_CALL = 8
EXPECTED_MAX_PARALLEL_SEARCHES = 4
EXPECTED_MAX_SEARCH_FILE_BYTES = 10_000_000
EXPECTED_PER_QUERY_TIMEOUT_SECONDS = 30.0
EXPECTED_TOOL_TIMEOUT_SECONDS = 60.0
EXPECTED_UNICODE_COLUMN = 2


def test_search_limits_match_accepted_defaults() -> None:
    limits = SearchLimits()

    assert limits.context_lines == DEFAULT_CONTEXT_LINES == EXPECTED_CONTEXT_LINES
    assert limits.max_line_chars == DEFAULT_MAX_LINE_CHARS == EXPECTED_MAX_LINE_CHARS
    assert limits.max_results_per_query == DEFAULT_MAX_RESULTS_PER_QUERY == EXPECTED_MAX_RESULTS_PER_QUERY
    assert limits.max_output_chars_per_query == DEFAULT_MAX_OUTPUT_PER_QUERY == EXPECTED_MAX_OUTPUT_CHARS
    assert limits.max_queries_per_call == DEFAULT_MAX_QUERIES_PER_CALL == EXPECTED_MAX_QUERIES_PER_CALL
    assert limits.max_output_chars_per_tool_call == DEFAULT_MAX_OUTPUT_PER_TOOL_CALL == EXPECTED_MAX_OUTPUT_CHARS
    assert limits.max_parallel_searches == DEFAULT_MAX_PARALLEL_SEARCHES == EXPECTED_MAX_PARALLEL_SEARCHES
    assert limits.max_search_file_bytes == DEFAULT_MAX_SEARCH_FILE_BYTES == EXPECTED_MAX_SEARCH_FILE_BYTES
    assert limits.per_query_timeout_seconds == DEFAULT_PER_QUERY_TIMEOUT_SECONDS == EXPECTED_PER_QUERY_TIMEOUT_SECONDS
    assert limits.tool_timeout_seconds == DEFAULT_TOOL_TIMEOUT_SECONDS == EXPECTED_TOOL_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: SearchQuery(""), "empty"),
        (lambda: SearchQuery("name", path="../outside"), "non-escaping"),
        (lambda: SearchQuery("name", glob=" "), "whitespace"),
        (lambda: SearchLimits(max_parallel_searches=9), "must not exceed"),
        (lambda: SearchLimits(per_query_timeout_seconds=0), "deadlines must be positive"),
        (lambda: SearchLimits(tool_timeout_seconds=2, per_query_timeout_seconds=3), "must not be shorter"),
        (lambda: SearchLimits(max_retries=2), "between 0 and 1"),
    ],
)
def test_search_query_and_limit_dtos_reject_invalid_values(factory: Callable[[], object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        factory()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: SearchLimits(context_lines=0),
        lambda: SearchLimits(max_line_chars=0),
        lambda: SearchLimits(max_results_per_query=0),
        lambda: SearchLimits(max_output_chars_per_query=0),
        lambda: SearchLimits(max_queries_per_call=0),
        lambda: SearchLimits(max_output_chars_per_tool_call=0),
        lambda: SearchLimits(max_search_file_bytes=0),
    ],
)
def test_search_limits_reject_each_non_positive_bound(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        factory()


def test_search_query_rejects_non_boolean_case_sensitivity() -> None:
    with pytest.raises(TypeError, match="boolean"):
        SearchQuery("name", case_sensitive=cast("bool", 1))


def test_search_command_and_result_copy_entries_and_enforce_batch_bounds() -> None:
    query = SearchQuery("UserService")
    command = SearchCodebaseCommand((query,))
    result = SearchCodebaseResult((SearchQuerySuccess(query=query, matches=()),))

    assert command.queries == (query,)
    assert result.results[0].query == query
    with pytest.raises(ValueError, match="safe batch bound"):
        SearchCodebaseCommand(tuple(query for _ in range(DEFAULT_MAX_QUERIES_PER_CALL + 1)))
    with pytest.raises(ValueError, match="must not be empty"):
        SearchCodebaseCommand(())
    with pytest.raises(ValueError, match="must not be empty"):
        SearchCodebaseResult(())


def test_search_error_uses_immutable_safe_metadata() -> None:
    metadata = {"backend_status": 2}
    error = SearchError(SearchErrorCode.INVALID_REGEX, metadata=metadata)
    metadata["backend_status"] = 1

    assert error.metadata == {"backend_status": 2}
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", error.metadata)["backend_status"] = 3


@pytest.mark.parametrize(
    ("factory", "exception", "message"),
    [
        (lambda: SearchError(SearchErrorCode.IO_ERROR, message="x" * 1_001), ValueError, "safe bound"),
        (lambda: SearchError(SearchErrorCode.IO_ERROR, metadata={"bad-key": "value"}), ValueError, "safe identifiers"),
        (
            lambda: SearchError(
                SearchErrorCode.IO_ERROR,
                metadata=cast("dict[str, str | int | float | bool | None]", {"value": object()}),
            ),
            TypeError,
            "scalar and safe",
        ),
    ],
)
def test_search_error_rejects_unsafe_content(
    factory: Callable[[], object], exception: type[Exception], message: str
) -> None:
    with pytest.raises(exception, match=message):
        factory()


def test_search_result_models_unicode_character_column_and_ordered_context() -> None:
    match = SearchMatch(
        path="src/service.py",
        line=4,
        column=2,
        text="éUserService",
        text_truncated=False,
        before=(SearchContextLine(line=3, text="@final"),),
        after=(SearchContextLine(line=5, text="pass"),),
    )
    success = SearchQuerySuccess(query=SearchQuery("UserService"), matches=(match,))

    assert match.column == EXPECTED_UNICODE_COLUMN
    assert success.matches_returned == 1
    with pytest.raises(FrozenInstanceError):
        _set_frozen_field(instance=success, field_name="limit_reached", value=True)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: SearchContextLine(line=0, text="text"), "one-based"),
        (lambda: SearchContextLine(line=1, text=" text"), "whitespace"),
        (lambda: SearchContextLine(line=1, text="text", text_truncated=cast("bool", 1)), "boolean"),
        (
            lambda: SearchMatch(
                path="src/service.py",
                line=4,
                column=1,
                text="match",
                text_truncated=False,
                before=(SearchContextLine(line=4, text="invalid"),),
            ),
            "precede",
        ),
        (
            lambda: SearchMatch(
                path="src/service.py",
                line=4,
                column=1,
                text="match",
                text_truncated=False,
                after=(SearchContextLine(line=4, text="invalid"),),
            ),
            "follow",
        ),
        (
            lambda: SearchMatch(
                path="src/service.py",
                line=4,
                column=1,
                text="match",
                text_truncated=False,
                before=(SearchContextLine(line=3, text="late"), SearchContextLine(line=2, text="early")),
            ),
            "ordered",
        ),
        (
            lambda: SearchMatch(path=".", line=1, column=1, text="match", text_truncated=False),
            "workspace file",
        ),
    ],
)
def test_search_match_dtos_reject_invalid_locations_and_context(factory: Callable[[], object], message: str) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        factory()


def test_search_success_validates_limit_and_omission_semantics() -> None:
    query = SearchQuery("UserService")

    omitted = SearchQuerySuccess(
        query=query,
        matches=(),
        output_omitted=True,
        reason="BATCH_OUTPUT_LIMIT",
        more_results_possible=True,
    )

    assert omitted.matches_returned == 0
    with pytest.raises(ValueError, match="more_results_possible"):
        SearchQuerySuccess(query=query, matches=(), more_results_possible=True)
    match = SearchMatch(path="src/service.py", line=1, column=1, text="match", text_truncated=False)
    with pytest.raises(ValueError, match="ordered"):
        SearchQuerySuccess(
            query=query,
            matches=(
                SearchMatch(path="src/z.py", line=1, column=1, text="later", text_truncated=False),
                match,
            ),
        )
    with pytest.raises(ValueError, match="output-omitted"):
        SearchQuerySuccess(
            query=query,
            matches=(match,),
            output_omitted=True,
            reason="BATCH_OUTPUT_LIMIT",
            more_results_possible=True,
        )
    with pytest.raises(ValueError, match="batch-output-limit"):
        SearchQuerySuccess(query=query, matches=(), output_omitted=True)
    with pytest.raises(ValueError, match="only output-omitted"):
        SearchQuerySuccess(query=query, matches=(), reason="BATCH_OUTPUT_LIMIT")


def test_error_taxonomy_reserves_backend_classified_failures() -> None:
    assert {code.value for code in SearchErrorCode} == {
        "INVALID_INPUT",
        "EMPTY_PATTERN",
        "INVALID_PATH",
        "PATH_OUTSIDE_WORKSPACE",
        "NOT_FOUND",
        "INVALID_REGEX",
        "INVALID_GLOB",
        "FILE_TOO_LARGE",
        "SEARCH_BACKEND_UNAVAILABLE",
        "SEARCH_TIMEOUT",
        "SEARCH_CANCELLED",
        "IO_ERROR",
    }
    failure = SearchQueryFailure(query=None, error=SearchError(SearchErrorCode.INVALID_GLOB))

    assert failure.success is False


def _set_frozen_field(instance: object, field_name: str, value: object) -> None:
    """Attempt ordinary mutation through a dynamic test boundary."""
    setattr(instance, field_name, value)
