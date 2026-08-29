"""Application orchestration for bounded workspace source searches."""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic

from fabrica.features.workspace_searching.application.dtos import (
    SearchCodebaseCommand,
    SearchCodebaseResult,
    SearchError,
    SearchErrorCode,
    SearchQuery,
    SearchQueryFailure,
    SearchQueryResult,
    SearchQuerySuccess,
)
from fabrica.features.workspace_searching.application.ports import (
    SearchCodebasePort,
    WorkspaceSearchBackend,
    WorkspaceSearchContext,
)
from fabrica.features.workspace_searching.application.result_limiting import limit_batch_results, limit_query_matches


@dataclass(frozen=True, slots=True)
class SearchCodebase(SearchCodebasePort):
    """Coordinate bounded, ordered, retry-aware workspace source searches."""

    backend: WorkspaceSearchBackend

    async def search(self, command: SearchCodebaseCommand, context: WorkspaceSearchContext) -> SearchCodebaseResult:
        """Search a batch while preserving input order and isolating query failures."""
        deadline = _deadline_monotonic(context)
        results: list[SearchQueryResult | None] = [None] * len(command.queries)
        queued = deque(enumerate(command.queries))
        active: dict[asyncio.Task[SearchQueryResult], tuple[int, SearchQuery]] = {}

        while active or queued:
            if context.cancellation.is_cancelled:
                _cancel_active(active)
                _fill_remaining(results, queued, SearchErrorCode.SEARCH_CANCELLED)
                await _collect_cancelled(active, results, SearchErrorCode.SEARCH_CANCELLED)
                break
            if monotonic() >= deadline:
                _cancel_active(active)
                _fill_remaining(results, queued, SearchErrorCode.SEARCH_TIMEOUT)
                await _collect_cancelled(active, results, SearchErrorCode.SEARCH_TIMEOUT)
                break

            while len(active) < context.limits.max_parallel_searches and queued:
                index, query = queued.popleft()
                task = asyncio.create_task(self._search_one(query, context, deadline))
                active[task] = (index, query)

            if not active:
                break
            timeout = min(0.01, max(0.0, deadline - monotonic()))
            done, _ = await asyncio.wait(active, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                index, query = active.pop(task)
                results[index] = _task_outcome(task, query)

        if any(result is None for result in results):
            msg = "search scheduler did not produce an outcome for every query"
            raise RuntimeError(msg)
        completed = tuple(result for result in results if result is not None)
        return limit_batch_results(completed, limits=context.limits)

    async def _search_one(
        self,
        query: SearchQuery,
        context: WorkspaceSearchContext,
        deadline: float,
    ) -> SearchQueryResult:
        """Execute one query with the remaining deadline budget and selective retry."""
        for attempt in range(context.limits.max_retries + 1):
            remaining = min(context.limits.per_query_timeout_seconds, deadline - monotonic())
            if remaining <= 0:
                return _failure(query, SearchErrorCode.SEARCH_TIMEOUT)
            try:
                outcome = await asyncio.wait_for(self.backend.search_query(query, context), timeout=remaining)
            except TimeoutError:
                outcome = _failure(query, SearchErrorCode.SEARCH_TIMEOUT)
            except asyncio.CancelledError:
                raise
            except OSError:
                outcome = _failure(query, SearchErrorCode.IO_ERROR, transient=True)
            normalized = _normalize_outcome(outcome, query, context)
            if not _is_retryable(normalized) or attempt == context.limits.max_retries:
                return normalized
        msg = "search retry loop exhausted unexpectedly"
        raise RuntimeError(msg)


def _deadline_monotonic(context: WorkspaceSearchContext) -> float:
    """Return the earliest host or configured tool deadline on the monotonic clock."""
    configured = monotonic() + context.limits.tool_timeout_seconds
    if context.deadline_at is None:
        return configured
    host_remaining = (context.deadline_at - datetime.now(UTC)).total_seconds()
    return min(configured, monotonic() + max(host_remaining, 0.0))


def _normalize_outcome(
    outcome: SearchQueryResult,
    query: SearchQuery,
    context: WorkspaceSearchContext,
) -> SearchQueryResult:
    """Apply query limits and bind unexpected query-less failures to their input."""
    if isinstance(outcome, SearchQuerySuccess):
        return limit_query_matches(
            query,
            outcome.matches,
            limits=context.limits,
            limit_reached=outcome.limit_reached,
        )
    if outcome.query is None:
        return SearchQueryFailure(query=query, error=outcome.error)
    return outcome


def _failure(query: SearchQuery, code: SearchErrorCode, *, transient: bool = False) -> SearchQueryFailure:
    """Create a safe scheduler-generated per-query failure."""
    metadata = {"transient": True} if transient else {}
    return SearchQueryFailure(query=query, error=SearchError(code=code, metadata=metadata))


def _is_retryable(outcome: SearchQueryResult) -> bool:
    """Allow retry only for an adapter-classified transient search failure."""
    return (
        isinstance(outcome, SearchQueryFailure)
        and outcome.error.code not in _DETERMINISTIC_ERROR_CODES
        and outcome.error.metadata.get("transient") is True
    )


def _task_outcome(task: asyncio.Task[SearchQueryResult], query: SearchQuery) -> SearchQueryResult:
    """Translate unexpected task cancellation into a stable query outcome."""
    if task.cancelled():
        return _failure(query, SearchErrorCode.SEARCH_CANCELLED)
    return task.result()


def _cancel_active(active: dict[asyncio.Task[SearchQueryResult], tuple[int, SearchQuery]]) -> None:
    """Request cancellation from every active query execution."""
    for task in active:
        task.cancel()


def _fill_remaining(
    results: list[SearchQueryResult | None],
    queued: deque[tuple[int, SearchQuery]],
    code: SearchErrorCode,
) -> None:
    """Fill queued query positions after a batch-wide stop condition."""
    for index, query in queued:
        results[index] = _failure(query, code)
    queued.clear()


async def _collect_cancelled(
    active: dict[asyncio.Task[SearchQueryResult], tuple[int, SearchQuery]],
    results: list[SearchQueryResult | None],
    code: SearchErrorCode,
) -> None:
    """Await active cleanup before returning stable stop-condition outcomes."""
    cancelled = tuple(active)
    await asyncio.gather(*cancelled, return_exceptions=True)
    for index, query in active.values():
        results[index] = _failure(query, code)


_DETERMINISTIC_ERROR_CODES = frozenset(
    {
        SearchErrorCode.EMPTY_PATTERN,
        SearchErrorCode.INVALID_PATH,
        SearchErrorCode.PATH_OUTSIDE_WORKSPACE,
        SearchErrorCode.INVALID_REGEX,
        SearchErrorCode.INVALID_GLOB,
    }
)
