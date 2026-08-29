"""Tests for bounded workspace-searching batch orchestration."""

import asyncio
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from time import monotonic

from fabrica.features.workspace_searching.application.dtos import (
    DEFAULT_MAX_RETRIES,
    SearchCodebaseCommand,
    SearchError,
    SearchErrorCode,
    SearchLimits,
    SearchMatch,
    SearchQuery,
    SearchQueryFailure,
    SearchQueryResult,
    SearchQuerySuccess,
)
from fabrica.features.workspace_searching.application.ports import WorkspaceSearchContext
from fabrica.features.workspace_searching.application.use_cases import SearchCodebase
from fabrica.features.workspace_searching.application.use_cases.search_codebase import _deadline_monotonic

MAXIMUM_PARALLEL_SEARCHES = 2


class MutableCancellation:
    """Test cancellation signal controlled by the backend fake."""

    def __init__(self) -> None:
        self.cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled


class DelayedBackend:
    """Fake backend that records concurrency and completes queries out of order."""

    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self.patterns: list[str] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def search_query(self, query: SearchQuery, context: WorkspaceSearchContext) -> SearchQuerySuccess:
        del context
        self.patterns.append(query.pattern)
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        if self.active == MAXIMUM_PARALLEL_SEARCHES:
            self.started.set()
        try:
            await self.release.wait()
            await asyncio.sleep(0 if query.pattern == "second" else 0.001)
            return _success(query)
        finally:
            self.active -= 1


class SequencedBackend:
    """Fake backend with scripted outcomes for each query pattern."""

    def __init__(self, outcomes: dict[str, tuple[SearchQueryResult | OSError, ...]]) -> None:
        self.outcomes = {pattern: deque(sequence) for pattern, sequence in outcomes.items()}
        self.calls: defaultdict[str, int] = defaultdict(int)

    async def search_query(self, query: SearchQuery, context: WorkspaceSearchContext) -> SearchQueryResult:
        del context
        self.calls[query.pattern] += 1
        outcome = self.outcomes[query.pattern].popleft()
        if isinstance(outcome, OSError):
            raise outcome
        return outcome


class CancellingBackend:
    """Fake backend that requests cancellation after the first admitted query."""

    def __init__(self, cancellation: MutableCancellation) -> None:
        self.cancellation = cancellation
        self.patterns: list[str] = []

    async def search_query(self, query: SearchQuery, context: WorkspaceSearchContext) -> SearchQuerySuccess:
        del context
        self.patterns.append(query.pattern)
        self.cancellation.cancelled = True
        return _success(query)


class BlockingBackend:
    """Fake backend that only exits when the scheduler cancels it."""

    def __init__(self) -> None:
        self.cancelled = False
        self.started = asyncio.Event()

    async def search_query(self, query: SearchQuery, context: WorkspaceSearchContext) -> SearchQuerySuccess:
        del query, context
        try:
            self.started.set()
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        msg = "blocking backend unexpectedly completed"
        raise AssertionError(msg)


class SelfCancellingBackend:
    """Fake backend that simulates unexpected backend task cancellation."""

    async def search_query(self, query: SearchQuery, context: WorkspaceSearchContext) -> SearchQuerySuccess:
        del query, context
        raise asyncio.CancelledError


def test_search_codebase_caps_concurrency_and_preserves_input_order() -> None:
    backend = DelayedBackend()
    queries = tuple(SearchQuery(pattern) for pattern in ("first", "second", "third"))

    async def search() -> tuple[SearchQueryResult, ...]:
        task = asyncio.create_task(
            SearchCodebase(backend).search(
                SearchCodebaseCommand(queries),
                _context(limits=SearchLimits(max_parallel_searches=MAXIMUM_PARALLEL_SEARCHES)),
            )
        )
        await backend.started.wait()
        assert backend.patterns == ["first", "second"]
        backend.release.set()
        return (await task).results

    results = asyncio.run(search())

    assert backend.maximum_active == MAXIMUM_PARALLEL_SEARCHES
    assert backend.patterns == ["first", "second", "third"]
    assert tuple(result.query.pattern for result in results if isinstance(result, SearchQuerySuccess)) == (
        "first",
        "second",
        "third",
    )


def test_search_codebase_preserves_mixed_outcomes_and_limits_success_matches() -> None:
    first = SearchQuery("first")
    second = SearchQuery("second")
    third = SearchQuery("third")
    backend = SequencedBackend(
        {
            "first": (SearchQuerySuccess(first, (_match("a.py"), _match("z.py"))),),
            "second": (SearchQueryFailure(second, SearchError(SearchErrorCode.INVALID_REGEX)),),
            "third": (SearchQuerySuccess(third, ()),),
        }
    )

    results = asyncio.run(
        SearchCodebase(backend).search(SearchCodebaseCommand((first, second, third)), _context())
    ).results

    assert isinstance(results[0], SearchQuerySuccess)
    assert tuple(match.path for match in results[0].matches) == ("a.py", "z.py")
    assert isinstance(results[1], SearchQueryFailure)
    assert results[1].error.code is SearchErrorCode.INVALID_REGEX
    assert isinstance(results[2], SearchQuerySuccess)


def test_search_codebase_suppresses_queued_work_after_cancellation() -> None:
    cancellation = MutableCancellation()
    backend = CancellingBackend(cancellation)
    queries = (SearchQuery("first"), SearchQuery("second"))

    results = asyncio.run(
        SearchCodebase(backend).search(
            SearchCodebaseCommand(queries),
            _context(cancellation=cancellation, limits=SearchLimits(max_parallel_searches=1)),
        )
    ).results

    assert backend.patterns == ["first"]
    assert isinstance(results[1], SearchQueryFailure)
    assert results[1].error.code is SearchErrorCode.SEARCH_CANCELLED


def test_search_codebase_cancels_active_work_and_suppresses_queue_after_deadline() -> None:
    backend = BlockingBackend()
    queries = (SearchQuery("first"), SearchQuery("second"))
    limits = SearchLimits(max_parallel_searches=1, per_query_timeout_seconds=0.01, tool_timeout_seconds=0.01)

    results = asyncio.run(
        SearchCodebase(backend).search(SearchCodebaseCommand(queries), _context(limits=limits))
    ).results

    assert backend.cancelled is True
    assert all(isinstance(result, SearchQueryFailure) for result in results)
    assert tuple(result.error.code for result in results if isinstance(result, SearchQueryFailure)) == (
        SearchErrorCode.SEARCH_TIMEOUT,
        SearchErrorCode.SEARCH_TIMEOUT,
    )


def test_search_codebase_applies_per_query_timeout_before_tool_deadline() -> None:
    backend = BlockingBackend()
    limits = SearchLimits(max_retries=0, per_query_timeout_seconds=0.01, tool_timeout_seconds=1.0)

    result = asyncio.run(
        SearchCodebase(backend).search(SearchCodebaseCommand((SearchQuery("blocked"),)), _context(limits=limits))
    ).results[0]

    assert backend.cancelled is True
    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.SEARCH_TIMEOUT


def test_search_codebase_cancels_active_work_when_host_cancels() -> None:
    cancellation = MutableCancellation()
    backend = BlockingBackend()
    queries = (SearchQuery("first"), SearchQuery("second"))

    async def search() -> tuple[SearchQueryResult, ...]:
        task = asyncio.create_task(
            SearchCodebase(backend).search(
                SearchCodebaseCommand(queries),
                _context(cancellation=cancellation, limits=SearchLimits(max_parallel_searches=1)),
            )
        )
        await backend.started.wait()
        cancellation.cancelled = True
        return (await task).results

    results = asyncio.run(search())

    assert backend.cancelled is True
    assert all(isinstance(result, SearchQueryFailure) for result in results)
    assert tuple(result.error.code for result in results if isinstance(result, SearchQueryFailure)) == (
        SearchErrorCode.SEARCH_CANCELLED,
        SearchErrorCode.SEARCH_CANCELLED,
    )


def test_search_codebase_translates_unexpected_backend_task_cancellation() -> None:
    result = asyncio.run(
        SearchCodebase(SelfCancellingBackend()).search(SearchCodebaseCommand((SearchQuery("cancelled"),)), _context())
    ).results[0]

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.SEARCH_CANCELLED


def test_search_codebase_binds_queryless_adapter_failure_to_its_input() -> None:
    query = SearchQuery("queryless")
    backend = SequencedBackend({"queryless": (SearchQueryFailure(None, SearchError(SearchErrorCode.INVALID_PATH)),)})

    result = asyncio.run(SearchCodebase(backend).search(SearchCodebaseCommand((query,)), _context())).results[0]

    assert isinstance(result, SearchQueryFailure)
    assert result.query == query
    assert result.error.code is SearchErrorCode.INVALID_PATH


def test_search_codebase_retries_only_adapter_classified_transient_failures() -> None:
    query = SearchQuery("retry")
    backend = SequencedBackend(
        {
            "retry": (
                SearchQueryFailure(query, SearchError(SearchErrorCode.IO_ERROR, metadata={"transient": True})),
                _success(query),
            )
        }
    )

    result = asyncio.run(SearchCodebase(backend).search(SearchCodebaseCommand((query,)), _context())).results[0]

    assert isinstance(result, SearchQuerySuccess)
    assert backend.calls["retry"] == DEFAULT_MAX_RETRIES + 1


def test_search_codebase_does_not_retry_deterministic_failures() -> None:
    query = SearchQuery("invalid")
    backend = SequencedBackend(
        {
            "invalid": (
                SearchQueryFailure(query, SearchError(SearchErrorCode.INVALID_REGEX, metadata={"transient": True})),
            )
        }
    )

    result = asyncio.run(SearchCodebase(backend).search(SearchCodebaseCommand((query,)), _context())).results[0]

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.INVALID_REGEX
    assert backend.calls["invalid"] == 1


def test_search_codebase_translates_backend_os_error_and_retries_once() -> None:
    query = SearchQuery("io-error")
    backend = SequencedBackend({"io-error": (OSError(), OSError())})

    result = asyncio.run(SearchCodebase(backend).search(SearchCodebaseCommand((query,)), _context())).results[0]

    assert isinstance(result, SearchQueryFailure)
    assert result.error.code is SearchErrorCode.IO_ERROR
    assert result.error.metadata == {"transient": True}
    assert backend.calls["io-error"] == DEFAULT_MAX_RETRIES + 1


def test_search_codebase_uses_expired_host_deadline_to_suppress_entire_queue() -> None:
    queries = (SearchQuery("first"), SearchQuery("second"))
    backend = SequencedBackend({query.pattern: (_success(query),) for query in queries})
    context = WorkspaceSearchContext(
        cancellation=MutableCancellation(),
        deadline_at=datetime.now(UTC) - timedelta(seconds=1),
        limits=SearchLimits(),
    )

    results = asyncio.run(SearchCodebase(backend).search(SearchCodebaseCommand(queries), context)).results

    assert all(isinstance(result, SearchQueryFailure) for result in results)
    assert tuple(result.error.code for result in results if isinstance(result, SearchQueryFailure)) == (
        SearchErrorCode.SEARCH_TIMEOUT,
        SearchErrorCode.SEARCH_TIMEOUT,
    )
    assert backend.calls == {}


def test_deadline_monotonic_uses_configured_limit_without_host_deadline() -> None:
    context = WorkspaceSearchContext(
        cancellation=MutableCancellation(),
        deadline_at=None,
        limits=SearchLimits(per_query_timeout_seconds=1.0, tool_timeout_seconds=1.0),
    )

    deadline = _deadline_monotonic(context)

    assert 0 < deadline - monotonic() <= context.limits.tool_timeout_seconds


def _context(
    *,
    cancellation: MutableCancellation | None = None,
    limits: SearchLimits | None = None,
) -> WorkspaceSearchContext:
    return WorkspaceSearchContext(
        cancellation=cancellation or MutableCancellation(),
        deadline_at=datetime.now(UTC) + timedelta(seconds=5),
        limits=limits or SearchLimits(),
    )


def _success(query: SearchQuery) -> SearchQuerySuccess:
    return SearchQuerySuccess(query=query, matches=())


def _match(path: str) -> SearchMatch:
    return SearchMatch(path=path, line=1, column=1, text="match", text_truncated=False)
