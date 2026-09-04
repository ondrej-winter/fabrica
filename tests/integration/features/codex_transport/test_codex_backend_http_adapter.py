"""Offline integration tests for the Codex backend HTTP adapter."""

import asyncio
from collections.abc import AsyncIterator

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


class _ClosingStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...], error: BaseException | None = None) -> None:
        self._chunks = chunks
        self._error = error
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk
        if self._error is not None:
            raise self._error

    async def aclose(self) -> None:
        self.closed = True


def test_codex_backend_http_adapter_consumes_completed_async_stream_and_closes_resources() -> None:
    stream = _ClosingStream(
        (
            b"event: response.output_text.delta\n",
            b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n',
            b"event: response.completed\n",
            b'data: {"type":"response.completed","response":{"output_text":"pong"}}\n\n',
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://chatgpt.com/backend-api/codex/responses"
        assert request.headers["Authorization"] == f"Bearer {CODEX_BEARER_VALUE}"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = CodexBackendHttpAdapter(http_client=AsyncHttpxRetryClient(client_factory=lambda: http_client))

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
    assert stream.closed
    assert http_client.is_closed


def test_codex_backend_http_adapter_maps_mid_stream_read_failure_without_partial_output() -> None:
    stream = _ClosingStream(
        (b'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"partial"}\n\n',),
        httpx.ReadError("synthetic stream failure"),
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = CodexBackendHttpAdapter(http_client=AsyncHttpxRetryClient(client_factory=lambda: http_client))

    result = asyncio.run(
        adapter.complete(
            command=CodexCompletionCommand(prompt="synthetic prompt"),
            credentials=CodexCredentials(access_token=CODEX_BEARER_VALUE, account_id=CODEX_ACCOUNT_ID),
        )
    )

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert result.output_text is None
    assert "partial" not in str(result)
    assert "synthetic stream failure" not in str(result)
    assert stream.closed
    assert http_client.is_closed


def test_codex_backend_http_adapter_maps_stream_cancellation_without_partial_output() -> None:
    stream = _ClosingStream(
        (b'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"partial"}\n\n',),
        asyncio.CancelledError(),
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = CodexBackendHttpAdapter(http_client=AsyncHttpxRetryClient(client_factory=lambda: http_client))

    result = asyncio.run(
        adapter.complete(
            command=CodexCompletionCommand(prompt="synthetic prompt"),
            credentials=CodexCredentials(access_token=CODEX_BEARER_VALUE, account_id=CODEX_ACCOUNT_ID),
        )
    )

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert result.output_text is None
    assert "partial" not in str(result)
    assert stream.closed
    assert http_client.is_closed


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
