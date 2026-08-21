"""Offline integration tests for the Codex backend HTTP adapter."""

import asyncio

import httpx

from fabrica.adapters.outbound.httpx_client import AsyncHttpxRetryClient
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import CodexBackendHttpAdapter
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportStatus,
    CodexUsageProbeCommand,
)
from tests.synthetic_values import CODEX_ACCOUNT_ID, CODEX_BEARER_VALUE


def test_codex_backend_http_adapter_executes_probe_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://chatgpt.com/backend-api/codex/responses"
        assert request.headers["Authorization"] == f"Bearer {CODEX_BEARER_VALUE}"
        return httpx.Response(200, json={"output": [{"content": [{"type": "output_text", "text": "pong"}]}]})

    adapter = CodexBackendHttpAdapter(
        http_client=AsyncHttpxRetryClient(
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
    )

    result = asyncio.run(
        adapter.complete(
            command=CodexCompletionCommand(prompt="Reply with the single word: pong"),
            credentials=CodexCredentials(
                access_token=CODEX_BEARER_VALUE,
                account_id=CODEX_ACCOUNT_ID,
            ),
        )
    )

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"
    assert CODEX_BEARER_VALUE not in str(result.observations)
    assert CODEX_ACCOUNT_ID not in str(result.observations)


def test_codex_backend_http_adapter_fetches_usage_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://chatgpt.com/backend-api/api/codex/usage"
        assert request.headers["Authorization"] == f"Bearer {CODEX_BEARER_VALUE}"
        return httpx.Response(
            200,
            headers={"x-codex-ratelimit-remaining": "42"},
            json={"plan_type": "synthetic-pro", "usage_percent": 20},
        )

    adapter = CodexBackendHttpAdapter(
        http_client=AsyncHttpxRetryClient(
            client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
    )

    result = asyncio.run(
        adapter.fetch_usage(
            command=CodexUsageProbeCommand(),
            credentials=CodexCredentials(
                access_token=CODEX_BEARER_VALUE,
                account_id=CODEX_ACCOUNT_ID,
            ),
        )
    )

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.evidence is not None
    assert result.evidence.values == {
        "plan_type": "synthetic-pro",
        "usage_percent": 20,
        "rate_limit_header_count": 1,
        "rate_limit_header_names": "x-codex-ratelimit-remaining",
    }
    assert CODEX_BEARER_VALUE not in str(result.observations)
    assert CODEX_ACCOUNT_ID not in str(result.observations)
