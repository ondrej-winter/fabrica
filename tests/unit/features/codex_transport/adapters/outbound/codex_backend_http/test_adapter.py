"""Tests for the Codex backend HTTP adapter."""

import httpx

from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import (
    CodexBackendHttpAdapter,
    CodexBackendRequestSettings,
)
from fabrica.features.codex_transport.application.dtos import (
    CodexCompletionCommand,
    CodexCredentials,
    CodexTransportStatus,
    CodexUsageProbeCommand,
)
from tests.synthetic_values import CODEX_ACCOUNT_ID, CODEX_BEARER_VALUE


def test_complete_posts_built_request_and_maps_success_response() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"output_text": "pong"})

    adapter = CodexBackendHttpAdapter(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = adapter.complete(
        command=CodexCompletionCommand(prompt="Reply with the single word: pong"),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"
    assert captured_request is not None
    assert captured_request.method == "POST"
    assert str(captured_request.url) == "https://chatgpt.com/backend-api/codex/responses"
    assert captured_request.headers["Authorization"] == f"Bearer {CODEX_BEARER_VALUE}"
    assert captured_request.headers["ChatGPT-Account-ID"] == "synthetic-account"


def test_complete_allows_timeout_and_request_setting_overrides() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.invalid/backend-api/custom-responses"
        assert request.headers["OAI-Product-Sku"] == "synthetic-sku"
        return httpx.Response(200, json={"output_text": "pong"})

    adapter = CodexBackendHttpAdapter(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        request_settings=CodexBackendRequestSettings(
            base_url="https://example.invalid/backend-api",
            path="custom-responses",
            model="synthetic-model",
            product_sku="synthetic-sku",
        ),
        timeout=3.0,
    )

    result = adapter.complete(
        command=CodexCompletionCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.SUCCESS


def test_complete_maps_backend_error_response_without_leaking_request_secrets() -> None:
    adapter = CodexBackendHttpAdapter(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    401,
                    json={"error": {"type": "invalid_token", "message": "synthetic auth failure"}},
                )
            )
        )
    )

    result = adapter.complete(
        command=CodexCompletionCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.AUTHENTICATION_FAILED
    assert CODEX_BEARER_VALUE not in str(result.observations)
    assert CODEX_ACCOUNT_ID not in str(result.observations)
    assert "synthetic auth failure" not in str(result.observations)


def test_complete_maps_non_json_success_to_backend_shape_mismatch() -> None:
    adapter = CodexBackendHttpAdapter(
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="not json")))
    )

    result = adapter.complete(
        command=CodexCompletionCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.BACKEND_SHAPE_MISMATCH


def test_complete_maps_event_stream_success_response() -> None:
    adapter = CodexBackendHttpAdapter(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={"content-type": "text/event-stream"},
                    text=(
                        "event: response.output_text.delta\n"
                        'data: {"type":"response.output_text.delta","delta":"pong"}\n\n'
                        "event: response.completed\n"
                        'data: {"type":"response.completed"}\n\n'
                    ),
                )
            )
        )
    )

    result = adapter.complete(
        command=CodexCompletionCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"


def test_complete_maps_httpx_transport_error_without_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        message = "synthetic failure for https://example.invalid"
        raise httpx.ConnectError(message, request=request)

    adapter = CodexBackendHttpAdapter(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = adapter.complete(
        command=CodexCompletionCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert result.observations[0].metadata == {"category": "client_error", "error_type": "ConnectError"}
    assert "example.invalid" not in str(result.observations)


def test_fetch_usage_gets_usage_endpoint_and_maps_success_response() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"plan_type": "synthetic-pro", "usage_percent": 10})

    adapter = CodexBackendHttpAdapter(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = adapter.fetch_usage(
        command=CodexUsageProbeCommand(),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.evidence is not None
    assert result.evidence.values["plan_type"] == "synthetic-pro"
    assert captured_request is not None
    assert captured_request.method == "GET"
    assert str(captured_request.url) == "https://chatgpt.com/backend-api/api/codex/usage"
    assert captured_request.headers["Authorization"] == f"Bearer {CODEX_BEARER_VALUE}"
    assert captured_request.headers["ChatGPT-Account-ID"] == "synthetic-account"


def test_fetch_usage_maps_httpx_transport_error_without_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        message = "synthetic failure for https://example.invalid"
        raise httpx.ConnectError(message, request=request)

    adapter = CodexBackendHttpAdapter(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = adapter.fetch_usage(
        command=CodexUsageProbeCommand(),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert result.observations[0].metadata == {"category": "client_error", "error_type": "ConnectError"}
    assert "example.invalid" not in str(result.observations)
