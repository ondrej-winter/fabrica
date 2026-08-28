"""Pure structural validation for workspace-searching requests."""

from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.workspace_searching.application.dtos import (
    DEFAULT_MAX_QUERIES_PER_CALL,
    SearchCodebaseCommand,
    SearchError,
    SearchErrorCode,
    SearchQuery,
    SearchQueryFailure,
)


@dataclass(frozen=True, slots=True)
class ValidatedSearchBatch:
    """Ordered valid queries and independent failures from raw canonical input."""

    entries: tuple[SearchQuery | SearchQueryFailure, ...]

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        if not entries:
            msg = "entries must not be empty"
            raise ValueError(msg)
        if len(entries) > DEFAULT_MAX_QUERIES_PER_CALL:
            msg = "entries exceeds the safe batch bound"
            raise ValueError(msg)
        object.__setattr__(self, "entries", entries)

    @property
    def command(self) -> SearchCodebaseCommand | None:
        """Return the executable canonical command when every entry is valid."""
        if any(isinstance(entry, SearchQueryFailure) for entry in self.entries):
            return None
        queries = tuple(entry for entry in self.entries if isinstance(entry, SearchQuery))
        return SearchCodebaseCommand(queries)


def validate_search_queries(raw_queries: object) -> ValidatedSearchBatch:
    """Validate canonical raw queries without evaluating regex or glob grammar."""
    if not isinstance(raw_queries, tuple):
        msg = "queries must be a tuple of canonical query objects"
        raise TypeError(msg)
    if not raw_queries:
        msg = "queries must not be empty"
        raise ValueError(msg)
    if len(raw_queries) > DEFAULT_MAX_QUERIES_PER_CALL:
        msg = "queries exceeds the safe batch bound"
        raise ValueError(msg)
    return ValidatedSearchBatch(tuple(_validate_query(raw_query) for raw_query in raw_queries))


def _validate_query(raw_query: object) -> SearchQuery | SearchQueryFailure:
    if not isinstance(raw_query, Mapping):
        return _invalid_input_failure("query must be an object")
    if set(raw_query) - {"pattern", "path", "glob", "case_sensitive"}:
        return _invalid_input_failure("query must not include additional properties")
    pattern = raw_query.get("pattern")
    if not isinstance(pattern, str):
        return _invalid_input_failure("query requires a string pattern")
    if not pattern.strip():
        return SearchQueryFailure(
            query=None,
            error=SearchError(SearchErrorCode.EMPTY_PATTERN, "pattern must not be empty"),
        )
    path = raw_query.get("path", ".")
    glob = raw_query.get("glob")
    case_sensitive = raw_query.get("case_sensitive", False)
    try:
        return SearchQuery(pattern=pattern, path=path, glob=glob, case_sensitive=case_sensitive)
    except (TypeError, ValueError) as err:
        return _invalid_input_failure(str(err))


def _invalid_input_failure(message: str) -> SearchQueryFailure:
    return SearchQueryFailure(query=None, error=SearchError(SearchErrorCode.INVALID_INPUT, message))


__all__ = ["ValidatedSearchBatch", "validate_search_queries"]
