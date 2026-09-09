"""Synchronous HTTPX retry execution."""

from __future__ import annotations

import logging
import random as random_module
import time
from typing import TYPE_CHECKING

import httpx

from fabrica.adapters.outbound.httpx_client.contracts import HttpxRetryRequest, HttpxRetryResult
from fabrica.adapters.outbound.httpx_client.exceptions import HttpxRetryError
from fabrica.adapters.outbound.httpx_client.retry_support import (
    RetryDelay,
    RetryState,
    diagnostics,
    remaining_budget,
    retry_delay_seconds,
    should_retry,
    timeout_with_budget,
    to_http_response,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from fabrica.adapters.outbound.httpx_client.policy import RetryPolicy

LOGGER = logging.getLogger(__name__)


class SyncHttpxRetryExecutor:
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

        while attempt < request.policy.max_attempts:  # pragma: no branch
            budget_seconds = remaining_budget(policy=request.policy, start_time=start_time, monotonic=self._monotonic)
            if budget_seconds <= 0:
                break
            attempt += 1
            try:
                response = client.request(
                    request.method,
                    request.url,
                    headers=dict(request.headers or {}),
                    json=dict(request.json) if request.json is not None else None,
                    timeout=timeout_with_budget(timeout=request.timeout, budget_seconds=budget_seconds),
                )
            except request.policy.retryable_exception_types as err:
                last_exception = err
                last_reason = "exception"
                last_status = None
                last_error_type = type(err).__name__
                state = RetryState(attempt, start_time, last_reason, last_status, last_error_type)
                if not should_retry(request=request, attempt=attempt, start_time=start_time, monotonic=self._monotonic):
                    raise HttpxRetryError(
                        err,
                        diagnostics(state=state, policy=request.policy, monotonic=self._monotonic),
                    ) from err
                self._sleep_before_retry(
                    policy=request.policy,
                    delay=RetryDelay(state=state, reason=last_reason, status=None, error_type=last_error_type),
                )
                continue
            except httpx.HTTPError as err:
                raise HttpxRetryError(
                    err,
                    diagnostics(
                        state=RetryState(attempt, start_time, "exception", None, type(err).__name__),
                        policy=request.policy,
                        monotonic=self._monotonic,
                    ),
                ) from err

            last_exception = None
            last_status = response.status_code
            state = RetryState(attempt, start_time, last_reason, last_status, last_error_type)
            if response.status_code not in request.policy.retryable_status_codes:
                return HttpxRetryResult(
                    response=to_http_response(response),
                    diagnostics=diagnostics(state=state, policy=request.policy, monotonic=self._monotonic),
                )

            last_reason = "http_status"
            state = RetryState(attempt, start_time, last_reason, last_status, last_error_type)
            if not should_retry(request=request, attempt=attempt, start_time=start_time, monotonic=self._monotonic):
                return HttpxRetryResult(
                    response=to_http_response(response),
                    diagnostics=diagnostics(state=state, policy=request.policy, monotonic=self._monotonic),
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
            raise HttpxRetryError(
                last_exception,
                diagnostics(state=state, policy=request.policy, monotonic=self._monotonic),
            )
        raise HttpxRetryError(
            httpx.TransportError("HTTP request failed before an attempt was made"),
            diagnostics(state=state, policy=request.policy, monotonic=self._monotonic),
        )

    def _sleep_before_retry(self, *, policy: RetryPolicy, delay: RetryDelay) -> None:
        delay_seconds = retry_delay_seconds(
            delay=delay,
            policy=policy,
            monotonic=self._monotonic,
            random=self._random,
        )
        budget_seconds = remaining_budget(policy=policy, start_time=delay.state.start_time, monotonic=self._monotonic)
        LOGGER.info(
            "retrying HTTP request",
            extra={
                "attempt": delay.state.attempt,
                "retry_reason": delay.reason,
                "http_status": delay.status,
                "error_type": delay.error_type,
                "retry_delay_seconds": round(delay_seconds, 6),
                "remaining_budget_seconds": round(budget_seconds, 6),
            },
        )
        if delay_seconds > 0:
            self._sleep(delay_seconds)
