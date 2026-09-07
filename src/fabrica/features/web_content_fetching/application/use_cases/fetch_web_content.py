"""Application orchestration for bounded, ordered public-web fetch batches."""

import asyncio
from collections import deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import cast

from fabrica.features.web_content_fetching.application.dtos import (
    FetchAttemptFailure,
    FetchAttemptSuccess,
    FetchError,
    FetchErrorCode,
    FetchFailure,
    FetchResult,
    FetchSuccess,
    FetchWebContentCommand,
    FetchWebContentRequest,
    FetchWebContentResult,
)
from fabrica.features.web_content_fetching.application.ports import (
    FetchWebContentContext,
    FetchWebContentPort,
    WebContentAttemptFetcher,
    WebContentProcessor,
)
from fabrica.features.web_content_fetching.application.result_limiting import limit_batch_content


@dataclass(frozen=True, slots=True)
class FetchWebContent(FetchWebContentPort):
    """Coordinate bounded, retry-aware fetch attempts and content normalization."""

    attempt_fetcher: WebContentAttemptFetcher
    processor: WebContentProcessor

    async def fetch(self, command: FetchWebContentCommand, context: FetchWebContentContext) -> FetchWebContentResult:
        """Fetch all input requests in order while isolating individual failures."""
        if not context.public_web_enabled:
            return limit_batch_content(
                tuple(_failure(request, FetchErrorCode.PUBLIC_WEB_DISABLED) for request in command.requests),
                max_content_chars=context.limits.max_batch_content_chars,
            )

        results: list[FetchResult | None] = [None] * len(command.requests)
        queued = deque(enumerate(command.requests))
        active: dict[asyncio.Task[FetchResult], tuple[int, FetchWebContentRequest]] = {}
        while active or queued:
            if context.cancellation.is_cancelled:
                _cancel_active(active)
                _fill_remaining(results, queued, FetchErrorCode.FETCH_CANCELLED)
                await _collect_cancelled(active, results, FetchErrorCode.FETCH_CANCELLED)
                break
            while len(active) < context.limits.max_parallel_fetches and queued:
                index, request = queued.popleft()
                active[asyncio.create_task(self._fetch_one(request, context))] = (index, request)
            if not active:  # pragma: no cover - positive configured concurrency schedules every queued valid request.
                break
            done, _ = await asyncio.wait(active, timeout=0.01, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                index, request = active.pop(task)
                results[index] = _task_outcome(task, request)

        if any(
            result is None for result in results
        ):  # pragma: no cover - scheduler fills one outcome for every request.
            msg = "fetch scheduler did not produce an outcome for every request"
            raise RuntimeError(msg)
        return limit_batch_content(
            tuple(cast("FetchResult", result) for result in results),
            max_content_chars=context.limits.max_batch_content_chars,
        )

    async def _fetch_one(self, request: FetchWebContentRequest, context: FetchWebContentContext) -> FetchResult:
        """Execute one request within its deadline and selective retry budget."""
        deadline = _request_deadline(context)
        for attempt in range(context.limits.max_retries + 1):
            if context.cancellation.is_cancelled:
                return _failure(request, FetchErrorCode.FETCH_CANCELLED)
            remaining = deadline - monotonic()
            if remaining <= 0:
                return _failure(request, FetchErrorCode.FETCH_TIMEOUT)
            attempt_context = replace(context, deadline_at=datetime.now(UTC) + timedelta(seconds=remaining))
            try:
                outcome = await asyncio.wait_for(
                    self.attempt_fetcher.fetch_attempt(request, attempt_context),
                    timeout=remaining,
                )
            except TimeoutError:
                return _failure(request, FetchErrorCode.FETCH_TIMEOUT)
            except asyncio.CancelledError:
                raise
            result = self._normalize_outcome(request, outcome, context)
            if not _is_retryable(outcome) or attempt == context.limits.max_retries:
                return result
            failure = cast("FetchAttemptFailure", outcome)
            if not await _wait_for_retry(failure.retry_after_seconds or 0.0, context, deadline):
                code = (
                    FetchErrorCode.FETCH_CANCELLED
                    if context.cancellation.is_cancelled
                    else FetchErrorCode.FETCH_TIMEOUT
                )
                return _failure(request, code)
        # Each bounded retry iteration returns before exhaustion.
        msg = "fetch retry loop exhausted unexpectedly"  # pragma: no cover
        raise RuntimeError(msg)  # pragma: no cover

    def _normalize_outcome(
        self,
        request: FetchWebContentRequest,
        outcome: FetchAttemptSuccess | FetchAttemptFailure,
        context: FetchWebContentContext,
    ) -> FetchResult:
        """Convert a transport attempt outcome to its public application result."""
        if isinstance(outcome, FetchAttemptFailure):
            return FetchFailure(request.url, outcome.error, outcome.final_url, outcome.status, outcome.redirects)
        processed = self.processor.process(
            outcome.body,
            content_type=outcome.content_type,
            final_url=outcome.final_url,
            max_chars=request.max_chars or context.limits.max_content_chars_per_request,
        )
        if isinstance(processed, FetchError):
            return FetchFailure(request.url, processed, outcome.final_url, outcome.status, outcome.redirects)
        normalized = processed
        return FetchSuccess(
            requested_url=request.url,
            final_url=outcome.final_url,
            status=outcome.status,
            content_type=outcome.content_type,
            media_type=normalized.media_type,
            size_bytes=len(outcome.body),
            content_format=normalized.content_format,
            content=normalized.content,
            content_chars=len(normalized.content),
            returned_chars=len(normalized.content),
            truncated=normalized.truncated,
            redirects=outcome.redirects,
        )


def _request_deadline(context: FetchWebContentContext) -> float:
    """Return the earliest host and per-request deadline on a monotonic clock."""
    deadline = monotonic() + context.limits.per_request_timeout_seconds
    if context.deadline_at is None:
        return deadline
    host_remaining = (context.deadline_at - datetime.now(UTC)).total_seconds()
    return min(deadline, monotonic() + max(host_remaining, 0.0))


async def _wait_for_retry(delay: float, context: FetchWebContentContext, deadline: float) -> bool:
    """Wait for an adapter-provided retry delay without ignoring cancellation or deadlines."""
    if delay <= 0:
        return not context.cancellation.is_cancelled and monotonic() < deadline
    end = monotonic() + delay
    while monotonic() < end:
        if context.cancellation.is_cancelled or monotonic() >= deadline:
            return False
        await asyncio.sleep(min(0.01, end - monotonic(), deadline - monotonic()))
    return not context.cancellation.is_cancelled and monotonic() < deadline


def _failure(request: FetchWebContentRequest, code: FetchErrorCode) -> FetchFailure:
    return FetchFailure(request.url, FetchError(code))


def _is_retryable(outcome: FetchAttemptSuccess | FetchAttemptFailure) -> bool:
    """Allow retries only for accepted adapter-classified transient failures."""
    return (
        isinstance(outcome, FetchAttemptFailure)
        and outcome.retryable
        and outcome.error.code
        in {
            FetchErrorCode.DNS_FAILED,
            FetchErrorCode.CONNECTION_FAILED,
            FetchErrorCode.HTTP_ERROR,
        }
    )


def _task_outcome(task: asyncio.Task[FetchResult], request: FetchWebContentRequest) -> FetchResult:
    if task.cancelled():
        return _failure(request, FetchErrorCode.FETCH_CANCELLED)
    return task.result()


def _cancel_active(active: dict[asyncio.Task[FetchResult], tuple[int, FetchWebContentRequest]]) -> None:
    for task in active:
        task.cancel()


def _fill_remaining(
    results: list[FetchResult | None],
    queued: deque[tuple[int, FetchWebContentRequest]],
    code: FetchErrorCode,
) -> None:
    for index, request in queued:
        results[index] = _failure(request, code)
    queued.clear()


async def _collect_cancelled(
    active: dict[asyncio.Task[FetchResult], tuple[int, FetchWebContentRequest]],
    results: list[FetchResult | None],
    code: FetchErrorCode,
) -> None:
    await asyncio.gather(*active, return_exceptions=True)
    for index, request in active.values():
        results[index] = _failure(request, code)


__all__ = ["FetchWebContent"]
