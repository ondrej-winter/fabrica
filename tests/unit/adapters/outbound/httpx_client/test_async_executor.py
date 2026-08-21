"""Tests for the asynchronous HTTPX retry executor."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from fabrica.adapters.outbound.httpx_client import (
    AsyncHttpxRetryExecutor,
    HttpTimeout,
    HttpxRetryError,
    HttpxRetryRequest,
    RetryPolicy,
)

SUCCESS_STATUS = 200
RETRYABLE_STATUS = 503
EXPECTED_ATTEMPT_COUNT = 2
EXPECTED_RETRY_COUNT = 1
EXPECTED_FIRST_JITTERED_DELAY = 0.25
SYNTHETIC_ERROR_MESSAGE = "synthetic secret url"


class AsyncMonotonicClock:
    """Deterministic monotonic clock and async sleep recorder for retry tests."""

    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.current

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.current += delay


def test_retries_transport_error_then_returns_success() -> None:
    clock = AsyncMonotonicClock()
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError(SYNTHETIC_ERROR_MESSAGE, request=request)
        return httpx.Response(SUCCESS_STATUS, json={"ok": True})

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            outcome = await _executor(clock).request(
                client=client,
                request=HttpxRetryRequest(
                    method="GET",
                    url="https://example.invalid/resource",
                    policy=RetryPolicy(total_budget_seconds=10.0),
                ),
            )

        assert outcome.response.status_code == SUCCESS_STATUS
        assert outcome.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT
        assert outcome.diagnostics.retry_count == EXPECTED_RETRY_COUNT
        assert outcome.diagnostics.last_retry_reason == "exception"
        assert outcome.diagnostics.last_error_type == "ConnectError"

    asyncio.run(execute())

    assert calls == EXPECTED_ATTEMPT_COUNT
    assert clock.sleeps == [EXPECTED_FIRST_JITTERED_DELAY]


def test_preserves_zero_retry_after_without_falling_back_to_jitter() -> None:
    clock = AsyncMonotonicClock()
    responses = iter(
        (
            httpx.Response(RETRYABLE_STATUS, headers={"Retry-After": "0"}),
            httpx.Response(SUCCESS_STATUS, json={"ok": True}),
        )
    )

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: next(responses))) as client:
            outcome = await _executor(clock).request(
                client=client,
                request=HttpxRetryRequest(
                    method="GET",
                    url="https://example.invalid/resource",
                    policy=RetryPolicy(total_budget_seconds=40.0),
                ),
            )

        assert outcome.response.status_code == SUCCESS_STATUS

    asyncio.run(execute())

    assert clock.sleeps == []


def test_bounds_per_attempt_timeout_to_remaining_retry_budget() -> None:
    clock = AsyncMonotonicClock()
    observed_timeouts: list[httpx.Timeout] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        timeout = request.extensions["timeout"]
        observed_timeouts.append(httpx.Timeout(**timeout))
        clock.current += 9.5
        return httpx.Response(RETRYABLE_STATUS)

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            outcome = await _executor(clock).request(
                client=client,
                request=HttpxRetryRequest(
                    method="GET",
                    url="https://example.invalid/resource",
                    policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0.0, total_budget_seconds=10.0),
                    timeout=HttpTimeout(connect_seconds=10.0, read_seconds=10.0, write_seconds=10.0, pool_seconds=10.0),
                ),
            )

        assert outcome.response.status_code == RETRYABLE_STATUS
        assert outcome.diagnostics.budget_exhausted is True

    asyncio.run(execute())

    assert [timeout.read for timeout in observed_timeouts] == [10.0, 0.5]


def test_raises_retry_error_with_diagnostics_after_exhausting_transport_errors() -> None:
    clock = AsyncMonotonicClock()

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(SYNTHETIC_ERROR_MESSAGE, request=request)

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpxRetryError) as error_info:
                await _executor(clock).request(
                    client=client,
                    request=HttpxRetryRequest(
                        method="GET",
                        url="https://example.invalid/resource",
                        policy=RetryPolicy(max_attempts=2, total_budget_seconds=10.0),
                    ),
                )

        error = error_info.value
        assert error.error_type == "ConnectError"
        assert error.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT
        assert error.diagnostics.retry_count == EXPECTED_RETRY_COUNT
        assert error.diagnostics.last_retry_reason == "exception"
        assert error.diagnostics.last_error_type == "ConnectError"

    asyncio.run(execute())


def _executor(clock: AsyncMonotonicClock) -> AsyncHttpxRetryExecutor:
    return AsyncHttpxRetryExecutor(monotonic=clock.monotonic, sleep=clock.sleep, random=_fixed_random)


def _fixed_random() -> float:
    return 0.5
