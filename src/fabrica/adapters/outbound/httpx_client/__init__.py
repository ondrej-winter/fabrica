"""Reusable synchronous and asynchronous HTTPX adapter infrastructure."""

from fabrica.adapters.outbound.httpx_client.async_client import AsyncHttpxRetryClient
from fabrica.adapters.outbound.httpx_client.async_executor import AsyncHttpxRetryExecutor
from fabrica.adapters.outbound.httpx_client.client import SyncHttpxRetryClient
from fabrica.adapters.outbound.httpx_client.contracts import (
    HttpResponse,
    HttpTimeout,
    HttpxRetryRequest,
    HttpxRetryResult,
    RetryDiagnostics,
)
from fabrica.adapters.outbound.httpx_client.exceptions import HttpxRetryError
from fabrica.adapters.outbound.httpx_client.executor import SyncHttpxRetryExecutor
from fabrica.adapters.outbound.httpx_client.policy import (
    DEFAULT_RETRY_POLICY,
    RetryPolicy,
)

__all__ = [
    "DEFAULT_RETRY_POLICY",
    "AsyncHttpxRetryClient",
    "AsyncHttpxRetryExecutor",
    "HttpResponse",
    "HttpTimeout",
    "HttpxRetryError",
    "HttpxRetryRequest",
    "HttpxRetryResult",
    "RetryDiagnostics",
    "RetryPolicy",
    "SyncHttpxRetryClient",
    "SyncHttpxRetryExecutor",
]
