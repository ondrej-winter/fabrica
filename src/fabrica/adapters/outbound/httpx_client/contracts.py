"""Boundary DTOs exposed by the reusable HTTPX retry adapter."""

from __future__ import annotations

import json as json_library
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fabrica.adapters.outbound.httpx_client.policy import RetryPolicy


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


@dataclass(frozen=True, slots=True)
class HttpxRetryResult:
    """Final HTTP response plus bounded retry diagnostics."""

    response: HttpResponse
    diagnostics: RetryDiagnostics
