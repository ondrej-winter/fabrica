"""Tests for Codex backend response and error mapping."""

from typing import cast

import pytest

from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.response_mapping import (
    CodexBackendResponse,
    CodexUsageResponse,
    map_codex_backend_response,
    map_codex_backend_transport_error,
    map_codex_usage_response,
    map_codex_usage_transport_error,
)
from fabrica.features.codex_transport.application.dtos import CodexTransportStatus
from fabrica.shared_kernel.model_usage import (
    ModelPricingStatus,
    ModelUsageCollectionStatus,
    ModelUsageEvidenceSource,
)

RESPONSE_INPUT_TOKENS = 10
RESPONSE_OUTPUT_TOKENS = 4
RESPONSE_TOTAL_TOKENS = 14
RESPONSE_CACHED_INPUT_TOKENS = 6
RESPONSE_REASONING_TOKENS = 2
STREAM_INPUT_TOKENS = 8
STREAM_OUTPUT_TOKENS = 2
STREAM_TOTAL_TOKENS = 10


def test_map_success_response_with_direct_output_text() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        json_body={"output_text": "pong"},
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"
    assert result.usage_evidence[0].status is ModelUsageCollectionStatus.UNAVAILABLE
    assert result.cost_evidence[0].pricing_status is ModelPricingStatus.UNKNOWN
    assert result.observations[0].metadata == {
        "http_status": 200,
        "category": "success",
        "header_count": 1,
        "response_shape": "responses_output_text",
        "error_type": None,
    }


def test_map_success_response_with_nested_responses_output_content() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={},
        json_body={
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": "po"},
                        {"type": "output_text", "text": "ng"},
                    ],
                },
            ],
        },
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"


def test_map_success_response_extracts_safe_response_usage_evidence() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={},
        json_body={
            "output_text": "pong",
            "model": "codex-mini",
            "usage": {
                "input_tokens": RESPONSE_INPUT_TOKENS,
                "output_tokens": RESPONSE_OUTPUT_TOKENS,
                "total_tokens": RESPONSE_TOTAL_TOKENS,
                "input_token_details": {"cached_tokens": RESPONSE_CACHED_INPUT_TOKENS},
                "output_token_details": {"reasoning_tokens": RESPONSE_REASONING_TOKENS},
                "account_id": "synthetic-account",
                "access_token": "synthetic-access-token",
            },
        },
    )

    result = map_codex_backend_response(response)

    usage = result.usage_evidence[0]
    assert usage.status is ModelUsageCollectionStatus.COLLECTED
    assert usage.source is ModelUsageEvidenceSource.RESPONSE_PAYLOAD
    assert usage.model == "codex-mini"
    assert usage.tokens.input_tokens == RESPONSE_INPUT_TOKENS
    assert usage.tokens.output_tokens == RESPONSE_OUTPUT_TOKENS
    assert usage.tokens.total_tokens == RESPONSE_TOTAL_TOKENS
    assert usage.tokens.cached_input_tokens == RESPONSE_CACHED_INPUT_TOKENS
    assert usage.tokens.reasoning_tokens == RESPONSE_REASONING_TOKENS
    assert "synthetic-account" not in str(result)
    assert "synthetic-access-token" not in str(result)


def test_map_success_response_extracts_partial_usage_without_zero_defaults() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={},
        json_body={"output_text": "pong", "usage": {"output_tokens": RESPONSE_OUTPUT_TOKENS}},
    )

    result = map_codex_backend_response(response)

    usage = result.usage_evidence[0]
    assert usage.status is ModelUsageCollectionStatus.PARTIALLY_COLLECTED
    assert usage.tokens.input_tokens is None
    assert usage.tokens.output_tokens == RESPONSE_OUTPUT_TOKENS
    assert usage.tokens.total_tokens is None


def test_map_success_response_ignores_unsafe_or_invalid_usage_fields() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={},
        json_body={
            "output_text": "pong",
            "usage": {
                "input_tokens": -1,
                "output_tokens": True,
                "total_tokens": "14",
                "authorization": "Bearer synthetic-token",
            },
        },
    )

    result = map_codex_backend_response(response)

    usage = result.usage_evidence[0]
    assert usage.status is ModelUsageCollectionStatus.UNAVAILABLE
    assert usage.tokens.input_tokens is None
    assert usage.tokens.output_tokens is None
    assert usage.tokens.total_tokens is None
    assert "synthetic-token" not in str(result)


def test_map_success_response_from_event_stream() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        json_body=(
            "event: response.output_text.delta\n"
            'data: {"type":"response.output_text.delta","delta":"po"}\n\n'
            "event: response.output_text.delta\n"
            'data: {"type":"response.output_text.delta","delta":"ng"}\n\n'
            "event: response.completed\n"
            'data: {"type":"response.completed"}\n\n'
        ),
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"
    assert result.observations[0].metadata["response_shape"] == "event_stream"


def test_map_success_response_from_event_stream_done_text() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        json_body=(
            "event: response.output_text.done\n"
            'data: {"type":"response.output_text.done","text":"pong"}\n\n'
            "event: response.completed\n"
            'data: {"type":"response.completed"}\n\n'
        ),
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"


def test_map_success_response_from_event_stream_completed_response_output() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        json_body=(
            "event: response.completed\n"
            "data: {"
            '"type":"response.completed",'
            '"response":{"output":[{"content":[{"type":"output_text","text":"pong"}]}]}'
            "}\n\n"
        ),
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"


def test_map_success_response_from_event_stream_extracts_usage_evidence() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        json_body=(
            "event: response.output_text.delta\n"
            'data: {"type":"response.output_text.delta","delta":"pong"}\n\n'
            "event: response.completed\n"
            "data: {"
            '"type":"response.completed",'
            f'"response":{{"usage":{{"input_tokens":{STREAM_INPUT_TOKENS},'
            f'"output_tokens":{STREAM_OUTPUT_TOKENS},"total_tokens":{STREAM_TOTAL_TOKENS}}}}}'
            "}\n\n"
        ),
    )

    result = map_codex_backend_response(response)

    usage = result.usage_evidence[0]
    assert result.status is CodexTransportStatus.SUCCESS
    assert usage.status is ModelUsageCollectionStatus.COLLECTED
    assert usage.source is ModelUsageEvidenceSource.STREAM_EVENT
    assert usage.tokens.input_tokens == STREAM_INPUT_TOKENS
    assert usage.tokens.output_tokens == STREAM_OUTPUT_TOKENS
    assert usage.tokens.total_tokens == STREAM_TOTAL_TOKENS


def test_map_success_response_from_event_stream_output_item_done_content() -> None:
    response = CodexBackendResponse(
        status_code=200,
        headers={"content-type": "text/event-stream"},
        json_body=(
            "event: response.output_item.done\n"
            "data: {"
            '"type":"response.output_item.done",'
            '"item":{"content":[{"type":"output_text","text":"pong"}]}'
            "}\n\n"
        ),
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.output_text == "pong"


def test_map_authentication_failure_for_401_and_403() -> None:
    for status_code in (401, 403):
        response = CodexBackendResponse(
            status_code=status_code,
            headers={},
            json_body={"error": {"type": "invalid_token", "message": "synthetic invalid credential"}},
        )

        result = map_codex_backend_response(response)

        assert result.status is CodexTransportStatus.AUTHENTICATION_FAILED
        assert result.output_text is None
        assert result.usage_evidence[0].status is ModelUsageCollectionStatus.FAILED
        assert result.cost_evidence[0].pricing_status is ModelPricingStatus.NOT_AVAILABLE
        assert result.observations[0].metadata["http_status"] == status_code
        assert result.observations[0].metadata["category"] == "authentication"
        assert result.observations[0].metadata["error_type"] == "invalid_token"


def test_map_cloudflare_challenge_to_transport_error() -> None:
    response = CodexBackendResponse(
        status_code=403,
        headers={"cf-mitigated": "challenge", "content-type": "text/html; charset=UTF-8"},
        json_body=None,
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert result.output_text is None
    assert result.observations[0].metadata == {
        "http_status": 403,
        "category": "edge_challenge",
        "header_count": 2,
        "response_shape": "NoneType",
        "error_type": None,
    }


def test_map_429_with_quota_body_to_quota_exceeded() -> None:
    response = CodexBackendResponse(
        status_code=429,
        headers={},
        json_body={"error": {"type": "insufficient_quota", "message": "synthetic quota exceeded"}},
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.QUOTA_EXCEEDED
    assert result.observations[0].metadata["category"] == "quota"


def test_map_429_without_quota_signal_to_rate_limited() -> None:
    response = CodexBackendResponse(
        status_code=429,
        headers={"x-ratelimit-remaining": "0"},
        json_body={"error": {"type": "rate_limited", "message": "synthetic rate limit"}},
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.RATE_LIMITED
    assert result.observations[0].metadata["category"] == "rate_limit"


def test_map_rate_limit_header_signal_to_rate_limited() -> None:
    response = CodexBackendResponse(status_code=503, headers={"x-codex-ratelimit-remaining": "0"}, json_body={})

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.RATE_LIMITED


def test_map_unexpected_success_shape_to_backend_shape_mismatch() -> None:
    response = CodexBackendResponse(status_code=200, headers={}, json_body={"unexpected": "shape"})

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.BACKEND_SHAPE_MISMATCH
    assert result.output_text is None
    assert result.observations[0].metadata["category"] == "shape_mismatch"
    assert result.observations[0].metadata["response_shape"] == "mapping"


def test_map_other_unsuccessful_status_to_transport_error() -> None:
    response = CodexBackendResponse(
        status_code=500,
        headers={"set-cookie": "synthetic-cookie"},
        json_body={"error": {"type": "server_error", "message": "synthetic backend failure"}},
    )

    result = map_codex_backend_response(response)

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert result.observations[0].metadata == {
        "http_status": 500,
        "category": "backend_error",
        "header_count": 1,
        "response_shape": "error",
        "error_type": "server_error",
    }
    assert "synthetic-cookie" not in str(result.observations)
    assert "synthetic backend failure" not in str(result.observations)


def test_map_transport_exception_to_transport_error_without_error_message() -> None:
    result = map_codex_backend_transport_error("TimeoutError")

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert result.output_text is None
    assert result.observations[0].metadata == {"category": "client_error", "error_type": "TimeoutError"}
    assert "example.invalid" not in str(result.observations)


def test_response_headers_are_copied_and_immutable() -> None:
    headers = {"x-test": "original"}
    response = CodexBackendResponse(status_code=200, headers=headers, json_body={"output_text": "pong"})

    headers["x-test"] = "mutated"

    assert response.headers["x-test"] == "original"
    with pytest.raises(TypeError):
        cast("dict[str, str]", response.headers)["x-test"] = "changed"


def test_map_usage_success_response_extracts_safe_usage_evidence() -> None:
    response = CodexUsageResponse(
        status_code=200,
        headers={"x-codex-ratelimit-remaining": "12", "set-cookie": "synthetic-cookie"},
        json_body={
            "plan_type": "synthetic-pro",
            "usage_percent": 25,
            "remaining": 75,
            "account_id": "synthetic-account",
            "access_token": "synthetic-access-token",
            "nested": {"quota": "not extracted"},
        },
    )

    result = map_codex_usage_response(response)

    assert result.status is CodexTransportStatus.SUCCESS
    assert result.evidence is not None
    assert result.evidence.values == {
        "plan_type": "synthetic-pro",
        "usage_percent": 25,
        "remaining": 75,
        "rate_limit_header_count": 1,
        "rate_limit_header_names": "x-codex-ratelimit-remaining",
    }
    assert "synthetic-account" not in str(result)
    assert "synthetic-access-token" not in str(result)
    assert "synthetic-cookie" not in str(result)


def test_map_usage_authentication_failure_for_401() -> None:
    response = CodexUsageResponse(
        status_code=401,
        headers={},
        json_body={"error": {"type": "invalid_token", "message": "synthetic auth failure"}},
    )

    result = map_codex_usage_response(response)

    assert result.status is CodexTransportStatus.AUTHENTICATION_FAILED
    assert result.evidence is None
    assert result.observations[0].metadata["category"] == "authentication"
    assert result.observations[0].metadata["error_type"] == "invalid_token"
    assert "synthetic auth failure" not in str(result.observations)


def test_map_usage_429_with_quota_body_to_quota_exceeded() -> None:
    response = CodexUsageResponse(
        status_code=429,
        headers={},
        json_body={"error": {"type": "quota_exceeded", "message": "synthetic quota exceeded"}},
    )

    result = map_codex_usage_response(response)

    assert result.status is CodexTransportStatus.QUOTA_EXCEEDED
    assert result.observations[0].metadata["category"] == "quota"


def test_map_usage_rate_limit_header_signal_to_rate_limited() -> None:
    response = CodexUsageResponse(status_code=200, headers={"x-codex-ratelimit-remaining": "0"}, json_body={})

    result = map_codex_usage_response(response)

    assert result.status is CodexTransportStatus.RATE_LIMITED


def test_map_usage_unexpected_success_shape_to_backend_shape_mismatch() -> None:
    response = CodexUsageResponse(status_code=200, headers={}, json_body={"unexpected": "shape"})

    result = map_codex_usage_response(response)

    assert result.status is CodexTransportStatus.BACKEND_SHAPE_MISMATCH
    assert result.observations[0].metadata["category"] == "shape_mismatch"


def test_map_usage_transport_exception_to_transport_error_without_error_message() -> None:
    result = map_codex_usage_transport_error("TimeoutError")

    assert result.status is CodexTransportStatus.TRANSPORT_ERROR
    assert result.evidence is None
    assert result.observations[0].metadata == {"category": "client_error", "error_type": "TimeoutError"}
    assert "example.invalid" not in str(result.observations)
