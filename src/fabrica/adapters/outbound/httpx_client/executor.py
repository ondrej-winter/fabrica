"""Synchronous HTTPX retry execution."""

from __future__ import annotations

import logging
import random as random_module
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import httpx

from fabrica.adapters.outbound.httpx_client.contracts import (
    HttpResponse,
    HttpTimeout,
    HttpxRetryRequest,
    HttpxRetryResult,
    RetryDiagnostics,
)
from fabrica.adapters.outbound.httpx_client.exceptions import HttpxRetryError

if TYPE_CHECKING:
    from collections.abc import Callable

    from fabrica.adapters.outbound.httpx_client.policy import RetryPolicy

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetryState:
    """Retry-loop facts passed between helper methods."""

    attempt: int
    start_time: float
    last_retry_reason: str | None
    last_http_status: int | None
    last_error_type: str | None


@dataclass(frozen=True, slots=True)
class RetryDelay:
    """Information needed to choose and log one retry delay."""

    state: RetryState
    reason: str
    status: int | None
    error_type: str | None
    retry_after: str | None = None


class HttpxRetryExecutor:
    """Execute synchronous HTTPX requests with explicit opt-in retry policies."""

    def __init__(
        self,
        *,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        random: Callable[[], float] | None = None,
    ) -> None:
        self._monotonic = monotonic if monotonic is not None else time.monotonic
        self._sleep = sleep if sleep is not None else time.sleep
        self._random = random if random is not None else random_module.random

    def request(
        self,
        *,
        client: httpx.Client,
        request: HttpxRetryRequest,
    ) -> HttpxRetryResult:
        """Execute one request according to the supplied retry policy."""
        start_time = self._monotonic()
        attempt = 0
        last_reason: str | None = None
        last_status: int | None = None
        last_error_type: str | None = None
        last_exception: httpx.HTTPError | None = None

        while attempt < request.policy.max_attempts:
            remaining_budget = self._remaining_budget(policy=request.policy, start_time=start_time)
            if remaining_budget <= 0:
                break
            attempt += 1
            try:
                response = client.request(
                    request.method,
                    request.url,
                    headers=dict(request.headers or {}),
                    json=dict(request.json) if request.json is not None else None,
                    timeout=_timeout_with_budget(timeout=request.timeout, budget_seconds=remaining_budget),
                )
            except request.policy.retryable_exception_types as err:
                last_exception = err
                last_reason = "exception"
                last_status = None
                last_error_type = type(err).__name__
                state = RetryState(attempt, start_time, last_reason, last_status, last_error_type)
                if not self._should_retry(attempt=attempt, policy=request.policy, start_time=start_time):
                    raise HttpxRetryError(err, self._diagnostics(state=state, policy=request.policy)) from err
                self._sleep_before_retry(
                    policy=request.policy,
                    delay=RetryDelay(state=state, reason=last_reason, status=None, error_type=last_error_type),
                )
                continue
            except httpx.HTTPError as err:
                raise HttpxRetryError(
                    err,
                    self._diagnostics(
                        state=RetryState(attempt, start_time, "exception", None, type(err).__name__),
                        policy=request.policy,
                    ),
                ) from err

            last_exception = None
            last_status = response.status_code
            state = RetryState(attempt, start_time, last_reason, last_status, last_error_type)
            if response.status_code not in request.policy.retryable_status_codes:
                return HttpxRetryResult(
                    response=_to_http_response(response),
                    diagnostics=self._diagnostics(state=state, policy=request.policy),
                )

            last_reason = "http_status"
            state = RetryState(attempt, start_time, last_reason, last_status, last_error_type)
            if not self._should_retry(attempt=attempt, policy=request.policy, start_time=start_time):
                return HttpxRetryResult(
                    response=_to_http_response(response),
                    diagnostics=self._diagnostics(state=state, policy=request.policy),
                )
            self._sleep_before_retry(
                policy=request.policy,
                delay=RetryDelay(
                    state=state,
                    reason=last_reason,
                    status=response.status_code,
                    error_type=None,
                    retry_after=response.headers.get("Retry-After"),
                ),
            )

        state = RetryState(attempt, start_time, last_reason, last_status, last_error_type)
        if last_exception is not None:
            raise HttpxRetryError(last_exception, self._diagnostics(state=state, policy=request.policy))
        raise HttpxRetryError(
            httpx.TransportError("HTTP request failed before an attempt was made"),
            self._diagnostics(state=state, policy=request.policy),
        )

    def _should_retry(self, *, attempt: int, policy: RetryPolicy, start_time: float) -> bool:
        return attempt < policy.max_attempts and self._remaining_budget(policy=policy, start_time=start_time) > 0

    def _sleep_before_retry(self, *, policy: RetryPolicy, delay: RetryDelay) -> None:
        remaining_budget = self._remaining_budget(policy=policy, start_time=delay.state.start_time)
        retry_after_delay = self._retry_after_delay(retry_after=delay.retry_after, policy=policy)
        requested_delay = (
            retry_after_delay if retry_after_delay is not None else self._jittered_backoff(delay.state.attempt, policy)
        )
        delay_seconds = min(requested_delay, remaining_budget)
        LOGGER.info(
            "retrying HTTP request",
            extra={
                "attempt": delay.state.attempt,
                "retry_reason": delay.reason,
                "http_status": delay.status,
                "error_type": delay.error_type,
                "retry_delay_seconds": round(delay_seconds, 6),
                "remaining_budget_seconds": round(remaining_budget, 6),
            },
        )
        if delay_seconds > 0:
            self._sleep(delay_seconds)

    def _jittered_backoff(self, attempt: int, policy: RetryPolicy) -> float:
        base_delay = min(policy.initial_delay_seconds * (2 ** max(attempt - 1, 0)), policy.max_delay_seconds)
        return self._random() * base_delay

    def _retry_after_delay(self, *, retry_after: str | None, policy: RetryPolicy) -> float | None:
        if retry_after is None:
            return None
        stripped = retry_after.strip()
        if not stripped:
            return None
        try:
            delay = float(stripped)
        except ValueError:
            delay = self._http_date_delay(stripped)
        if delay is None or delay < 0:
            return None
        return min(delay, policy.retry_after_cap_seconds)

    def _http_date_delay(self, value: str) -> float | None:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return (parsed - datetime.now(UTC)).total_seconds()

    def _remaining_budget(self, *, policy: RetryPolicy, start_time: float) -> float:
        return max(policy.total_budget_seconds - (self._monotonic() - start_time), 0.0)

    def _diagnostics(self, *, state: RetryState, policy: RetryPolicy) -> RetryDiagnostics:
        elapsed_seconds = self._monotonic() - state.start_time
        return RetryDiagnostics(
            attempt_count=state.attempt,
            retry_count=max(state.attempt - 1, 0),
            last_retry_reason=state.last_retry_reason,
            last_http_status=state.last_http_status,
            last_error_type=state.last_error_type,
            elapsed_seconds=round(elapsed_seconds, 6),
            budget_exhausted=elapsed_seconds >= policy.total_budget_seconds,
        )


def _to_http_response(response: httpx.Response) -> HttpResponse:
    return HttpResponse(status_code=response.status_code, headers=dict(response.headers), text=response.text)


def _timeout_with_budget(*, timeout: float | HttpTimeout | None, budget_seconds: float) -> float | httpx.Timeout:
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
