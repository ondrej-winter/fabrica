"""Tests for complete-object workspace-searching result limits."""

from fabrica.features.workspace_searching.application.dtos import (
    SearchCodebaseResult,
    SearchLimits,
    SearchMatch,
    SearchQuery,
    SearchQuerySuccess,
)
from fabrica.features.workspace_searching.application.result_formatting import search_codebase_result_payload
from fabrica.features.workspace_searching.application.result_limiting import limit_batch_results, limit_query_matches


def test_limit_query_matches_sorts_caps_and_never_returns_a_partial_match_object() -> None:
    query = SearchQuery("match")
    matches = (
        _match("src/z.py", "z"),
        _match("src/a.py", "a"),
        _match("src/b.py", "b"),
    )

    result = limit_query_matches(query, matches, limits=SearchLimits(max_results_per_query=2))

    assert [match.path for match in result.matches] == ["src/a.py", "src/b.py"]
    assert result.limit_reached is True
    assert result.output_truncated is False
    assert result.more_results_possible is True


def test_limit_query_matches_marks_output_truncation_before_exceeding_the_json_budget() -> None:
    query = SearchQuery("match")
    baseline = limit_query_matches(query, (), limits=SearchLimits())
    baseline_length = len(str(search_codebase_result_payload(SearchCodebaseResult((baseline,)))))
    limits = SearchLimits(max_output_chars_per_query=baseline_length + 10)

    result = limit_query_matches(query, (_match("src/a.py", "x" * 100),), limits=limits)

    assert result.matches == ()
    assert result.output_truncated is True
    assert result.more_results_possible is True


def test_limit_batch_results_replaces_later_successes_with_explicit_omissions() -> None:
    first = SearchQuerySuccess(query=SearchQuery("first"), matches=(_match("src/a.py", "a"),))
    second = SearchQuerySuccess(query=SearchQuery("second"), matches=(_match("src/b.py", "b"),))
    omitted_second = SearchQuerySuccess(
        query=second.query,
        matches=(),
        output_omitted=True,
        reason="BATCH_OUTPUT_LIMIT",
        more_results_possible=True,
    )
    first_only = len(str(search_codebase_result_payload(SearchCodebaseResult((first,)))))
    with_omission = len(str(search_codebase_result_payload(SearchCodebaseResult((first, omitted_second)))))
    limits = SearchLimits(max_output_chars_per_tool_call=with_omission)

    result = limit_batch_results((first, second), limits=limits)

    assert result.results[0] == first
    assert result.results[1] == omitted_second
    assert with_omission > first_only


def _match(path: str, text: str) -> SearchMatch:
    return SearchMatch(path=path, line=1, column=1, text=text, text_truncated=False)
