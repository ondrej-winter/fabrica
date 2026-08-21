"""Reusable synchronous HTTPX adapter infrastructure."""

from fabrica.adapters.outbound.httpx_client.client import HttpxRetryClient
from fabrica.adapters.outbound.httpx_client.contracts import (
    HttpResponse,
    HttpTimeout,
    HttpxRetryRequest,
    HttpxRetryResult,
    RetryDiagnostics,
)
from fabrica.adapters.outbound.httpx_client.exceptions import HttpxRetryError
from fabrica.adapters.outbound.httpx_client.executor import HttpxRetryExecutor
from fabrica.adapters.outbound.httpx_client.policy import (
    DEFAULT_RETRY_POLICY,
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
