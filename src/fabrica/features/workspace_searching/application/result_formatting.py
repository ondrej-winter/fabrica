"""Canonical JSON-compatible formatting for workspace-searching results."""

from fabrica.features.workspace_searching.application.dtos import (
    SearchCodebaseResult,
    SearchContextLine,
    SearchMatch,
    SearchQuery,
    SearchQueryResult,
    SearchQuerySuccess,
)


def search_codebase_result_payload(result: SearchCodebaseResult) -> dict[str, object]:
    """Return the stable top-level payload for a complete search batch."""
    return {"results": [search_query_result_payload(item) for item in result.results]}


def search_query_result_payload(result: SearchQueryResult) -> dict[str, object]:
    """Return the stable payload for one independent query outcome."""
    if isinstance(result, SearchQuerySuccess):
        return {
            "query": search_query_payload(result.query),
            "success": True,
            "matches": [search_match_payload(match) for match in result.matches],
            "matches_returned": result.matches_returned,
            "limit_reached": result.limit_reached,
            "output_truncated": result.output_truncated,
            "output_omitted": result.output_omitted,
            "reason": result.reason,
            "more_results_possible": result.more_results_possible,
        }
    return {
        "query": search_query_payload(result.query) if result.query is not None else None,
        "success": False,
        "error": {
            "code": result.error.code.value,
            "message": result.error.message,
            "metadata": dict(result.error.metadata),
        },
    }


def search_query_payload(query: SearchQuery) -> dict[str, object]:
    """Return the canonical public representation of one query."""
    return {
        "pattern": query.pattern,
        "path": query.path,
        "glob": query.glob,
        "case_sensitive": query.case_sensitive,
    }


def search_match_payload(match: SearchMatch) -> dict[str, object]:
    """Return the canonical public representation of one matching line."""
    return {
        "path": match.path,
        "line": match.line,
        "column": match.column,
        "text": match.text,
        "text_truncated": match.text_truncated,
        "before": [_context_line_payload(line) for line in match.before],
        "after": [_context_line_payload(line) for line in match.after],
    }


def _context_line_payload(line: SearchContextLine) -> dict[str, object]:
    return {"line": line.line, "text": line.text, "text_truncated": line.text_truncated}


__all__ = [
    "search_codebase_result_payload",
    "search_match_payload",
    "search_query_payload",
    "search_query_result_payload",
]
