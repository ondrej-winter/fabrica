"""Tests for the Codex backend HTTP adapter."""

from collections.abc import Callable

import httpx

from fabrica.adapters.outbound.httpx_client import RetryPolicy, SyncHttpxRetryClient, SyncHttpxRetryExecutor
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

EXPECTED_ATTEMPT_COUNT = 2
EXPECTED_RETRY_COUNT = 1
EXPECTED_FIRST_JITTERED_DELAY = 0.25
SUCCESS_STATUS = 200
RETRYABLE_STATUS = 503
SYNTHETIC_ERROR_MESSAGE = "synthetic secret url"


class MonotonicClock:
    def __init__(self) -> None:
        self.current = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.current

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.current += delay


def test_complete_posts_built_request_and_maps_success_response() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"output_text": "pong"})

    adapter = CodexBackendHttpAdapter(http_client=_http_client(handler))

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
        http_client=_http_client(handler),
        request_settings=CodexBackendRequestSettings(
            base_url="https://example.invalid/backend-api",
            path="custom-responses",
            model="synthetic-model",
            product_sku="synthetic-sku",
        ),
        completion_timeout=3.0,
    )

    result = adapter.complete(
        command=CodexCompletionCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.SUCCESS


def test_complete_retries_transient_post_failure_and_records_summary() -> None:
    clock = MonotonicClock()
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(RETRYABLE_STATUS)
        return httpx.Response(SUCCESS_STATUS, json={"output_text": "pong"})

    adapter = CodexBackendHttpAdapter(
        http_client=_http_client(handler, clock=clock),
        completion_retry_policy=RetryPolicy(total_budget_seconds=10.0),
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
    assert calls == EXPECTED_ATTEMPT_COUNT
    assert clock.sleeps == [EXPECTED_FIRST_JITTERED_DELAY]
    retry_observation = result.observations[-1]
    assert retry_observation.message == "HTTP retry policy completed"
    assert retry_observation.metadata["attempt_count"] == EXPECTED_ATTEMPT_COUNT
    assert retry_observation.metadata["retry_count"] == EXPECTED_RETRY_COUNT
    assert retry_observation.metadata["last_retry_reason"] == "http_status"
    assert retry_observation.metadata["last_http_status"] == SUCCESS_STATUS
    assert CODEX_BEARER_VALUE not in str(retry_observation)
    assert CODEX_ACCOUNT_ID not in str(retry_observation)


def test_complete_default_retry_policy_does_not_replay_backend_5xx() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(RETRYABLE_STATUS)
        return httpx.Response(SUCCESS_STATUS, json={"output_text": "pong"})

    adapter = CodexBackendHttpAdapter(http_client=_http_client(handler))

    result = adapter.complete(
        command=CodexCompletionCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert calls == 1
    retry_observation = result.observations[-1]
    assert retry_observation.metadata["attempt_count"] == 1
    assert retry_observation.metadata["retry_count"] == 0
    assert retry_observation.metadata["last_http_status"] == RETRYABLE_STATUS


def test_complete_maps_backend_error_response_without_leaking_request_secrets() -> None:
    adapter = CodexBackendHttpAdapter(
        http_client=_http_client(
            lambda _request: httpx.Response(
                401,
                json={"error": {"type": "invalid_token", "message": "synthetic auth failure"}},
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
    adapter = CodexBackendHttpAdapter(http_client=_http_client(lambda _request: httpx.Response(200, text="not json")))

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
        http_client=_http_client(
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

    adapter = CodexBackendHttpAdapter(http_client=_http_client(handler))

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

    adapter = CodexBackendHttpAdapter(http_client=_http_client(handler))

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


def test_fetch_usage_retries_connect_error_and_records_summary() -> None:
    clock = MonotonicClock()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError(SYNTHETIC_ERROR_MESSAGE, request=request)
        return httpx.Response(SUCCESS_STATUS, json={"plan_type": "synthetic-pro", "usage_percent": 10})

    adapter = CodexBackendHttpAdapter(
        http_client=_http_client(handler, clock=clock),
        usage_retry_policy=RetryPolicy(total_budget_seconds=10.0),
    )

    result = adapter.fetch_usage(
        command=CodexUsageProbeCommand(),
        credentials=CodexCredentials(
            access_token=CODEX_BEARER_VALUE,
            account_id=CODEX_ACCOUNT_ID,
        ),
    )

    assert result.status is CodexTransportStatus.SUCCESS
    assert calls == EXPECTED_ATTEMPT_COUNT
    assert clock.sleeps == [EXPECTED_FIRST_JITTERED_DELAY]
    retry_observation = result.observations[-1]
    assert retry_observation.metadata["attempt_count"] == EXPECTED_ATTEMPT_COUNT
    assert retry_observation.metadata["retry_count"] == EXPECTED_RETRY_COUNT
    assert retry_observation.metadata["last_retry_reason"] == "exception"
    assert retry_observation.metadata["last_error_type"] == "ConnectError"
    assert "example.invalid" not in str(result.observations)
    assert CODEX_BEARER_VALUE not in str(result.observations)


def test_fetch_usage_maps_httpx_transport_error_without_error_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        message = "synthetic failure for https://example.invalid"
        raise httpx.ConnectError(message, request=request)

    adapter = CodexBackendHttpAdapter(http_client=_http_client(handler))

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


def _http_client(
    handler: Callable[[httpx.Request], httpx.Response], clock: MonotonicClock | None = None
) -> SyncHttpxRetryClient:
    executor = (
        SyncHttpxRetryExecutor(monotonic=clock.monotonic, sleep=clock.sleep, random=lambda: 0.5)
        if clock is not None
        else SyncHttpxRetryExecutor()
    )
    return SyncHttpxRetryClient(
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        executor=executor,
    )
