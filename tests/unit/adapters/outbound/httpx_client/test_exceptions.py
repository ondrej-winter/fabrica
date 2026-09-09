"""Tests for HTTPX retry adapter exceptions."""

from __future__ import annotations

import httpx

from fabrica.adapters.outbound.httpx_client import HttpxRetryError, RetryDiagnostics


def test_exposes_error_message_type_and_diagnostics() -> None:
    request = httpx.Request("GET", "https://example.invalid/resource")
    error = httpx.ConnectError("connection failed", request=request)
    diagnostics = RetryDiagnostics(
        attempt_count=1,
        retry_count=0,
        last_retry_reason="exception",
        last_http_status=None,
        last_error_type="ConnectError",
        elapsed_seconds=0.0,
        budget_exhausted=False,
    )

    wrapped_error = HttpxRetryError(error, diagnostics)

    assert str(wrapped_error) == "connection failed"
    assert wrapped_error.error_type == "ConnectError"
    assert wrapped_error.diagnostics is diagnostics
