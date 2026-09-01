"""Tests for the HTTPX public web-content attempt fetcher."""

import asyncio
import gzip
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx

from fabrica.features.web_content_fetching.adapters.outbound.httpx_fetcher import HttpxWebContentAttemptFetcher
from fabrica.features.web_content_fetching.application.dtos import (
    FetchAttemptFailure,
    FetchAttemptSuccess,
    FetchErrorCode,
    FetchWebContentLimits,
    FetchWebContentRequest,
)
from fabrica.features.web_content_fetching.application.ports import FetchWebContentContext

_SERVICE_UNAVAILABLE_STATUS = 503


@dataclass
class _Resolver:
    answers: tuple[str, ...] = ("8.8.8.8",)
    hostnames: list[str] = field(default_factory=list)

    async def resolve(self, hostname: str, context: FetchWebContentContext) -> tuple[str, ...]:
        _ = context
        self.hostnames.append(hostname)
        return self.answers


@dataclass
class _Cancellation:
    cancelled: bool = False

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled


class _ClosingStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...], cancellation: _Cancellation | None = None) -> None:
        self._chunks = chunks
        self._cancellation = cancellation
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for index, chunk in enumerate(self._chunks):
            if index == 1 and self._cancellation is not None:
                self._cancellation.cancelled = True
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


def test_fetch_attempt_streams_a_successful_get_with_host_headers_and_closes_resources() -> None:
    resolver = _Resolver()
    observed_request: httpx.Request | None = None
    stream = _ClosingStream((b"hello", b" world"))

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, headers={"content-type": "text/plain"}, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpxWebContentAttemptFetcher(
        resolver=resolver,
        client_factory=lambda: client,
        headers={"User-Agent": "FabricaAgent/1.0"},
    )

    result = asyncio.run(fetcher.fetch_attempt(FetchWebContentRequest("https://example.com/docs"), _context()))

    assert result == FetchAttemptSuccess(
        final_url="https://example.com/docs",
        status=200,
        content_type="text/plain",
        body=b"hello world",
    )
    assert observed_request is not None
    assert observed_request.method == "GET"
    assert observed_request.headers["user-agent"] == "FabricaAgent/1.0"
    assert resolver.hostnames == ["example.com"]
    assert stream.closed
    assert client.is_closed


def test_fetch_attempt_follows_relative_redirects_only_after_revalidating_each_destination() -> None:
    resolver = _Resolver()
    requested_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/final"})
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"done")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    fetcher = HttpxWebContentAttemptFetcher(resolver=resolver, client_factory=lambda: client)

    result = asyncio.run(fetcher.fetch_attempt(FetchWebContentRequest("https://example.com/start"), _context()))

    assert isinstance(result, FetchAttemptSuccess)
    assert result.final_url == "https://example.com/final"
    assert result.body == b"done"
    assert [(redirect.status, redirect.from_url, redirect.to_url) for redirect in result.redirects] == [
        (302, "https://example.com/start", "https://example.com/final")
    ]
    assert requested_urls == ["https://example.com/start", "https://example.com/final"]
    assert resolver.hostnames == ["example.com", "example.com"]


def test_fetch_attempt_rejects_insecure_redirect_without_requesting_its_destination() -> None:
    resolver = _Resolver()

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(301, headers={"location": "http://insecure.example/path"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpxWebContentAttemptFetcher(resolver=resolver, client_factory=lambda: client)

    result = asyncio.run(fetcher.fetch_attempt(FetchWebContentRequest("https://example.com/start"), _context()))

    _assert_failure(result, FetchErrorCode.INSECURE_REDIRECT)
    assert resolver.hostnames == ["example.com"]


def test_fetch_attempt_stops_and_closes_the_stream_when_body_exceeds_the_actual_limit() -> None:
    stream = _ClosingStream((b"abc", b"def"))

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, headers={"content-type": "text/plain", "content-length": "1"}, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpxWebContentAttemptFetcher(resolver=_Resolver(), client_factory=lambda: client)

    result = asyncio.run(
        fetcher.fetch_attempt(FetchWebContentRequest("https://example.com"), _context(max_response_bytes=5))
    )

    _assert_failure(result, FetchErrorCode.RESPONSE_TOO_LARGE)
    assert stream.closed
    assert client.is_closed


def test_fetch_attempt_rejects_an_oversized_content_length_before_consuming_the_stream() -> None:
    stream = _ClosingStream((b"body",))

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, headers={"content-length": "6"}, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpxWebContentAttemptFetcher(resolver=_Resolver(), client_factory=lambda: client)

    result = asyncio.run(
        fetcher.fetch_attempt(FetchWebContentRequest("https://example.com"), _context(max_response_bytes=5))
    )

    _assert_failure(result, FetchErrorCode.RESPONSE_TOO_LARGE)
    assert stream.closed


def test_fetch_attempt_enforces_the_decoded_size_limit_for_compressed_responses() -> None:
    compressed_body = gzip.compress(b"x" * 100)

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip", "content-length": str(len(compressed_body))},
            content=compressed_body,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpxWebContentAttemptFetcher(resolver=_Resolver(), client_factory=lambda: client)

    result = asyncio.run(
        fetcher.fetch_attempt(FetchWebContentRequest("https://example.com"), _context(max_response_bytes=50))
    )

    _assert_failure(result, FetchErrorCode.RESPONSE_TOO_LARGE)


def test_fetch_attempt_distinguishes_cancellation_during_body_consumption() -> None:
    cancellation = _Cancellation()
    stream = _ClosingStream((b"first", b"second"), cancellation)

    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, stream=stream)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpxWebContentAttemptFetcher(resolver=_Resolver(), client_factory=lambda: client)

    result = asyncio.run(
        fetcher.fetch_attempt(FetchWebContentRequest("https://example.com"), _context(cancellation=cancellation))
    )

    _assert_failure(result, FetchErrorCode.FETCH_CANCELLED)
    assert stream.closed


def test_fetch_attempt_returns_timeout_before_dns_when_the_host_deadline_has_expired() -> None:
    resolver = _Resolver()
    fetcher = HttpxWebContentAttemptFetcher(resolver=resolver)
    expired_context = _context(deadline_at=datetime.now(UTC) - timedelta(seconds=1))

    result = asyncio.run(fetcher.fetch_attempt(FetchWebContentRequest("https://example.com"), expired_context))

    _assert_failure(result, FetchErrorCode.FETCH_TIMEOUT)
    assert resolver.hostnames == []


def test_fetch_attempt_maps_http_errors_and_marks_transient_statuses_retryable() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(_SERVICE_UNAVAILABLE_STATUS)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpxWebContentAttemptFetcher(resolver=_Resolver(), client_factory=lambda: client)

    result = asyncio.run(fetcher.fetch_attempt(FetchWebContentRequest("https://example.com"), _context()))

    failure = _assert_failure(result, FetchErrorCode.HTTP_ERROR)
    assert failure.status == _SERVICE_UNAVAILABLE_STATUS
    assert failure.retryable


def _context(
    *,
    cancellation: _Cancellation | None = None,
    deadline_at: datetime | None = None,
    max_response_bytes: int = 5_000_000,
) -> FetchWebContentContext:
    return FetchWebContentContext(
        public_web_enabled=True,
        cancellation=cancellation if cancellation is not None else _Cancellation(),
        deadline_at=deadline_at,
        limits=FetchWebContentLimits(max_response_bytes=max_response_bytes),
    )


def _assert_failure(result: object, expected_code: FetchErrorCode) -> FetchAttemptFailure:
    assert isinstance(result, FetchAttemptFailure)
    assert result.error.code is expected_code
    return result
