"""Reusable synchronous HTTPX adapter infrastructure."""

from fabrica.adapters.outbound.httpx_client.adapter import (
    DEFAULT_RETRY_POLICY,
    HttpResponse,
    HttpTimeout,
    HttpxRetryClient,
    HttpxRetryError,
    HttpxRetryExecutor,
    HttpxRetryRequest,
    HttpxRetryResult,
    RetryDiagnostics,
    RetryPolicy,
)

__all__ = [
    "DEFAULT_RETRY_POLICY",
    "HttpResponse",
    "HttpTimeout",
    "HttpxRetryClient",
    "HttpxRetryError",
    "HttpxRetryExecutor",
    "HttpxRetryRequest",
    "HttpxRetryResult",
    "RetryDiagnostics",
    "RetryPolicy",
]
