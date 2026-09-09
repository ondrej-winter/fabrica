"""Tests for the async HTTPX retry client lifecycle wrapper."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
import pytest

from fabrica.adapters.outbound.httpx_client import (
    AsyncHttpxRetryClient,
    HttpTimeout,
    HttpxRetryError,
    HttpxRetryRequest,
    RetryPolicy,
)

SUCCESS_STATUS = 200
RETRYABLE_STATUS = 429
UNRETRYABLE_STATUS = 418
EXPECTED_ATTEMPT_COUNT = 2
EXPECTED_RETRY_COUNT = 1
SAME_TIMEOUT_SECONDS = 1.5
SYNTHETIC_READ_FAILURE_MESSAGE = "synthetic read failure"
SYNTHETIC_CONNECTION_FAILURE_MESSAGE = "synthetic connection failure"

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator


class _FailingStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"partial"
        raise httpx.ReadError(SYNTHETIC_READ_FAILURE_MESSAGE)

    async def aclose(self) -> None:
        return None


def test_same_timeout_applies_one_value_to_all_http_phases() -> None:
    timeout = HttpTimeout.same(SAME_TIMEOUT_SECONDS)

    assert timeout.connect_seconds == SAME_TIMEOUT_SECONDS
    assert timeout.read_seconds == SAME_TIMEOUT_SECONDS
    assert timeout.write_seconds == SAME_TIMEOUT_SECONDS
    assert timeout.pool_seconds == SAME_TIMEOUT_SECONDS


def test_uses_async_client_factory_and_closes_client_after_request() -> None:
    observed_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(SUCCESS_STATUS, json={"ok": True})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(method="GET", url="https://example.invalid/resource", policy=RetryPolicy())

    result = asyncio.run(retry_client.request(request))

    assert result.response.status_code == SUCCESS_STATUS
    assert observed_request is not None
    assert str(observed_request.url) == request.url
    assert http_client.is_closed


def test_stream_delivers_body_to_consumer_and_closes_client() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(SUCCESS_STATUS, content=b"streamed-body")

    async def consume(body: AsyncIterable[bytes]) -> str:
        return b"".join([chunk async for chunk in body]).decode()

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(method="GET", url="https://example.invalid/resource", policy=RetryPolicy())

    result = asyncio.run(retry_client.stream(request, consume))

    assert result.response.status_code == SUCCESS_STATUS
    assert result.response.text == "streamed-body"
    assert http_client.is_closed


def test_stream_retries_retryable_status_before_consuming_a_body() -> None:
    calls = 0
    consumed_status_codes: list[int] = []

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(RETRYABLE_STATUS, headers={"Retry-After": ""})
        return httpx.Response(SUCCESS_STATUS, content=b"streamed-body")

    async def consume(body: AsyncIterable[bytes]) -> str:
        consumed_status_codes.append(calls)
        return b"".join([chunk async for chunk in body]).decode()

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(
        method="POST",
        url="https://example.invalid/resource",
        policy=RetryPolicy(max_attempts=EXPECTED_ATTEMPT_COUNT, initial_delay_seconds=0.0),
        replay_safe=True,
    )

    result = asyncio.run(retry_client.stream(request, consume))

    assert result.response.status_code == SUCCESS_STATUS
    assert result.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT
    assert result.diagnostics.retry_count == EXPECTED_RETRY_COUNT
    assert calls == EXPECTED_ATTEMPT_COUNT
    assert consumed_status_codes == [EXPECTED_ATTEMPT_COUNT]
    assert http_client.is_closed


def test_stream_retries_connection_failure_before_opening_a_body() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError(SYNTHETIC_CONNECTION_FAILURE_MESSAGE, request=request)
        return httpx.Response(SUCCESS_STATUS, content=b"streamed-body")

    async def consume(body: AsyncIterable[bytes]) -> str:
        return b"".join([chunk async for chunk in body]).decode()

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(
        method="POST",
        url="https://example.invalid/resource",
        policy=RetryPolicy(max_attempts=EXPECTED_ATTEMPT_COUNT, initial_delay_seconds=0.0),
        replay_safe=True,
    )

    result = asyncio.run(retry_client.stream(request, consume))

    assert result.response.status_code == SUCCESS_STATUS
    assert result.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT
    assert result.diagnostics.retry_count == EXPECTED_RETRY_COUNT
    assert result.diagnostics.last_retry_reason == "exception"
    assert result.diagnostics.last_error_type == "ConnectError"
    assert calls == EXPECTED_ATTEMPT_COUNT
    assert http_client.is_closed


def test_stream_wraps_non_retryable_connection_failure_without_opening_a_body() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(SYNTHETIC_CONNECTION_FAILURE_MESSAGE, request=request)

    async def consume(body: AsyncIterable[bytes]) -> str:
        return b"".join([chunk async for chunk in body]).decode()

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(
        method="GET",
        url="https://example.invalid/resource",
        policy=RetryPolicy(retryable_exception_types=()),
        replay_safe=True,
    )

    with pytest.raises(HttpxRetryError) as error_info:
        asyncio.run(retry_client.stream(request, consume))

    assert error_info.value.error_type == "ConnectError"
    assert error_info.value.diagnostics.attempt_count == EXPECTED_RETRY_COUNT
    assert calls == EXPECTED_RETRY_COUNT
    assert http_client.is_closed


def test_stream_stops_after_retryable_connection_failure_exhausts_attempts() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(SYNTHETIC_CONNECTION_FAILURE_MESSAGE, request=request)

    async def consume(body: AsyncIterable[bytes]) -> str:
        return b"".join([chunk async for chunk in body]).decode()

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(
        method="GET",
        url="https://example.invalid/resource",
        policy=RetryPolicy(max_attempts=EXPECTED_RETRY_COUNT),
        replay_safe=True,
    )

    with pytest.raises(HttpxRetryError) as error_info:
        asyncio.run(retry_client.stream(request, consume))

    assert error_info.value.error_type == "ConnectError"
    assert error_info.value.diagnostics.attempt_count == EXPECTED_RETRY_COUNT
    assert calls == EXPECTED_RETRY_COUNT
    assert http_client.is_closed


def test_stream_consumes_final_retryable_response_without_another_replay() -> None:
    calls = 0
    consumed_status_codes: list[int] = []

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(RETRYABLE_STATUS, content=b"rate-limited")

    async def consume(body: AsyncIterable[bytes]) -> str:
        consumed_status_codes.append(calls)
        return b"".join([chunk async for chunk in body]).decode()

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(
        method="GET",
        url="https://example.invalid/resource",
        policy=RetryPolicy(max_attempts=EXPECTED_ATTEMPT_COUNT, initial_delay_seconds=0.0),
        replay_safe=True,
    )

    result = asyncio.run(retry_client.stream(request, consume))

    assert result.response.status_code == RETRYABLE_STATUS
    assert result.response.text == "rate-limited"
    assert result.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT
    assert result.diagnostics.retry_count == EXPECTED_RETRY_COUNT
    assert result.diagnostics.last_retry_reason == "http_status"
    assert calls == EXPECTED_ATTEMPT_COUNT
    assert consumed_status_codes == [EXPECTED_ATTEMPT_COUNT]
    assert http_client.is_closed


def test_stream_consumes_unretryable_response_once() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(UNRETRYABLE_STATUS, content=b"backend failure")

    async def consume(body: AsyncIterable[bytes]) -> str:
        return b"".join([chunk async for chunk in body]).decode()

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(
        method="GET",
        url="https://example.invalid/resource",
        policy=RetryPolicy(max_attempts=EXPECTED_ATTEMPT_COUNT, initial_delay_seconds=0.0),
        replay_safe=True,
    )

    result = asyncio.run(retry_client.stream(request, consume))

    assert result.response.status_code == UNRETRYABLE_STATUS
    assert result.response.text == "backend failure"
    assert result.diagnostics.attempt_count == 1
    assert result.diagnostics.retry_count == 0
    assert calls == 1
    assert http_client.is_closed


def test_stream_closes_client_when_body_read_fails_without_replaying_request() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(SUCCESS_STATUS, stream=_FailingStream())

    async def consume(body: AsyncIterable[bytes]) -> str:
        return b"".join([chunk async for chunk in body]).decode()

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(
        method="GET",
        url="https://example.invalid/resource",
        policy=RetryPolicy(retryable_exception_types=(httpx.ReadError,)),
        replay_safe=True,
    )

    with pytest.raises(httpx.ReadError):
        asyncio.run(retry_client.stream(request, consume))

    assert calls == 1
    assert http_client.is_closed


def test_stream_propagates_cancellation_and_closes_client() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(SUCCESS_STATUS, content=b"streamed-body")

    async def consume(body: AsyncIterable[bytes]) -> str:
        async for _ in body:
            break
        raise asyncio.CancelledError

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    retry_client = AsyncHttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(method="GET", url="https://example.invalid/resource", policy=RetryPolicy())

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(retry_client.stream(request, consume))

    assert http_client.is_closed
