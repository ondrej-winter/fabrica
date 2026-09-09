"""Tests for shared HTTPX retry-support mechanics."""

from __future__ import annotations

import httpx

from fabrica.adapters.outbound.httpx_client import HttpTimeout, HttpxRetryRequest, RetryPolicy
from fabrica.adapters.outbound.httpx_client.retry_support import (
    RetryDelay,
    RetryState,
    diagnostics,
    http_date_delay,
    jittered_backoff,
    remaining_budget,
    retry_after_delay,
    retry_delay_seconds,
    should_retry,
    timeout_with_budget,
    to_http_response,
)

EXPECTED_ATTEMPT_COUNT = 2
CREATED_STATUS = 201
EXPECTED_REMAINING_BUDGET_SECONDS = 0.75
EXPECTED_ELAPSED_SECONDS = 2.0
EXPECTED_RETRY_DELAY_SECONDS = 1.5
EXPECTED_CAPPED_BACKOFF_SECONDS = 3.0
EXPECTED_RETRY_AFTER_SECONDS = 2.5


def test_retry_state_and_delay_retain_public_values() -> None:
    state = RetryState(1, 2.0, "exception", None, "ConnectError")

    delay = RetryDelay(state, "exception", None, "ConnectError", "1")

    assert delay.state is state
    assert delay.reason == "exception"
    assert delay.status is None
    assert delay.error_type == "ConnectError"
    assert delay.retry_after == "1"


def test_should_retry_requires_replay_authorization_attempt_capacity_and_budget() -> None:
    policy = RetryPolicy(max_attempts=2, total_budget_seconds=1.0)
    replay_safe_request = HttpxRetryRequest("GET", "https://example.invalid", policy, replay_safe=True)
    replay_unsafe_request = HttpxRetryRequest("GET", "https://example.invalid", policy)

    assert should_retry(request=replay_safe_request, attempt=1, start_time=0.0, monotonic=lambda: 0.5) is True
    assert should_retry(request=replay_safe_request, attempt=2, start_time=0.0, monotonic=lambda: 0.5) is False
    assert should_retry(request=replay_safe_request, attempt=1, start_time=0.0, monotonic=lambda: 1.0) is False
    assert should_retry(request=replay_unsafe_request, attempt=1, start_time=0.0, monotonic=lambda: 0.5) is False


def test_remaining_budget_never_returns_a_negative_value() -> None:
    policy = RetryPolicy(total_budget_seconds=2.0)

    assert remaining_budget(policy=policy, start_time=1.0, monotonic=lambda: 2.25) == EXPECTED_REMAINING_BUDGET_SECONDS
    assert remaining_budget(policy=policy, start_time=1.0, monotonic=lambda: 4.0) == 0.0


def test_diagnostics_rounds_elapsed_time_and_marks_exhausted_budget() -> None:
    state = RetryState(2, 1.0, "http_status", 503, None)

    result = diagnostics(state=state, policy=RetryPolicy(total_budget_seconds=2.0), monotonic=lambda: 3.0000004)

    assert result.attempt_count == EXPECTED_ATTEMPT_COUNT
    assert result.retry_count == 1
    assert result.elapsed_seconds == EXPECTED_ELAPSED_SECONDS
    assert result.budget_exhausted is True


def test_retry_delay_prefers_capped_retry_after_and_remaining_budget() -> None:
    policy = RetryPolicy(retry_after_cap_seconds=3.0, total_budget_seconds=2.0)
    delay = RetryDelay(RetryState(1, 0.0, "http_status", 429, None), "http_status", 429, None, "10")

    assert (
        retry_delay_seconds(delay=delay, policy=policy, monotonic=lambda: 0.5, random=lambda: 1.0)
        == EXPECTED_RETRY_DELAY_SECONDS
    )


def test_jittered_backoff_applies_exponential_cap_and_random_factor() -> None:
    policy = RetryPolicy(initial_delay_seconds=1.0, max_delay_seconds=3.0)

    assert jittered_backoff(3, policy, random=lambda: 0.5) == EXPECTED_RETRY_DELAY_SECONDS
    assert jittered_backoff(4, policy, random=lambda: 1.0) == EXPECTED_CAPPED_BACKOFF_SECONDS


def test_retry_after_delay_handles_delta_and_invalid_values() -> None:
    policy = RetryPolicy(retry_after_cap_seconds=10.0)

    assert retry_after_delay(retry_after="2.5", policy=policy) == EXPECTED_RETRY_AFTER_SECONDS
    assert retry_after_delay(retry_after="invalid", policy=policy) is None
    assert retry_after_delay(retry_after=None, policy=policy) is None


def test_http_date_delay_returns_none_for_invalid_values() -> None:
    assert http_date_delay("invalid") is None


def test_to_http_response_maps_httpx_response_to_boundary_response() -> None:
    mapped = to_http_response(httpx.Response(CREATED_STATUS, headers={"X-Trace": "trace-1"}, text="created"))

    assert mapped.status_code == CREATED_STATUS
    assert mapped.headers["x-trace"] == "trace-1"
    assert mapped.text == "created"


def test_timeout_with_budget_handles_missing_numeric_and_per_phase_timeouts() -> None:
    assert timeout_with_budget(timeout=None, budget_seconds=EXPECTED_ELAPSED_SECONDS) == EXPECTED_ELAPSED_SECONDS
    assert timeout_with_budget(timeout=3.0, budget_seconds=EXPECTED_ELAPSED_SECONDS) == EXPECTED_ELAPSED_SECONDS

    timeout = timeout_with_budget(
        timeout=HttpTimeout(connect_seconds=1.0, read_seconds=None, write_seconds=3.0, pool_seconds=None),
        budget_seconds=EXPECTED_ELAPSED_SECONDS,
    )

    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 1.0
    assert timeout.read == EXPECTED_ELAPSED_SECONDS
    assert timeout.write == EXPECTED_ELAPSED_SECONDS
    assert timeout.pool == EXPECTED_ELAPSED_SECONDS
