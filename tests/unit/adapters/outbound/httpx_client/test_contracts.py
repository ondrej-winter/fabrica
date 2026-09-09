"""Tests for HTTPX retry adapter boundary contracts."""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from typing import cast

import pytest

from fabrica.adapters.outbound.httpx_client import (
    HttpResponse,
    HttpTimeout,
    HttpxRetryRequest,
    HttpxRetryResult,
    RetryDiagnostics,
    RetryPolicy,
)

EXPECTED_ATTEMPT_COUNT = 2
EXPECTED_HTTP_STATUS = 200


def test_same_timeout_applies_value_to_every_phase() -> None:
    assert HttpTimeout.same(1.5) == HttpTimeout(
        connect_seconds=1.5,
        read_seconds=1.5,
        write_seconds=1.5,
        pool_seconds=1.5,
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("connect_seconds", -0.1),
        ("read_seconds", float("nan")),
        ("write_seconds", float("inf")),
        ("pool_seconds", float("-inf")),
    ],
)
def test_timeout_rejects_invalid_phase_values(field_name: str, value: float) -> None:
    with pytest.raises(ValueError, match=field_name):
        HttpTimeout(**{field_name: value})


@pytest.mark.parametrize("value", [-0.1, float("nan"), float("inf"), float("-inf")])
def test_same_timeout_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError, match="connect_seconds"):
        HttpTimeout.same(value)


def test_request_retains_public_parameters() -> None:
    policy = RetryPolicy()
    timeout = HttpTimeout.same(2.0)

    request = HttpxRetryRequest(
        method="POST",
        url="https://example.invalid/resource",
        policy=policy,
        headers={"X-Request-Id": "request-1"},
        json={"query": "value"},
        timeout=timeout,
        replay_safe=True,
    )

    assert request.method == "POST"
    assert request.url == "https://example.invalid/resource"
    assert request.policy is policy
    assert request.headers == {"X-Request-Id": "request-1"}
    assert request.json == {"query": "value"}
    assert request.timeout is timeout
    assert request.replay_safe is True


def test_diagnostics_metadata_is_complete_and_immutable() -> None:
    diagnostics = RetryDiagnostics(
        attempt_count=2,
        retry_count=1,
        last_retry_reason="http_status",
        last_http_status=503,
        last_error_type=None,
        elapsed_seconds=0.25,
        budget_exhausted=False,
    )

    metadata = diagnostics.as_metadata()

    assert metadata == {
        "attempt_count": 2,
        "retry_count": 1,
        "last_retry_reason": "http_status",
        "last_http_status": 503,
        "last_error_type": None,
        "elapsed_seconds": 0.25,
        "budget_exhausted": False,
    }
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", metadata)["attempt_count"] = 3


def test_response_copies_and_immutably_exposes_headers() -> None:
    source_headers = {"X-Request-Id": "request-1"}

    response = HttpResponse(status_code=200, headers=source_headers, text="{}")
    source_headers["X-Request-Id"] = "request-2"

    assert response.headers == {"X-Request-Id": "request-1"}
    with pytest.raises(TypeError):
        cast("MutableMapping[str, str]", response.headers)["X-Other"] = "value"


def test_response_decodes_json_text() -> None:
    response = HttpResponse(status_code=200, headers={}, text='{"ok": true}')

    assert response.json() == {"ok": True}


def test_response_json_propagates_decode_errors() -> None:
    response = HttpResponse(status_code=200, headers={}, text="not json")

    with pytest.raises(json.JSONDecodeError):
        response.json()


def test_result_groups_response_and_diagnostics() -> None:
    response = HttpResponse(status_code=EXPECTED_HTTP_STATUS, headers={}, text="ok")
    diagnostics = RetryDiagnostics(
        attempt_count=1,
        retry_count=0,
        last_retry_reason=None,
        last_http_status=EXPECTED_HTTP_STATUS,
        last_error_type=None,
        elapsed_seconds=0.0,
        budget_exhausted=False,
    )

    result = HttpxRetryResult(response=response, diagnostics=diagnostics)

    assert result.response is response
    assert result.diagnostics is diagnostics
