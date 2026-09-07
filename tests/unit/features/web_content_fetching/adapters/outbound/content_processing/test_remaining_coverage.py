"""Focused coverage for content-processing defensive input paths."""

import pytest

from fabrica.features.web_content_fetching.adapters.outbound.content_processing import (
    WebContentProcessingAdapter,
    classify_web_content,
    decode_web_content,
    limit_web_content,
)
from fabrica.features.web_content_fetching.application.dtos import FetchError


@pytest.mark.parametrize(
    ("content_type", "body", "match"),
    [
        (42, b"text", "Content-Type"),
        ("text/plain", "text", "body must be bytes"),
    ],
)
def test_classification_rejects_non_string_header_or_non_bytes_body(
    content_type: object,
    body: object,
    match: str,
) -> None:
    with pytest.raises(TypeError, match=match):
        classify_web_content(content_type, body)  # ty: ignore[invalid-argument-type]


def test_classification_treats_empty_text_as_non_binary() -> None:
    result = classify_web_content("text/plain", b"")

    assert not isinstance(result, FetchError)
    assert result.media_type == "text/plain"


@pytest.mark.parametrize(
    ("body", "declared_charset", "match"),
    [
        ("not-bytes", None, "body must be bytes"),
        (b"text", 42, "declared_charset"),
    ],
)
def test_decoding_rejects_invalid_argument_types(body: object, declared_charset: object, match: str) -> None:
    with pytest.raises(TypeError, match=match):
        decode_web_content(body, declared_charset=declared_charset)  # ty: ignore[invalid-argument-type]


def test_decoding_handles_utf16_and_utf32_boms() -> None:
    assert decode_web_content("Hello".encode("utf-16"), declared_charset=None) == "Hello"
    assert decode_web_content("Hello".encode("utf-32"), declared_charset=None) == "Hello"


def test_output_limiting_rejects_non_string_content() -> None:
    with pytest.raises(TypeError, match="content must be a string"):
        limit_web_content(42, max_chars=1)  # ty: ignore[invalid-argument-type]


def test_processing_adapter_delegates_to_pipeline() -> None:
    result = WebContentProcessingAdapter().process(
        b"content",
        content_type="text/plain",
        final_url="https://example.com",
        max_chars=10,
    )

    assert not isinstance(result, FetchError)
    assert result.content == "content"
