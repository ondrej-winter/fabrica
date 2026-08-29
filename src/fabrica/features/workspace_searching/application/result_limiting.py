"""Complete-object per-query and aggregate result limiting."""

import json

from fabrica.features.workspace_searching.application.dtos import (
    SearchCodebaseResult,
    SearchLimits,
    SearchMatch,
    SearchQuery,
    SearchQueryResult,
    SearchQuerySuccess,
)
from fabrica.features.workspace_searching.application.result_formatting import (
    search_codebase_result_payload,
    search_query_result_payload,
)


def limit_query_matches(
    query: SearchQuery,
    matches: tuple[SearchMatch, ...],
    *,
    limits: SearchLimits,
    limit_reached: bool = False,
) -> SearchQuerySuccess:
    """Return a sorted query success whose matches fit its full JSON budget."""
    ordered_matches = tuple(sorted(matches, key=lambda match: (match.path, match.line, match.column)))
    capped_matches = ordered_matches[: limits.max_results_per_query]
    result_limit_reached = limit_reached or len(ordered_matches) > len(capped_matches)
    accepted: list[SearchMatch] = []
    for candidate in capped_matches:
        proposed = SearchQuerySuccess(
            query=query,
            matches=(*accepted, candidate),
            limit_reached=result_limit_reached,
            more_results_possible=result_limit_reached,
        )
        if _serialized_length(search_query_result_payload(proposed)) > limits.max_output_chars_per_query:
            return SearchQuerySuccess(
                query=query,
                matches=tuple(accepted),
                limit_reached=result_limit_reached,
                output_truncated=True,
                more_results_possible=True,
            )
        accepted.append(candidate)
    return SearchQuerySuccess(
        query=query,
        matches=tuple(accepted),
        limit_reached=result_limit_reached,
        more_results_possible=result_limit_reached,
    )


def limit_batch_results(results: tuple[SearchQueryResult, ...], *, limits: SearchLimits) -> SearchCodebaseResult:
    """Return ordered outcomes that fit the top-level JSON budget without cuts.

    Once the aggregate budget is exhausted, later successful outcomes become the
    explicit Version 1 batch-output omission representation. Failure outcomes
    remain intact because they have no equivalent omission DTO and are already
    required to preserve independent input validation feedback.
    """
    accepted: list[SearchQueryResult] = []
    budget_exhausted = False
    for result in results:
        candidate = _omitted_result(result) if budget_exhausted else result
        proposed = SearchCodebaseResult((*accepted, candidate))
        if _serialized_length(search_codebase_result_payload(proposed)) <= limits.max_output_chars_per_tool_call:
            accepted.append(candidate)
            continue
        budget_exhausted = True
        omitted = _omitted_result(result)
        proposed_omitted = SearchCodebaseResult((*accepted, omitted))
        if _serialized_length(search_codebase_result_payload(proposed_omitted)) > limits.max_output_chars_per_tool_call:
            msg = "aggregate search output limit cannot represent the required omission result"
            raise ValueError(msg)
        accepted.append(omitted)
    return SearchCodebaseResult(tuple(accepted))


def _omitted_result(result: SearchQueryResult) -> SearchQueryResult:
    if not isinstance(result, SearchQuerySuccess):
        return result
    return SearchQuerySuccess(
        query=result.query,
        matches=(),
        output_omitted=True,
        reason="BATCH_OUTPUT_LIMIT",
        more_results_possible=True,
    )


def _serialized_length(payload: object) -> int:
    return len(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


__all__ = ["limit_batch_results", "limit_query_matches"]
