"""Synchronous HTTPX retry support for outbound adapters."""

from __future__ import annotations

import json as json_library
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Self

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

LOGGER = logging.getLogger(__name__)

DEFAULT_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
DEFAULT_RETRYABLE_EXCEPTIONS = (httpx.TimeoutException, httpx.TransportError)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry policy for an explicitly opted-in HTTP request."""

    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 4.0
    retry_after_cap_seconds: float = 30.0
    total_budget_seconds: float = 30.0
    retryable_status_codes: frozenset[int] = field(default_factory=lambda: DEFAULT_RETRYABLE_STATUS_CODES)
    retryable_exception_types: tuple[type[httpx.HTTPError], ...] = DEFAULT_RETRYABLE_EXCEPTIONS

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            msg = "max_attempts must be at least 1"
            raise ValueError(msg)
        for field_name in (
            "initial_delay_seconds",
            "max_delay_seconds",
            "retry_after_cap_seconds",
            "total_budget_seconds",
        ):
            value = getattr(self, field_name)
            if value < 0:
                msg = f"{field_name} must not be negative"
                raise ValueError(msg)
        if self.total_budget_seconds == 0:
            msg = "total_budget_seconds must be greater than 0"
            raise ValueError(msg)
        for exception_type in self.retryable_exception_types:
            if not issubclass(exception_type, httpx.HTTPError):
                msg = "retryable_exception_types must contain only httpx.HTTPError subclasses"
                raise TypeError(msg)


DEFAULT_RETRY_POLICY = RetryPolicy()


@dataclass(frozen=True, slots=True)
class HttpTimeout:
    """HTTP timeout settings owned by the shared HTTP adapter boundary."""

    connect_seconds: float | None = None
    read_seconds: float | None = None
    write_seconds: float | None = None
    pool_seconds: float | None = None

    @classmethod
    def same(cls, seconds: float) -> Self:
        """Return timeout settings that apply the same limit to all phases."""
        return cls(
            connect_seconds=seconds,
            read_seconds=seconds,
            write_seconds=seconds,
            pool_seconds=seconds,
        )


@dataclass(frozen=True, slots=True)
class HttpxRetryRequest:
    """HTTP request parameters and retry policy for one execution."""

    method: str
    url: str
    policy: RetryPolicy
    headers: Mapping[str, str] | None = None
    json: Mapping[str, object] | None = None
    timeout: float | HttpTimeout | None = None


@dataclass(frozen=True, slots=True)
class RetryDiagnostics:
    """Secret-safe retry summary returned to the owning outbound adapter."""

    attempt_count: int
    retry_count: int
    last_retry_reason: str | None
    last_http_status: int | None
    last_error_type: str | None
    elapsed_seconds: float
    budget_exhausted: bool

    def as_metadata(self) -> Mapping[str, str | int | float | bool | None]:
        """Return retry diagnostics as immutable scalar metadata."""
        return MappingProxyType(
            {
                "attempt_count": self.attempt_count,
                "retry_count": self.retry_count,
                "last_retry_reason": self.last_retry_reason,
                "last_http_status": self.last_http_status,
                "last_error_type": self.last_error_type,
                "elapsed_seconds": self.elapsed_seconds,
                "budget_exhausted": self.budget_exhausted,
            }
        )


@dataclass(frozen=True, slots=True)
class HttpxRetryResult:
    """Final HTTP response plus bounded retry diagnostics."""

    response: HttpResponse
    diagnostics: RetryDiagnostics


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """HTTP response data exposed by the shared HTTP adapter boundary."""

    status_code: int
    headers: Mapping[str, str]
    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))

    def json(self) -> object:
        """Decode response text as JSON."""
        return json_library.loads(self.text)


class HttpxRetryError(Exception):
    """HTTPX request failure with bounded retry diagnostics."""

    def __init__(self, error: httpx.HTTPError, diagnostics: RetryDiagnostics) -> None:
        super().__init__(str(error))
        self.error_type = type(error).__name__
        self.diagnostics = diagnostics


@dataclass(frozen=True, slots=True)
class RetryState:
    """Mutable retry-loop facts passed between helper methods."""

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


@dataclass(frozen=True, slots=True)
class HttpxRetryExecutor:
    """Execute synchronous HTTPX requests with explicit opt-in retry policies."""

    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    random: Callable[[], float] = random.random

    def request(
        self,
        *,
        client: httpx.Client,
        request: HttpxRetryRequest,
    ) -> HttpxRetryResult:
        """Execute one request according to the supplied retry policy."""
        start_time = self.monotonic()
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
                if not self._should_retry(attempt=attempt, policy=request.policy, start_time=start_time):
                    raise HttpxRetryError(
                        err,
                        self._diagnostics(
                            state=RetryState(
                                attempt=attempt,
                                start_time=start_time,
                                last_retry_reason=last_reason,
                                last_http_status=last_status,
                                last_error_type=last_error_type,
                            ),
                            policy=request.policy,
                        ),
                    ) from err
                self._sleep_before_retry(
                    policy=request.policy,
                    delay=RetryDelay(
                        state=RetryState(
                            attempt=attempt,
                            start_time=start_time,
                            last_retry_reason=last_reason,
                            last_http_status=last_status,
                            last_error_type=last_error_type,
                        ),
                        reason=last_reason,
                        status=None,
                        error_type=last_error_type,
                    ),
                )
                continue
            except httpx.HTTPError as err:
                raise HttpxRetryError(
                    err,
                    self._diagnostics(
                        state=RetryState(
                            attempt=attempt,
                            start_time=start_time,
                            last_retry_reason="exception",
                            last_http_status=None,
                            last_error_type=type(err).__name__,
                        ),
                        policy=request.policy,
                    ),
                ) from err

            last_exception = None
            last_status = response.status_code
            if response.status_code not in request.policy.retryable_status_codes:
                return HttpxRetryResult(
                    response=_to_http_response(response),
                    diagnostics=self._diagnostics(
                        state=RetryState(
                            attempt=attempt,
                            start_time=start_time,
                            last_retry_reason=last_reason,
                            last_http_status=last_status,
                            last_error_type=last_error_type,
                        ),
                        policy=request.policy,
                    ),
                )

            last_reason = "http_status"
            if not self._should_retry(attempt=attempt, policy=request.policy, start_time=start_time):
                return HttpxRetryResult(
                    response=_to_http_response(response),
                    diagnostics=self._diagnostics(
                        state=RetryState(
                            attempt=attempt,
                            start_time=start_time,
                            last_retry_reason=last_reason,
                            last_http_status=last_status,
                            last_error_type=last_error_type,
                        ),
                        policy=request.policy,
                    ),
                )
            self._sleep_before_retry(
                policy=request.policy,
                delay=RetryDelay(
                    state=RetryState(
                        attempt=attempt,
                        start_time=start_time,
                        last_retry_reason=last_reason,
                        last_http_status=last_status,
                        last_error_type=last_error_type,
                    ),
                    reason=last_reason,
                    status=response.status_code,
                    error_type=None,
                    retry_after=response.headers.get("Retry-After"),
                ),
            )

        if last_exception is not None:
            raise HttpxRetryError(
                last_exception,
                self._diagnostics(
                    state=RetryState(
                        attempt=attempt,
                        start_time=start_time,
                        last_retry_reason=last_reason,
                        last_http_status=last_status,
                        last_error_type=last_error_type,
                    ),
                    policy=request.policy,
                ),
            )
        raise HttpxRetryError(
            httpx.TransportError("HTTP request failed before an attempt was made"),
            self._diagnostics(
                state=RetryState(
                    attempt=attempt,
                    start_time=start_time,
                    last_retry_reason=last_reason,
                    last_http_status=last_status,
                    last_error_type=last_error_type,
                ),
                policy=request.policy,
            ),
        )

    def _should_retry(self, *, attempt: int, policy: RetryPolicy, start_time: float) -> bool:
        return attempt < policy.max_attempts and self._remaining_budget(policy=policy, start_time=start_time) > 0

    def _sleep_before_retry(
        self,
        *,
        policy: RetryPolicy,
        delay: RetryDelay,
    ) -> None:
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
            self.sleep(delay_seconds)

    def _jittered_backoff(self, attempt: int, policy: RetryPolicy) -> float:
        base_delay = min(policy.initial_delay_seconds * (2 ** max(attempt - 1, 0)), policy.max_delay_seconds)
        return self.random() * base_delay

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
        return max(policy.total_budget_seconds - (self.monotonic() - start_time), 0.0)

    def _diagnostics(
        self,
        *,
        state: RetryState,
        policy: RetryPolicy,
    ) -> RetryDiagnostics:
        elapsed_seconds = self.monotonic() - state.start_time
        return RetryDiagnostics(
            attempt_count=state.attempt,
            retry_count=max(state.attempt - 1, 0),
            last_retry_reason=state.last_retry_reason,
            last_http_status=state.last_http_status,
            last_error_type=state.last_error_type,
            elapsed_seconds=round(elapsed_seconds, 6),
            budget_exhausted=elapsed_seconds >= policy.total_budget_seconds,
        )


@dataclass(frozen=True, slots=True)
class HttpxRetryClient:
    """Create HTTPX clients, execute retry requests, and own client lifecycle."""

    client_factory: Callable[[], httpx.Client] = httpx.Client
    executor: HttpxRetryExecutor = field(default_factory=HttpxRetryExecutor)

    def request(self, request: HttpxRetryRequest) -> HttpxRetryResult:
        """Execute one retry request using a short-lived HTTPX client."""
        with self.client_factory() as client:
            return self.executor.request(client=client, request=request)


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
