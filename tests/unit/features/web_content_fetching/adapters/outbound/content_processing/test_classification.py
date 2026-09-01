"""Tests for safe textual web-content classification."""

import pytest

from fabrica.features.web_content_fetching.adapters.outbound.content_processing import (
    ClassifiedWebContent,
    WebContentKind,
    classify_web_content,
)
from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode


@pytest.mark.parametrize(
    ("content_type", "kind"),
    [
        ("text/html; charset=UTF-8", WebContentKind.HTML),
        ("application/xhtml+xml", WebContentKind.HTML),
        ("application/problem+json", WebContentKind.JSON),
        ("application/xml", WebContentKind.XML),
        ("text/markdown", WebContentKind.MARKDOWN),
        ("text/plain", WebContentKind.TEXT),
    ],
)
def test_classify_web_content_accepts_supported_textual_families(content_type: str, kind: WebContentKind) -> None:
    result = classify_web_content(content_type, b"plain textual body")

    assert result == ClassifiedWebContent(
        content_type.split(";", maxsplit=1)[0],
        "utf-8" if ";" in content_type else None,
        kind,
    )


@pytest.mark.parametrize(
    "content_type",
    ["image/png", "application/pdf", "application/zip", "application/octet-stream"],
)
def test_classify_web_content_rejects_declared_binary_types(content_type: str) -> None:
    result = classify_web_content(content_type, b"text cannot override a binary declaration")

    assert isinstance(result, FetchError)
    assert result.code is FetchErrorCode.UNSUPPORTED_CONTENT_TYPE


def test_classify_web_content_rejects_binary_bytes_despite_text_declaration() -> None:
    result = classify_web_content("text/plain", b"safe prefix\x00unsafe binary suffix")

    assert isinstance(result, FetchError)
    assert result.code is FetchErrorCode.UNSUPPORTED_CONTENT_TYPE
