"""Tests for canonical public-web result formatting."""

from typing import cast

import pytest

from fabrica.features.web_content_fetching.application.dtos import (
    FetchContentFormat,
    FetchError,
    FetchErrorCode,
    FetchFailure,
    FetchRedirect,
    FetchSuccess,
    FetchWebContentResult,
)
from fabrica.features.web_content_fetching.application.result_formatting import (
    fetch_result_payload,
    fetch_web_content_result_payload,
)


def test_fetch_web_content_result_payload_includes_content_and_trust_metadata() -> None:
    result = FetchWebContentResult((_success(),), batch_content_truncated=True)

    payload = fetch_web_content_result_payload(result)

    assert payload == {
        "results": [
            {
                "requested_url": "https://example.com/page",
                "final_url": "https://example.com/page",
                "status": 200,
                "redirects": [],
                "trust": "untrusted_web_content",
                "success": True,
                "content_type": "text/plain",
                "media_type": "text/plain",
                "size_bytes": 5,
                "content_format": "text",
                "content": "hello",
                "content_chars": 5,
                "returned_chars": 5,
                "truncated": False,
            }
        ],
        "batch_content_truncated": True,
    }


def test_fetch_web_content_result_payload_retains_failure_and_redirect_metadata() -> None:
    result = FetchWebContentResult(
        (
            FetchFailure(
                requested_url="https://example.com/start",
                final_url="https://example.com/final",
                status=503,
                redirects=(FetchRedirect(302, "https://example.com/start", "https://example.com/final"),),
                error=FetchError(FetchErrorCode.HTTP_ERROR, "Unavailable", {"retryable": True}),
            ),
        )
    )

    payload = fetch_web_content_result_payload(result)

    assert payload["results"] == [
        {
            "requested_url": "https://example.com/start",
            "final_url": "https://example.com/final",
            "status": 503,
            "redirects": [
                {"status": 302, "from_url": "https://example.com/start", "to_url": "https://example.com/final"}
            ],
            "trust": "untrusted_web_content",
            "success": False,
            "error": {"code": "HTTP_ERROR", "message": "Unavailable", "metadata": {"retryable": True}},
        }
    ]


def test_fetch_result_payload_rejects_non_result_values() -> None:
    with pytest.raises(TypeError, match="fetch outcome"):
        fetch_result_payload(cast("FetchSuccess", object()))


def _success() -> FetchSuccess:
    return FetchSuccess(
        requested_url="https://example.com/page",
        final_url="https://example.com/page",
        status=200,
        content_type="text/plain",
        media_type="text/plain",
        size_bytes=5,
        content_format=FetchContentFormat.TEXT,
        content="hello",
        content_chars=5,
        returned_chars=5,
        truncated=False,
    )
