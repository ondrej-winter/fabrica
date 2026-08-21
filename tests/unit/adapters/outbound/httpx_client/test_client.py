"""Tests for the HTTPX retry client lifecycle wrapper."""

from __future__ import annotations

import httpx

from fabrica.adapters.outbound.httpx_client import (
    HttpxRetryClient,
    HttpxRetryRequest,
    RetryPolicy,
)

SUCCESS_STATUS = 200


def test_uses_client_factory_and_closes_client_after_request() -> None:
    observed_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(SUCCESS_STATUS, json={"ok": True})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    retry_client = HttpxRetryClient(client_factory=lambda: http_client)
    request = HttpxRetryRequest(method="GET", url="https://example.invalid/resource", policy=RetryPolicy())

    result = retry_client.request(request)

    assert result.response.status_code == SUCCESS_STATUS
    assert observed_request is not None
    assert str(observed_request.url) == request.url
    assert http_client.is_closed
