"""Tests for the HTTPX retry adapter package exports."""

from __future__ import annotations

from fabrica.adapters.outbound import httpx_client


def test_exports_declared_public_symbols() -> None:
    exported_names = set(httpx_client.__all__)

    assert exported_names == {
        "DEFAULT_RETRY_POLICY",
        "AsyncHttpBodyConsumer",
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
    }
    assert all(hasattr(httpx_client, name) for name in exported_names)
