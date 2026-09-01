"""Tests for ordered, bounded public-web fetch orchestration."""

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import NoReturn

from fabrica.features.web_content_fetching.application.dtos import (
    FetchAttemptFailure,
    FetchAttemptSuccess,
    FetchContentFormat,
    FetchError,
    FetchErrorCode,
    FetchFailure,
    FetchSuccess,
    FetchWebContentCommand,
    FetchWebContentLimits,
    FetchWebContentRequest,
    ProcessedWebContent,
)
from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext
from fabrica.features.web_content_fetching.application.use_cases import FetchWebContent
from fabrica.features.web_content_fetching.application.use_cases.fetch_web_content import (
    _request_deadline,
    _wait_for_retry,
)

_CONCURRENCY_LIMIT = 2
_SUCCESS_STATUS = 200


@dataclass
class _Cancellation:
    cancelled: bool = False

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled


class _Fetcher:
    def __init__(self, outcomes: dict[str, tuple[FetchAttemptSuccess | FetchAttemptFailure, ...]]) -> None:
        self.outcomes = {url: deque(sequence) for url, sequence in outcomes.items()}
        self.calls: defaultdict[str, int] = defaultdict(int)

    async def fetch_attempt(
        self, request: FetchWebContentRequest, context: FetchWebContentContext
    ) -> FetchAttemptSuccess | FetchAttemptFailure:
        del context
        self.calls[request.url] += 1
        return self.outcomes[request.url].popleft()


class _BlockingFetcher:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def fetch_attempt(
        self, request: FetchWebContentRequest, context: FetchWebContentContext
    ) -> FetchAttemptSuccess:
        del context
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        if self.active == _CONCURRENCY_LIMIT:
            self.started.set()
        try:
            await self.release.wait()
            await asyncio.sleep(0 if request.url.endswith("second") else 0.001)
            return _attempt_success(request.url, request.url.rsplit("/", 1)[-1])
        finally:
            self.active -= 1


class _CancellingFetcher:
    def __init__(self, cancellation: _Cancellation) -> None:
        self.cancellation = cancellation
        self.calls: list[str] = []

    async def fetch_attempt(
        self, request: FetchWebContentRequest, context: FetchWebContentContext
    ) -> FetchAttemptSuccess:
        del context
        self.calls.append(request.url)
        self.cancellation.cancelled = True
        return _attempt_success(request.url, "first")


class _BlockingUntilCancelledFetcher:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def fetch_attempt(self, request: FetchWebContentRequest, context: FetchWebContentContext) -> NoReturn:
        del request, context
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        msg = "blocking fetcher unexpectedly completed"
        raise RuntimeError(msg)


class _Processor:
    def process(
        self, body: bytes, *, content_type: str, final_url: str, max_chars: int
    ) -> ProcessedWebContent | FetchError:
        del content_type, final_url
        content = body.decode()[:max_chars]
        return ProcessedWebContent(
            media_type="text/plain",
            content_format=FetchContentFormat.TEXT,
            content=content,
            content_chars=len(body.decode()),
            returned_chars=len(content),
            truncated=len(content) < len(body.decode()),
        )


class _FailingProcessor:
    def process(
        self, body: bytes, *, content_type: str, final_url: str, max_chars: int
    ) -> ProcessedWebContent | FetchError:
        del body, content_type, final_url, max_chars
        return FetchError(FetchErrorCode.UNSUPPORTED_CONTENT_TYPE)


def test_fetch_caps_concurrency_and_preserves_input_order() -> None:
    fetcher = _BlockingFetcher()
    command = _command("first", "second", "third")

    async def run() -> tuple[FetchSuccess | FetchFailure, ...]:
        task = asyncio.create_task(
            FetchWebContent(fetcher, _Processor()).fetch(command, _context(max_parallel_fetches=_CONCURRENCY_LIMIT))
        )
        await fetcher.started.wait()
        assert fetcher.maximum_active == _CONCURRENCY_LIMIT
        fetcher.release.set()
        return (await task).results

    results = asyncio.run(run())

    assert [result.requested_url.rsplit("/", 1)[-1] for result in results] == ["first", "second", "third"]
    assert fetcher.maximum_active == _CONCURRENCY_LIMIT


def test_fetch_isolates_failures_and_retries_only_typed_transient_outcomes() -> None:
    retry_url = "https://example.com/retry"
    failed_url = "https://example.com/failed"
    fetcher = _Fetcher(
        {
            retry_url: (
                FetchAttemptFailure(FetchError(FetchErrorCode.CONNECTION_FAILED), retryable=True),
                _attempt_success(retry_url, "recovered"),
            ),
            failed_url: (FetchAttemptFailure(FetchError(FetchErrorCode.INVALID_URL), retryable=True),),
        }
    )

    results = asyncio.run(FetchWebContent(fetcher, _Processor()).fetch(_command("retry", "failed"), _context())).results

    assert isinstance(results[0], FetchSuccess)
    assert isinstance(results[1], FetchFailure)
    assert results[1].error.code is FetchErrorCode.INVALID_URL
    assert fetcher.calls == {retry_url: 2, failed_url: 1}


def test_fetch_returns_disabled_failures_without_calling_the_attempt_fetcher() -> None:
    fetcher = _Fetcher({})
    context = _context(public_web_enabled=False)

    results = asyncio.run(FetchWebContent(fetcher, _Processor()).fetch(_command("first", "second"), context)).results

    assert all(isinstance(result, FetchFailure) for result in results)
    assert [result.error.code for result in results if isinstance(result, FetchFailure)] == [
        FetchErrorCode.PUBLIC_WEB_DISABLED,
        FetchErrorCode.PUBLIC_WEB_DISABLED,
    ]
    assert fetcher.calls == {}


def test_fetch_returns_timeout_without_starting_work_after_host_deadline_expires() -> None:
    fetcher = _Fetcher({"https://example.com/first": (_attempt_success("https://example.com/first", "first"),)})
    context = _context(deadline_at=datetime.now(UTC) - timedelta(seconds=1))

    result = asyncio.run(FetchWebContent(fetcher, _Processor()).fetch(_command("first"), context)).results[0]

    assert isinstance(result, FetchFailure)
    assert result.error.code is FetchErrorCode.FETCH_TIMEOUT
    assert fetcher.calls == {}


def test_fetch_marks_queued_work_cancelled_after_host_cancellation() -> None:
    cancellation = _Cancellation()
    fetcher = _CancellingFetcher(cancellation)
    context = FetchWebContentContext(
        public_web_enabled=True,
        cancellation=cancellation,
        deadline_at=datetime.now(UTC) + timedelta(seconds=5),
        limits=FetchWebContentLimits(max_parallel_fetches=1),
    )

    results = asyncio.run(FetchWebContent(fetcher, _Processor()).fetch(_command("first", "second"), context)).results

    assert isinstance(results[0], FetchSuccess)
    assert isinstance(results[1], FetchFailure)
    assert results[1].error.code is FetchErrorCode.FETCH_CANCELLED
    assert fetcher.calls == ["https://example.com/first"]


def test_fetch_returns_processor_failure_with_transport_metadata() -> None:
    request = FetchWebContentRequest("https://example.com/content")
    fetcher = _Fetcher({request.url: (_attempt_success(request.url, "content"),)})

    result = asyncio.run(
        FetchWebContent(fetcher, _FailingProcessor()).fetch(FetchWebContentCommand((request,)), _context())
    ).results[0]

    assert isinstance(result, FetchFailure)
    assert result.error.code is FetchErrorCode.UNSUPPORTED_CONTENT_TYPE
    assert result.final_url == request.url
    assert result.status == _SUCCESS_STATUS


def test_fetch_cancels_active_work_when_host_cancellation_arrives() -> None:
    fetcher = _BlockingUntilCancelledFetcher()
    cancellation = _Cancellation()
    context = FetchWebContentContext(
        public_web_enabled=True,
        cancellation=cancellation,
        deadline_at=datetime.now(UTC) + timedelta(seconds=5),
        limits=FetchWebContentLimits(max_parallel_fetches=1),
    )

    async def run() -> FetchFailure:
        task = asyncio.create_task(FetchWebContent(fetcher, _Processor()).fetch(_command("first"), context))
        await fetcher.started.wait()
        cancellation.cancelled = True
        result = (await task).results[0]
        assert isinstance(result, FetchFailure)
        return result

    result = asyncio.run(run())

    assert result.error.code is FetchErrorCode.FETCH_CANCELLED
    assert fetcher.cancelled


def test_fetch_returns_timeout_when_attempt_exceeds_request_deadline() -> None:
    fetcher = _BlockingUntilCancelledFetcher()
    context = _context_with_limits(per_request_timeout_seconds=0.001)

    result = asyncio.run(FetchWebContent(fetcher, _Processor()).fetch(_command("first"), context)).results[0]

    assert isinstance(result, FetchFailure)
    assert result.error.code is FetchErrorCode.FETCH_TIMEOUT
    assert fetcher.cancelled


def test_retry_wait_stops_when_cancellation_is_requested() -> None:
    cancellation = _Cancellation(cancelled=True)
    context = FetchWebContentContext(
        public_web_enabled=True,
        cancellation=cancellation,
        deadline_at=None,
        limits=FetchWebContentLimits(),
    )

    assert not asyncio.run(_wait_for_retry(1.0, context, float("inf")))


def test_request_deadline_uses_per_request_timeout_without_a_host_deadline() -> None:
    context = FetchWebContentContext(
        public_web_enabled=True,
        cancellation=_Cancellation(),
        deadline_at=None,
        limits=FetchWebContentLimits(per_request_timeout_seconds=1.0),
    )

    deadline = _request_deadline(context)

    assert 0 < deadline - monotonic() <= context.limits.per_request_timeout_seconds


def _attempt_success(url: str, content: str) -> FetchAttemptSuccess:
    return FetchAttemptSuccess(final_url=url, status=_SUCCESS_STATUS, content_type="text/plain", body=content.encode())


def _command(*names: str) -> FetchWebContentCommand:
    return FetchWebContentCommand(tuple(FetchWebContentRequest(f"https://example.com/{name}") for name in names))


def _context(
    *,
    max_parallel_fetches: int = 4,
    public_web_enabled: bool = True,
    deadline_at: datetime | None = None,
) -> FetchWebContentContext:
    return FetchWebContentContext(
        public_web_enabled=public_web_enabled,
        cancellation=_Cancellation(),
        deadline_at=deadline_at or datetime.now(UTC) + timedelta(seconds=5),
        limits=FetchWebContentLimits(max_parallel_fetches=max_parallel_fetches),
    )


def _context_with_limits(*, per_request_timeout_seconds: float) -> FetchWebContentContext:
    return FetchWebContentContext(
        public_web_enabled=True,
        cancellation=_Cancellation(),
        deadline_at=datetime.now(UTC) + timedelta(seconds=5),
        limits=FetchWebContentLimits(per_request_timeout_seconds=per_request_timeout_seconds),
    )
