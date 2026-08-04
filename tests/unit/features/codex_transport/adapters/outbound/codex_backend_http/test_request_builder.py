"""Tests for Codex backend request building."""

from typing import cast

import pytest

from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import (
    DEFAULT_CODEX_BACKEND_BASE_URL,
    DEFAULT_CODEX_BACKEND_PATH,
    DEFAULT_CODEX_MODEL,
    DEFAULT_CODEX_PRODUCT_SKU,
    DEFAULT_CODEX_USAGE_PATH,
    CodexBackendRequestSettings,
    CodexUsageRequestSettings,
    build_codex_backend_request,
    build_codex_usage_request,
)
from fabrica.features.codex_transport.adapters.outbound.redaction import REDACTED_VALUE
from fabrica.features.codex_transport.application.dtos import (
    CodexCredentials,
    CodexTransportProbeCommand,
    CodexUsageProbeCommand,
)


def test_build_codex_backend_request_uses_default_backend_url_and_headers() -> None:
    request = build_codex_backend_request(
        command=CodexTransportProbeCommand(prompt="Reply with the single word: pong"),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
    )

    assert request.url == f"{DEFAULT_CODEX_BACKEND_BASE_URL}{DEFAULT_CODEX_BACKEND_PATH}"
    assert request.headers == {
        "Authorization": "Bearer synthetic-access-token",
        "ChatGPT-Account-ID": "synthetic-account",
        "Content-Type": "application/json",
        "OAI-Product-Sku": DEFAULT_CODEX_PRODUCT_SKU,
    }


def test_build_codex_backend_request_produces_minimal_non_streaming_responses_payload() -> None:
    request = build_codex_backend_request(
        command=CodexTransportProbeCommand(prompt="Reply with the single word: pong"),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
    )

    assert request.json_payload == {
        "model": DEFAULT_CODEX_MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Reply with the single word: pong"},
                ],
            }
        ],
        "stream": True,
        "store": False,
    }


def test_build_codex_backend_request_allows_adapter_owned_backend_shape_overrides() -> None:
    request = build_codex_backend_request(
        command=CodexTransportProbeCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
        settings=CodexBackendRequestSettings(
            base_url="https://example.invalid/backend-api",
            path="/custom-responses",
            model="synthetic-model",
            product_sku="synthetic-sku",
        ),
    )

    assert request.url == "https://example.invalid/backend-api/custom-responses"
    assert request.headers["OAI-Product-Sku"] == "synthetic-sku"
    assert request.json_payload["model"] == "synthetic-model"


def test_build_codex_backend_request_allows_low_reasoning_effort_override() -> None:
    request = build_codex_backend_request(
        command=CodexTransportProbeCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
        settings=CodexBackendRequestSettings(
            model="gpt-5.3-codex-spark",
            reasoning_effort="low",
        ),
    )

    assert request.json_payload["model"] == "gpt-5.3-codex-spark"
    assert request.json_payload["reasoning"] == {"effort": "low"}


def test_backend_request_containers_are_copied_and_immutable() -> None:
    request = build_codex_backend_request(
        command=CodexTransportProbeCommand(prompt="synthetic prompt"),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
    )

    with pytest.raises(TypeError):
        cast("dict[str, str]", request.headers)["Authorization"] = "mutated"
    with pytest.raises(TypeError):
        cast("dict[str, object]", request.json_payload)["stream"] = True


def test_backend_request_redacted_observation_excludes_raw_tokens_and_account_identifiers() -> None:
    request = build_codex_backend_request(
        command=CodexTransportProbeCommand(prompt="Reply with the single word: pong"),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
    )

    observation = request.redacted_observation()

    assert observation.message == "built Codex backend request"
    assert observation.metadata == {
        "url": "https://chatgpt.com/backend-api/codex/responses",
        "authorization": REDACTED_VALUE,
        "account_header": REDACTED_VALUE,
        "header_count": 4,
        "payload_shape": "responses_non_streaming",
        "stream": True,
    }
    assert "synthetic-access-token" not in str(observation.metadata)
    assert "synthetic-account" not in str(observation.metadata)


def test_build_codex_usage_request_uses_default_usage_endpoint_and_headers() -> None:
    request = build_codex_usage_request(
        command=CodexUsageProbeCommand(),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
    )

    assert request.url == f"{DEFAULT_CODEX_BACKEND_BASE_URL}{DEFAULT_CODEX_USAGE_PATH}"
    assert request.headers == {
        "Authorization": "Bearer synthetic-access-token",
        "ChatGPT-Account-ID": "synthetic-account",
        "Content-Type": "application/json",
    }
    assert request.include_rate_limit_reset is False


def test_build_codex_usage_request_allows_adapter_owned_endpoint_override() -> None:
    request = build_codex_usage_request(
        command=CodexUsageProbeCommand(include_rate_limit_reset=True),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
        settings=CodexUsageRequestSettings(
            base_url="https://example.invalid/backend-api",
            usage_path="custom-usage",
        ),
    )

    assert request.url == "https://example.invalid/backend-api/custom-usage"
    assert request.include_rate_limit_reset is True


def test_usage_request_redacted_observation_excludes_raw_tokens_and_account_identifiers() -> None:
    request = build_codex_usage_request(
        command=CodexUsageProbeCommand(include_rate_limit_reset=True),
        credentials=CodexCredentials(
            access_token="synthetic-access-token",  # noqa: S106 - synthetic test value, not a secret.
            account_id="synthetic-account",
        ),
    )

    observation = request.redacted_observation()

    assert observation.message == "built Codex usage evidence request"
    assert observation.metadata == {
        "url": "https://chatgpt.com/backend-api/api/codex/usage",
        "authorization": REDACTED_VALUE,
        "account_header": REDACTED_VALUE,
        "header_count": 3,
        "include_rate_limit_reset": True,
    }
    assert "synthetic-access-token" not in str(observation.metadata)
    assert "synthetic-account" not in str(observation.metadata)
