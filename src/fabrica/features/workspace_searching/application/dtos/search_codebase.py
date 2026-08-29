"""Immutable DTOs for the workspace-searching application boundary."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

DEFAULT_CONTEXT_LINES = 2
DEFAULT_MAX_LINE_CHARS = 2_000
DEFAULT_MAX_RESULTS_PER_QUERY = 100
DEFAULT_MAX_OUTPUT_PER_QUERY = 48_000
DEFAULT_MAX_QUERIES_PER_CALL = 8
DEFAULT_MAX_OUTPUT_PER_TOOL_CALL = 48_000
DEFAULT_MAX_PARALLEL_SEARCHES = 4
DEFAULT_MAX_SEARCH_FILE_BYTES = 10_000_000
DEFAULT_PER_QUERY_TIMEOUT_SECONDS = 30.0
DEFAULT_TOOL_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 1
MAX_SEARCH_PATTERN_CHARS = 4_096
MAX_WORKSPACE_PATH_CHARS = 4_096
MAX_GLOB_CHARS = 4_096
MAX_ERROR_MESSAGE_CHARS = 1_000

SafeSearchMetadataValue = str | int | float | bool | None


class SearchErrorCode(StrEnum):
    """Stable Version 1 error codes for individual search outcomes."""

    INVALID_INPUT = "INVALID_INPUT"
    EMPTY_PATTERN = "EMPTY_PATTERN"
    INVALID_PATH = "INVALID_PATH"
    PATH_OUTSIDE_WORKSPACE = "PATH_OUTSIDE_WORKSPACE"
    NOT_FOUND = "NOT_FOUND"
    INVALID_REGEX = "INVALID_REGEX"
    INVALID_GLOB = "INVALID_GLOB"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    SEARCH_BACKEND_UNAVAILABLE = "SEARCH_BACKEND_UNAVAILABLE"
    SEARCH_TIMEOUT = "SEARCH_TIMEOUT"
    SEARCH_CANCELLED = "SEARCH_CANCELLED"
    IO_ERROR = "IO_ERROR"


@dataclass(frozen=True, slots=True)
class SearchLimits:
    """Bounds for one workspace-searching batch invocation."""

    context_lines: int = DEFAULT_CONTEXT_LINES
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY
    max_output_chars_per_query: int = DEFAULT_MAX_OUTPUT_PER_QUERY
    max_queries_per_call: int = DEFAULT_MAX_QUERIES_PER_CALL
    max_output_chars_per_tool_call: int = DEFAULT_MAX_OUTPUT_PER_TOOL_CALL
    max_parallel_searches: int = DEFAULT_MAX_PARALLEL_SEARCHES
    max_search_file_bytes: int = DEFAULT_MAX_SEARCH_FILE_BYTES
    per_query_timeout_seconds: float = DEFAULT_PER_QUERY_TIMEOUT_SECONDS
    tool_timeout_seconds: float = DEFAULT_TOOL_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES

    def __post_init__(self) -> None:
        for field_name in (
            "context_lines",
            "max_line_chars",
            "max_results_per_query",
            "max_output_chars_per_query",
            "max_queries_per_call",
            "max_output_chars_per_tool_call",
            "max_parallel_searches",
            "max_search_file_bytes",
        ):
            if getattr(self, field_name) < 1:
                msg = f"{field_name} must be at least 1"
                raise ValueError(msg)
        if self.max_parallel_searches > self.max_queries_per_call:
            msg = "max_parallel_searches must not exceed max_queries_per_call"
            raise ValueError(msg)
        if self.per_query_timeout_seconds <= 0 or self.tool_timeout_seconds <= 0:
            msg = "search deadlines must be positive"
            raise ValueError(msg)
        if self.tool_timeout_seconds < self.per_query_timeout_seconds:
            msg = "tool deadline must not be shorter than the per-query deadline"
            raise ValueError(msg)
        if self.max_retries < 0 or self.max_retries > DEFAULT_MAX_RETRIES:
            msg = "max_retries must be between 0 and 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """One canonical regex search request with literal workspace scope controls."""

    pattern: str
    path: str = "."
    glob: str | None = None
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        _validate_pattern(self.pattern)
        _validate_workspace_scope(self.path)
        _validate_glob(self.glob)
        if not isinstance(self.case_sensitive, bool):
            msg = "case_sensitive must be a boolean"
            raise TypeError(msg)


@dataclass(frozen=True, slots=True)
class SearchCodebaseCommand:
    """Canonical ordered batch command for workspace source discovery."""

    queries: tuple[SearchQuery, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "queries", tuple(self.queries))
        if not self.queries:
            msg = "queries must not be empty"
            raise ValueError(msg)
        if len(self.queries) > DEFAULT_MAX_QUERIES_PER_CALL:
            msg = "queries exceeds the safe batch bound"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SearchError:
    """Stable safe error returned for one independent search query."""

    code: SearchErrorCode
    message: str | None = None
    metadata: Mapping[str, SafeSearchMetadataValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.message is not None and len(self.message) > MAX_ERROR_MESSAGE_CHARS:
            msg = "search error message exceeds the safe bound"
            raise ValueError(msg)
        metadata = dict(self.metadata)
        for key, value in metadata.items():
            if not key or not key.replace("_", "").isalnum():
                msg = "search error metadata keys must be safe identifiers"
                raise ValueError(msg)
            if not isinstance(value, (str, int, float, bool, type(None))):
                msg = "search error metadata values must be scalar and safe"
                raise TypeError(msg)
        object.__setattr__(self, "metadata", MappingProxyType(metadata))


@dataclass(frozen=True, slots=True)
class SearchContextLine:
    """A bounded, one-based source line surrounding a search match."""

    line: int
    text: str
    text_truncated: bool = False

    def __post_init__(self) -> None:
        _validate_one_based_integer(self.line, field_name="line")
        _validate_source_text(self.text, field_name="text")
        _validate_boolean(self.text_truncated, field_name="text_truncated")


@dataclass(frozen=True, slots=True)
class SearchMatch:
    """One matching source line and its structured surrounding context."""

    path: str
    line: int
    column: int
    text: str
    text_truncated: bool
    before: tuple[SearchContextLine, ...] = field(default_factory=tuple)
    after: tuple[SearchContextLine, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_workspace_result_path(self.path)
        _validate_one_based_integer(self.line, field_name="line")
        _validate_one_based_integer(self.column, field_name="column")
        _validate_source_text(self.text, field_name="text")
        _validate_boolean(self.text_truncated, field_name="text_truncated")
        before = tuple(self.before)
        after = tuple(self.after)
        if any(context.line >= self.line for context in before):
            msg = "before context lines must precede the matching line"
            raise ValueError(msg)
        if any(context.line <= self.line for context in after):
            msg = "after context lines must follow the matching line"
            raise ValueError(msg)
        if tuple(sorted(line.line for line in before)) != tuple(line.line for line in before):
            msg = "before context lines must be ordered"
            raise ValueError(msg)
        if tuple(sorted(line.line for line in after)) != tuple(line.line for line in after):
            msg = "after context lines must be ordered"
            raise ValueError(msg)
        object.__setattr__(self, "before", before)
        object.__setattr__(self, "after", after)


@dataclass(frozen=True, slots=True)
class SearchQuerySuccess:
    """Successful query outcome, including no-match and bounded-result states."""

    query: SearchQuery
    matches: tuple[SearchMatch, ...]
    limit_reached: bool = False
    output_truncated: bool = False
    output_omitted: bool = False
    reason: str | None = None
    more_results_possible: bool = False
    success: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        matches = tuple(self.matches)
        if len(matches) > DEFAULT_MAX_RESULTS_PER_QUERY:
            msg = "matches exceeds the safe per-query bound"
            raise ValueError(msg)
        if tuple(sorted(matches, key=lambda match: (match.path, match.line, match.column))) != matches:
            msg = "matches must be ordered by path, line, and column"
            raise ValueError(msg)
        for field_name in ("limit_reached", "output_truncated", "output_omitted", "more_results_possible"):
            _validate_boolean(getattr(self, field_name), field_name=field_name)
        if self.output_omitted:
            if matches:
                msg = "output-omitted results must not contain matches"
                raise ValueError(msg)
            if self.reason != "BATCH_OUTPUT_LIMIT" or not self.more_results_possible:
                msg = "output-omitted results require the batch-output-limit reason"
                raise ValueError(msg)
        elif self.reason is not None:
            msg = "only output-omitted results may include a reason"
            raise ValueError(msg)
        if not (self.limit_reached or self.output_truncated or self.output_omitted) and self.more_results_possible:
            msg = "more_results_possible requires a limiting condition"
            raise ValueError(msg)
        object.__setattr__(self, "matches", matches)

    @property
    def matches_returned(self) -> int:
        """Return the number of complete matching-line objects returned."""
        return len(self.matches)


@dataclass(frozen=True, slots=True)
class SearchQueryFailure:
    """Non-fatal per-query failure that preserves batch partial success."""

    query: SearchQuery | None
    error: SearchError
    success: bool = field(default=False, init=False)


type SearchQueryResult = SearchQuerySuccess | SearchQueryFailure


@dataclass(frozen=True, slots=True)
class SearchCodebaseResult:
    """Ordered aggregate of independent workspace-searching outcomes."""

    results: tuple[SearchQueryResult, ...]

    def __post_init__(self) -> None:
        results = tuple(self.results)
        if not results:
            msg = "results must not be empty"
            raise ValueError(msg)
        if len(results) > DEFAULT_MAX_QUERIES_PER_CALL:
            msg = "results exceeds the safe batch bound"
            raise ValueError(msg)
        object.__setattr__(self, "results", results)


def _validate_pattern(value: str) -> None:
    _validate_text(value, field_name="pattern")
    if len(value) > MAX_SEARCH_PATTERN_CHARS:
        msg = "pattern exceeds the safe bound"
        raise ValueError(msg)
    if not value.strip():
        msg = "pattern must not be empty"
        raise ValueError(msg)


def _validate_workspace_scope(value: str) -> None:
    _validate_text(value, field_name="path")
    if len(value) > MAX_WORKSPACE_PATH_CHARS:
        msg = "path exceeds the safe bound"
        raise ValueError(msg)
    if value != "." and (value.startswith(("/", "\\")) or "\\" in value or ".." in value.split("/")):
        msg = "path must be workspace-relative and non-escaping"
        raise ValueError(msg)


def _validate_workspace_result_path(value: str) -> None:
    _validate_workspace_scope(value)
    if value == ".":
        msg = "match path must identify a workspace file"
        raise ValueError(msg)


def _validate_glob(value: str | None) -> None:
    if value is None:
        return
    _validate_text(value, field_name="glob")
    if len(value) > MAX_GLOB_CHARS:
        msg = "glob exceeds the safe bound"
        raise ValueError(msg)


def _validate_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        msg = f"{field_name} must be a string"
        raise TypeError(msg)
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if value != value.strip():
        msg = f"{field_name} must not contain leading or trailing whitespace"
        raise ValueError(msg)


def _validate_source_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        msg = f"{field_name} must be a string"
        raise TypeError(msg)


def _validate_one_based_integer(value: int, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        msg = f"{field_name} must be a one-based integer"
        raise ValueError(msg)


def _validate_boolean(value: object, *, field_name: str) -> None:
    if not isinstance(value, bool):
        msg = f"{field_name} must be a boolean"
        raise TypeError(msg)


__all__ = [
    "DEFAULT_CONTEXT_LINES",
    "DEFAULT_MAX_LINE_CHARS",
    "DEFAULT_MAX_OUTPUT_PER_QUERY",
    "DEFAULT_MAX_OUTPUT_PER_TOOL_CALL",
    "DEFAULT_MAX_PARALLEL_SEARCHES",
    "DEFAULT_MAX_QUERIES_PER_CALL",
    "DEFAULT_MAX_RESULTS_PER_QUERY",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_SEARCH_FILE_BYTES",
    "DEFAULT_PER_QUERY_TIMEOUT_SECONDS",
    "DEFAULT_TOOL_TIMEOUT_SECONDS",
    "SafeSearchMetadataValue",
    "SearchCodebaseCommand",
    "SearchCodebaseResult",
    "SearchContextLine",
    "SearchError",
    "SearchErrorCode",
    "SearchLimits",
    "SearchMatch",
    "SearchQuery",
    "SearchQueryFailure",
    "SearchQueryResult",
    "SearchQuerySuccess",
]
