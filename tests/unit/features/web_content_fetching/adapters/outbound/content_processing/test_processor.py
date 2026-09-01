"""Tests for composition failure paths in web-content processing."""

import pytest

from fabrica.features.web_content_fetching.adapters.outbound.content_processing import processor
from fabrica.features.web_content_fetching.adapters.outbound.content_processing.classification import (
    ClassifiedWebContent,
    WebContentKind,
)
from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode


@pytest.mark.parametrize("stage", ["classification", "decoding", "extraction"])
def test_process_web_content_returns_each_stage_error_unchanged(monkeypatch: pytest.MonkeyPatch, stage: str) -> None:
    error = FetchError(FetchErrorCode.UNSUPPORTED_CONTENT_TYPE)
    classified = ClassifiedWebContent("text/plain", "utf-8", WebContentKind.TEXT)

    def classify(content_type: str, body: bytes) -> ClassifiedWebContent | FetchError:
        del content_type, body
        return error if stage == "classification" else classified

    def decode(body: bytes, *, declared_charset: str | None) -> str | FetchError:
        del body, declared_charset
        return error if stage == "decoding" else "content"

    def extract(content: str, *, kind: WebContentKind, final_url: str) -> FetchError:
        del content, kind, final_url
        if stage != "extraction":
            pytest.fail("extraction should not succeed")
        return error

    monkeypatch.setattr(
        processor,
        "classify_web_content",
        classify,
    )
    monkeypatch.setattr(processor, "decode_web_content", decode)
    monkeypatch.setattr(processor, "extract_web_content", extract)

    result = processor.process_web_content(
        b"content", content_type="text/plain", final_url="https://example.com", max_chars=1_000
    )

    assert result is error
