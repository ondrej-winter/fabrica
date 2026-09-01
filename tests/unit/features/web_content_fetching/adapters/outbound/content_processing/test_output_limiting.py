"""Tests for explicit per-response output limiting."""

import pytest

from fabrica.features.web_content_fetching.adapters.outbound.content_processing import (
    limit_web_content,
    process_web_content,
)
from fabrica.features.web_content_fetching.application.dtos import FetchContentFormat, FetchError

_SOURCE_CONTENT_CHARS = 8
_OUTPUT_CONTENT_CHARS = 5
_PROCESSOR_OUTPUT_CHARS = 10


def test_limit_web_content_preserves_the_head_and_reports_truncation() -> None:
    result = limit_web_content("abcdefgh", max_chars=_OUTPUT_CONTENT_CHARS)

    assert result.content == "abcde"
    assert result.content_chars == _SOURCE_CONTENT_CHARS
    assert result.returned_chars == _OUTPUT_CONTENT_CHARS
    assert result.truncated is True


@pytest.mark.parametrize("max_chars", [0, True])
def test_limit_web_content_rejects_invalid_caps(max_chars: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        limit_web_content("content", max_chars=max_chars)


def test_process_web_content_composes_classification_extraction_and_limiting() -> None:
    result = process_web_content(
        b"# Heading\n\nThis body is longer than the response cap.",
        content_type="text/markdown; charset=utf-8",
        final_url="https://example.com",
        max_chars=_PROCESSOR_OUTPUT_CHARS,
    )

    assert not isinstance(result, FetchError)
    assert result.content_format is FetchContentFormat.MARKDOWN
    assert result.content == "# Heading\n"
    assert result.content_chars > result.returned_chars
    assert result.returned_chars == _PROCESSOR_OUTPUT_CHARS
    assert result.truncated is True
