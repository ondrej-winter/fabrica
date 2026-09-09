"""Tests for the asynchronous HTTPX retry executor."""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx
import pytest

from fabrica.adapters.outbound.httpx_client import (
    AsyncHttpxRetryExecutor,
    HttpTimeout,
    HttpxRetryError,
    HttpxRetryRequest,
    RetryPolicy,
    retry_support,
)

SUCCESS_STATUS = 200
RETRYABLE_STATUS = 503
EXPECTED_ATTEMPT_COUNT = 2
EXPECTED_RETRY_COUNT = 1
EXPECTED_FIRST_JITTERED_DELAY = 0.25
SYNTHETIC_ERROR_MESSAGE = "synthetic secret url"
REMAINING_BUDGET_SECONDS = 2.0
EXPECTED_SECOND_JITTERED_DELAY = 0.5


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


def test_does_not_retry_retryable_status_without_replay_authorization() -> None:
    clock = AsyncMonotonicClock()
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(RETRYABLE_STATUS)

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            outcome = await _executor(clock).request(
                client=client,
                request=HttpxRetryRequest(
                    method="POST",
                    url="https://example.invalid/resource",
                    policy=RetryPolicy(total_budget_seconds=10.0),
                ),
            )

        assert outcome.response.status_code == RETRYABLE_STATUS
        assert outcome.diagnostics.attempt_count == 1
        assert outcome.diagnostics.retry_count == 0

    asyncio.run(execute())

    assert calls == 1
    assert clock.sleeps == []


def test_stream_does_not_retry_retryable_exception_without_replay_authorization() -> None:
    clock = AsyncMonotonicClock()
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(SYNTHETIC_ERROR_MESSAGE, request=request)

    async def consume(_body) -> str:
        pytest.fail("must not consume")

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpxRetryError) as error_info:
                await _executor(clock).stream(
                    client=client,
                    request=HttpxRetryRequest(
                        method="POST",
                        url="https://example.invalid/resource",
                        policy=RetryPolicy(total_budget_seconds=10.0),
                    ),
                    body_consumer=consume,
                )

        assert error_info.value.diagnostics.attempt_count == 1
        assert error_info.value.diagnostics.retry_count == 0

    asyncio.run(execute())

    assert calls == 1
    assert clock.sleeps == []


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
                    method="POST",
                    url="https://example.invalid/resource",
                    policy=RetryPolicy(total_budget_seconds=10.0),
                    replay_safe=True,
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
                    replay_safe=True,
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
                    replay_safe=True,
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
                        replay_safe=True,
                    ),
                )

        error = error_info.value
        assert error.error_type == "ConnectError"
        assert error.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT
        assert error.diagnostics.retry_count == EXPECTED_RETRY_COUNT
        assert error.diagnostics.last_retry_reason == "exception"
        assert error.diagnostics.last_error_type == "ConnectError"

    asyncio.run(execute())


def test_raises_before_request_when_total_budget_is_exhausted() -> None:
    clock = _budget_exhausted_clock()

    async def handler(_request: httpx.Request) -> httpx.Response:
        pytest.fail("must not request")

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpxRetryError, match="before an attempt") as error_info:
                await AsyncHttpxRetryExecutor(monotonic=clock, sleep=_no_sleep).request(
                    client=client,
                    request=HttpxRetryRequest(
                        method="GET",
                        url="https://example.invalid/resource",
                        policy=RetryPolicy(total_budget_seconds=1.0),
                        replay_safe=True,
                    ),
                )

        assert error_info.value.diagnostics.attempt_count == 0

    asyncio.run(execute())


def test_stream_raises_before_request_when_total_budget_is_exhausted() -> None:
    clock = _budget_exhausted_clock()

    async def handler(_request: httpx.Request) -> httpx.Response:
        pytest.fail("must not request")

    async def consume(_body) -> str:
        pytest.fail("must not consume")

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpxRetryError, match="before an attempt") as error_info:
                await AsyncHttpxRetryExecutor(monotonic=clock, sleep=_no_sleep).stream(
                    client=client,
                    request=HttpxRetryRequest(
                        method="GET",
                        url="https://example.invalid/resource",
                        policy=RetryPolicy(total_budget_seconds=1.0),
                        replay_safe=True,
                    ),
                    body_consumer=consume,
                )

        assert error_info.value.diagnostics.attempt_count == 0

    asyncio.run(execute())


def test_stream_raises_last_retryable_exception_after_retry_budget_is_consumed() -> None:
    clock = AsyncMonotonicClock()

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(SYNTHETIC_ERROR_MESSAGE, request=request)

    async def consume(_body) -> str:
        pytest.fail("must not consume")

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpxRetryError) as error_info:
                await _executor(clock).stream(
                    client=client,
                    request=HttpxRetryRequest(
                        method="GET",
                        url="https://example.invalid/resource",
                        policy=RetryPolicy(initial_delay_seconds=1.0, total_budget_seconds=0.5),
                        replay_safe=True,
                    ),
                    body_consumer=consume,
                )

        assert error_info.value.error_type == "ConnectError"
        assert error_info.value.diagnostics.attempt_count == 1

    asyncio.run(execute())


def test_raises_last_retryable_exception_when_retry_delay_exhausts_budget() -> None:
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
                        policy=RetryPolicy(initial_delay_seconds=1.0, total_budget_seconds=1.0),
                        replay_safe=True,
                    ),
                )

        assert error_info.value.error_type == "ConnectError"
        assert error_info.value.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT

    asyncio.run(execute())


def test_raises_non_retryable_httpx_error_without_retrying() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        message = "synthetic decoding error"
        raise httpx.DecodingError(message)

    async def execute() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(HttpxRetryError) as error_info:
                await _executor(AsyncMonotonicClock()).request(
                    client=client,
                    request=HttpxRetryRequest(
                        method="GET",
                        url="https://example.invalid/resource",
                        policy=RetryPolicy(total_budget_seconds=10.0),
                        replay_safe=True,
                    ),
                )

        assert error_info.value.error_type == "DecodingError"
        assert error_info.value.diagnostics.attempt_count == 1

    asyncio.run(execute())


def test_raises_generic_retry_error_when_retry_delay_exhausts_budget_after_http_status() -> None:
    clock = AsyncMonotonicClock()

    async def execute() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(RETRYABLE_STATUS))
        ) as client:
            with pytest.raises(HttpxRetryError, match="before an attempt") as error_info:
                await _executor(clock).request(
                    client=client,
                    request=HttpxRetryRequest(
                        method="GET",
                        url="https://example.invalid/resource",
                        policy=RetryPolicy(initial_delay_seconds=1.0, total_budget_seconds=1.0),
                        replay_safe=True,
                    ),
                )

        assert error_info.value.diagnostics.last_http_status == RETRYABLE_STATUS

    asyncio.run(execute())


def test_retry_after_helpers_reject_blank_invalid_and_past_values() -> None:
    policy = RetryPolicy()

    assert retry_support.retry_after_delay(retry_after=" ", policy=policy) is None
    assert retry_support.retry_after_delay(retry_after="not-a-date", policy=policy) is None
    assert retry_support.retry_after_delay(retry_after="-1", policy=policy) is None


def test_http_date_delay_treats_naive_dates_as_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        retry_support,
        "parsedate_to_datetime",
        lambda _value: datetime(2026, 1, 1),  # noqa: DTZ001
    )

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN206
            return cls(2026, 1, 1, tzinfo=tz)

    monkeypatch.setattr(retry_support, "datetime", FixedDateTime)

    assert retry_support.http_date_delay("synthetic") == 0.0


def test_http_date_delay_accepts_aware_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    aware_date = datetime(2026, 1, 1, tzinfo=retry_support.UTC)
    monkeypatch.setattr(retry_support, "parsedate_to_datetime", lambda _value: aware_date)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN206
            return cls(2026, 1, 1, tzinfo=tz)

    monkeypatch.setattr(retry_support, "datetime", FixedDateTime)

    assert retry_support.http_date_delay("synthetic") == 0.0


def test_jittered_backoff_grows_for_later_attempts() -> None:
    assert (
        retry_support.jittered_backoff(
            2,
            RetryPolicy(),
            random=_fixed_random,
        )
        == EXPECTED_SECOND_JITTERED_DELAY
    )


def test_timeout_helpers_bound_numeric_and_missing_phase_values() -> None:
    assert (
        retry_support.timeout_with_budget(
            timeout=10.0,
            budget_seconds=REMAINING_BUDGET_SECONDS,
        )
        == REMAINING_BUDGET_SECONDS
    )

    timeout = retry_support.timeout_with_budget(
        timeout=HttpTimeout(read_seconds=1.0),
        budget_seconds=REMAINING_BUDGET_SECONDS,
    )

    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == REMAINING_BUDGET_SECONDS
    assert timeout.read == 1.0
    assert timeout.write == REMAINING_BUDGET_SECONDS
    assert timeout.pool == REMAINING_BUDGET_SECONDS


def _executor(clock: AsyncMonotonicClock) -> AsyncHttpxRetryExecutor:
    return AsyncHttpxRetryExecutor(monotonic=clock.monotonic, sleep=clock.sleep, random=_fixed_random)


def _budget_exhausted_clock():
    calls = 0

    def monotonic() -> float:
        nonlocal calls
        calls += 1
        return 0.0 if calls == 1 else 1.0

    return monotonic


async def _no_sleep(_delay: float) -> None:
    return None


def _fixed_random() -> float:
    return 0.5
