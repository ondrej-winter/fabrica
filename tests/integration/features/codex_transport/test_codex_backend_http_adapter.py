"""Offline integration tests for the Codex backend HTTP adapter."""

import httpx

from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import CodexBackendHttpAdapter
from fabrica.features.codex_transport.application.dtos import (
    CodexCredentials,
    CodexTransportProbeCommand,
    CodexTransportStatus,
    CodexUsageProbeCommand,
    CodexUsageStatus,
)


def test_codex_backend_http_adapter_executes_probe_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://chatgpt.com/backend-api/codex/responses"
        assert request.headers["Authorization"] == "Bearer synthetic-access-token"
        return httpx.Response(200, json={"output": [{"content": [{"type": "output_text", "text": "pong"}]}]})

    adapter = CodexBackendHttpAdapter(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = adapter.execute_probe(
        command=CodexTransportProbeCommand(prompt="Reply with the single word: pong"),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
    )

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"
    assert "synthetic-access-token" not in str(result.observations)
    assert "synthetic-account" not in str(result.observations)


def test_codex_backend_http_adapter_fetches_usage_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://chatgpt.com/backend-api/api/codex/usage"
        assert request.headers["Authorization"] == "Bearer synthetic-access-token"
        return httpx.Response(
            200,
            headers={"x-codex-ratelimit-remaining": "42"},
            json={"plan_type": "synthetic-pro", "usage_percent": 20},
        )

    adapter = CodexBackendHttpAdapter(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = adapter.fetch_usage(
        command=CodexUsageProbeCommand(),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
    )

    assert result.status is CodexUsageStatus.SUCCESS
    assert result.evidence is not None
    assert result.evidence.values == {
        "plan_type": "synthetic-pro",
        "usage_percent": 20,
        "rate_limit_header_count": 1,
        "rate_limit_header_names": "x-codex-ratelimit-remaining",
    }
    assert "synthetic-access-token" not in str(result.observations)
    assert "synthetic-account" not in str(result.observations)
