"""Retry policy defaults and validation for HTTPX retry requests."""

from dataclasses import dataclass, field

import httpx

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
