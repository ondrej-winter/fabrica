"""Tests for the synchronous HTTPX retry executor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import cast

import httpx
import pytest

from fabrica.adapters.outbound.httpx_client import (
    HttpTimeout,
    HttpxRetryError,
    HttpxRetryExecutor,
    HttpxRetryRequest,
    RetryPolicy,
)

SUCCESS_STATUS = 200
RETRYABLE_STATUS = 503
RATE_LIMIT_STATUS = 429
EXPECTED_ATTEMPT_COUNT = 2
EXPECTED_RETRY_COUNT = 1
EXPECTED_FIRST_JITTERED_DELAY = 0.25
RETRY_AFTER_CAP_SECONDS = 30.0
HTTP_DATE_DELAY_SECONDS = 5.0
SYNTHETIC_ERROR_MESSAGE = "synthetic secret url"


class MonotonicClock:
    """Deterministic monotonic clock and sleep recorder for retry tests."""

    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.current

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.current += delay


def test_retries_transport_error_then_returns_success() -> None:
    clock = MonotonicClock()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError(SYNTHETIC_ERROR_MESSAGE, request=request)
        return httpx.Response(SUCCESS_STATUS, json={"ok": True})

    outcome = _executor(clock).request(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        request=HttpxRetryRequest(
            method="GET",
            url="https://example.invalid/resource",
            policy=RetryPolicy(total_budget_seconds=10.0),
        ),
    )

    assert outcome.response.status_code == SUCCESS_STATUS
    assert calls == EXPECTED_ATTEMPT_COUNT
    assert clock.sleeps == [EXPECTED_FIRST_JITTERED_DELAY]
    assert outcome.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT
    assert outcome.diagnostics.retry_count == EXPECTED_RETRY_COUNT
    assert outcome.diagnostics.last_retry_reason == "exception"
    assert outcome.diagnostics.last_error_type == "ConnectError"


def test_honors_bounded_retry_after_delta_seconds() -> None:
    clock = MonotonicClock()
    responses = iter(
        (
            httpx.Response(RATE_LIMIT_STATUS, headers={"Retry-After": "60"}),
            httpx.Response(SUCCESS_STATUS, json={"ok": True}),
        )
    )

    outcome = _executor(clock).request(
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: next(responses))),
        request=HttpxRetryRequest(
            method="GET",
            url="https://example.invalid/resource",
            policy=RetryPolicy(total_budget_seconds=40.0, retry_after_cap_seconds=30.0),
        ),
    )

    assert outcome.response.status_code == SUCCESS_STATUS
    assert clock.sleeps == [RETRY_AFTER_CAP_SECONDS]
    assert outcome.diagnostics.last_http_status == SUCCESS_STATUS
    assert outcome.diagnostics.retry_count == EXPECTED_RETRY_COUNT


def test_honors_retry_after_http_date() -> None:
    clock = MonotonicClock()
    retry_after = format_datetime(datetime.now(UTC) + timedelta(seconds=HTTP_DATE_DELAY_SECONDS), usegmt=True)
    responses = iter(
        (
            httpx.Response(RETRYABLE_STATUS, headers={"Retry-After": retry_after}),
            httpx.Response(SUCCESS_STATUS, json={"ok": True}),
        )
    )

    outcome = _executor(clock).request(
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: next(responses))),
        request=HttpxRetryRequest(
            method="GET",
            url="https://example.invalid/resource",
            policy=RetryPolicy(total_budget_seconds=40.0, retry_after_cap_seconds=30.0),
        ),
    )

    assert outcome.response.status_code == SUCCESS_STATUS
    assert 0 < clock.sleeps[0] <= HTTP_DATE_DELAY_SECONDS


def test_preserves_zero_retry_after_without_falling_back_to_jitter() -> None:
    clock = MonotonicClock()
    responses = iter(
        (
            httpx.Response(RATE_LIMIT_STATUS, headers={"Retry-After": "0"}),
            httpx.Response(SUCCESS_STATUS, json={"ok": True}),
        )
    )

    outcome = _executor(clock).request(
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: next(responses))),
        request=HttpxRetryRequest(
            method="GET",
            url="https://example.invalid/resource",
            policy=RetryPolicy(total_budget_seconds=40.0),
        ),
    )

    assert outcome.response.status_code == SUCCESS_STATUS
    assert clock.sleeps == []


def test_bounds_per_attempt_timeout_to_remaining_retry_budget() -> None:
    clock = MonotonicClock()
    observed_timeouts: list[httpx.Timeout] = []

    def handler(request: httpx.Request) -> httpx.Response:
        timeout = request.extensions["timeout"]
        observed_timeouts.append(httpx.Timeout(**timeout))
        clock.current += 9.5
        return httpx.Response(RETRYABLE_STATUS)

    outcome = _executor(clock).request(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        request=HttpxRetryRequest(
            method="GET",
            url="https://example.invalid/resource",
            policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0.0, total_budget_seconds=10.0),
            timeout=HttpTimeout(connect_seconds=10.0, read_seconds=10.0, write_seconds=10.0, pool_seconds=10.0),
        ),
    )

    assert outcome.response.status_code == RETRYABLE_STATUS
    assert [timeout.read for timeout in observed_timeouts] == [10.0, 0.5]
    assert outcome.diagnostics.budget_exhausted is True


def test_rejects_non_http_retry_exception_types() -> None:
    invalid_exception_type = cast("type[httpx.HTTPError]", KeyboardInterrupt)

    with pytest.raises(TypeError, match="retryable_exception_types"):
        RetryPolicy(retryable_exception_types=(invalid_exception_type,))


def test_rejects_zero_retry_budget() -> None:
    with pytest.raises(ValueError, match="total_budget_seconds"):
        RetryPolicy(total_budget_seconds=0.0)


def test_stops_when_attempt_budget_is_exhausted() -> None:
    clock = MonotonicClock()

    outcome = _executor(clock).request(
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(RETRYABLE_STATUS))),
        request=HttpxRetryRequest(
            method="GET",
            url="https://example.invalid/resource",
            policy=RetryPolicy(max_attempts=2, total_budget_seconds=10.0),
        ),
    )

    assert outcome.response.status_code == RETRYABLE_STATUS
    assert outcome.diagnostics.attempt_count == EXPECTED_ATTEMPT_COUNT
    assert outcome.diagnostics.retry_count == EXPECTED_RETRY_COUNT
    assert outcome.diagnostics.last_retry_reason == "http_status"
    assert outcome.diagnostics.last_http_status == RETRYABLE_STATUS


def test_raises_retry_error_with_diagnostics_after_exhausting_transport_errors() -> None:
    clock = MonotonicClock()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(SYNTHETIC_ERROR_MESSAGE, request=request)

    with pytest.raises(HttpxRetryError) as error_info:
        _executor(clock).request(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
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


def test_raises_retry_error_without_retrying_non_retryable_httpx_errors() -> None:
    clock = MonotonicClock()

    def handler(_request: httpx.Request) -> httpx.Response:
        message = "synthetic decoding error"
        raise httpx.DecodingError(message)

    with pytest.raises(HttpxRetryError) as error_info:
        _executor(clock).request(
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            request=HttpxRetryRequest(
                method="GET",
                url="https://example.invalid/resource",
                policy=RetryPolicy(total_budget_seconds=10.0),
            ),
        )

    error = error_info.value
    assert error.error_type == "DecodingError"
    assert error.diagnostics.attempt_count == 1
    assert error.diagnostics.retry_count == 0
    assert error.diagnostics.last_error_type == "DecodingError"


def _executor(clock: MonotonicClock) -> HttpxRetryExecutor:
    return HttpxRetryExecutor(monotonic=clock.monotonic, sleep=clock.sleep, random=_fixed_random)


def _fixed_random() -> float:
    return 0.5
