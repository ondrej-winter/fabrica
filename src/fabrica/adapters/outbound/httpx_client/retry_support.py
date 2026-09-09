"""Shared retry-policy mechanics for synchronous and asynchronous HTTPX execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from fabrica.adapters.outbound.httpx_client.contracts import (
    HttpResponse,
    HttpTimeout,
    HttpxRetryRequest,
    RetryDiagnostics,
)
from fabrica.adapters.outbound.httpx_client.policy import RetryPolicy


@dataclass(frozen=True, slots=True)
class RetryState:
    """Retry-loop facts used for delay decisions and diagnostics."""

    attempt: int
    start_time: float
    last_retry_reason: str | None
    last_http_status: int | None
    last_error_type: str | None


@dataclass(frozen=True, slots=True)
class RetryDelay:
    """Information needed to calculate and log one retry delay."""

    state: RetryState
    reason: str
    status: int | None
    error_type: str | None
    retry_after: str | None = None


def should_retry(
    *,
    request: HttpxRetryRequest,
    attempt: int,
    start_time: float,
    monotonic: Callable[[], float],
) -> bool:
    """Return whether another request attempt is authorized and affordable."""
    return (
        request.replay_safe
        and attempt < request.policy.max_attempts
        and remaining_budget(policy=request.policy, start_time=start_time, monotonic=monotonic) > 0
    )


def remaining_budget(*, policy: RetryPolicy, start_time: float, monotonic: Callable[[], float]) -> float:
    """Return the non-negative retry budget remaining at the current instant."""
    return max(policy.total_budget_seconds - (monotonic() - start_time), 0.0)


def diagnostics(*, state: RetryState, policy: RetryPolicy, monotonic: Callable[[], float]) -> RetryDiagnostics:
    """Build secret-safe diagnostics for a completed or failed retry execution."""
    elapsed_seconds = monotonic() - state.start_time
    return RetryDiagnostics(
        attempt_count=state.attempt,
        retry_count=max(state.attempt - 1, 0),
        last_retry_reason=state.last_retry_reason,
        last_http_status=state.last_http_status,
        last_error_type=state.last_error_type,
        elapsed_seconds=round(elapsed_seconds, 6),
        budget_exhausted=elapsed_seconds >= policy.total_budget_seconds,
    )


def retry_delay_seconds(
    *,
    delay: RetryDelay,
    policy: RetryPolicy,
    monotonic: Callable[[], float],
    random: Callable[[], float],
) -> float:
    """Calculate a retry delay constrained by Retry-After and remaining budget."""
    remaining = remaining_budget(policy=policy, start_time=delay.state.start_time, monotonic=monotonic)
    retry_after = retry_after_delay(retry_after=delay.retry_after, policy=policy)
    requested = retry_after if retry_after is not None else jittered_backoff(delay.state.attempt, policy, random=random)
    return min(requested, remaining)


def jittered_backoff(attempt: int, policy: RetryPolicy, *, random: Callable[[], float]) -> float:
    """Return a full-jitter exponential retry delay."""
    base_delay = min(policy.initial_delay_seconds * (2 ** max(attempt - 1, 0)), policy.max_delay_seconds)
    return random() * base_delay


def retry_after_delay(*, retry_after: str | None, policy: RetryPolicy) -> float | None:
    """Parse a bounded non-negative Retry-After header value."""
    if retry_after is None:
        return None
    stripped = retry_after.strip()
    if not stripped:
        return None
    try:
        delay = float(stripped)
    except ValueError:
        delay = http_date_delay(stripped)
    if delay is None or delay < 0:
        return None
    return min(delay, policy.retry_after_cap_seconds)


def http_date_delay(value: str) -> float | None:
    """Return seconds until an HTTP-date value, or ``None`` when invalid."""
    try:
        parsed = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (parsed - datetime.now(UTC)).total_seconds()


def to_http_response(response: httpx.Response) -> HttpResponse:
    """Map an HTTPX response to the shared adapter boundary DTO."""
    return HttpResponse(status_code=response.status_code, headers=dict(response.headers), text=response.text)


def timeout_with_budget(*, timeout: float | HttpTimeout | None, budget_seconds: float) -> float | httpx.Timeout:
    """Clamp every HTTP timeout phase to the remaining retry budget."""
    if timeout is None:
        return budget_seconds
    if isinstance(timeout, int | float):
        return min(float(timeout), budget_seconds)
    return httpx.Timeout(
        connect=_timeout_value_with_budget(timeout.connect_seconds, budget_seconds),
        read=_timeout_value_with_budget(timeout.read_seconds, budget_seconds),
        write=_timeout_value_with_budget(timeout.write_seconds, budget_seconds),
        pool=_timeout_value_with_budget(timeout.pool_seconds, budget_seconds),
    )


def _timeout_value_with_budget(value: float | None, budget_seconds: float) -> float:
    if value is None:
        return budget_seconds
    return min(value, budget_seconds)
