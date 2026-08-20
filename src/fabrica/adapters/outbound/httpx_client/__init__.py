"""Reusable synchronous HTTPX adapter infrastructure."""

from fabrica.adapters.outbound.httpx_client.adapter import (
    DEFAULT_RETRY_POLICY,
    HttpxRequest,
    HttpxRetryExecutor,
    RetryDiagnostics,
    RetryOutcome,
    RetryPolicy,
    diagnostics_metadata,
)

__all__ = [
    "DEFAULT_RETRY_POLICY",
    "HttpxRequest",
    "HttpxRetryExecutor",
    "RetryDiagnostics",
    "RetryOutcome",
    "RetryPolicy",
    "diagnostics_metadata",
]
