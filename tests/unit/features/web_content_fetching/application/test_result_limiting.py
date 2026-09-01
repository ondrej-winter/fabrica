"""Tests for aggregate public-web content allocation."""

from typing import cast

import pytest

from fabrica.features.web_content_fetching.application.dtos import (
    FetchContentFormat,
    FetchError,
    FetchErrorCode,
    FetchFailure,
    FetchSuccess,
)
from fabrica.features.web_content_fetching.application.result_limiting import limit_batch_content

_SERVICE_UNAVAILABLE_STATUS = 503


def test_limit_batch_content_preserves_all_metadata_while_trimming_only_content() -> None:
    success = _success("abcdef")
    failure = FetchFailure(
        "https://example.com/failure",
        FetchError(FetchErrorCode.HTTP_ERROR),
        status=_SERVICE_UNAVAILABLE_STATUS,
    )

    result = limit_batch_content((success, failure, _success("ghij")), max_content_chars=8)

    first, retained_failure, second = result.results
    assert isinstance(first, FetchSuccess)
    assert first.content == "abcdef"
    assert isinstance(retained_failure, FetchFailure)
    assert retained_failure.status == _SERVICE_UNAVAILABLE_STATUS
    assert isinstance(second, FetchSuccess)
    assert second.content == "gh"
    assert second.truncated
    assert result.batch_content_truncated


@pytest.mark.parametrize("limit", [0, True, "invalid"])
def test_limit_batch_content_rejects_invalid_limits(limit: object) -> None:
    with pytest.raises((TypeError, ValueError), match="positive integer"):
        limit_batch_content((_success("content"),), max_content_chars=cast("int", limit))


def _success(content: str) -> FetchSuccess:
    return FetchSuccess(
        requested_url="https://example.com/page",
        final_url="https://example.com/page",
        status=200,
        content_type="text/plain",
        media_type="text/plain",
        size_bytes=len(content),
        content_format=FetchContentFormat.TEXT,
        content=content,
        content_chars=len(content),
        returned_chars=len(content),
        truncated=False,
    )
