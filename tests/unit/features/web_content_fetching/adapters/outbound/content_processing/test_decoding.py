"""Tests for deterministic response text decoding."""

import pytest

from fabrica.features.web_content_fetching.adapters.outbound.content_processing import decode_web_content
from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode


def test_decode_web_content_prefers_a_bom_to_a_conflicting_declared_charset() -> None:
    result = decode_web_content(b"\xef\xbb\xbfHello", declared_charset="ascii")

    assert result == "Hello"


def test_decode_web_content_uses_a_declared_supported_charset() -> None:
    result = decode_web_content("café".encode("iso-8859-1"), declared_charset="iso-8859-1")

    assert result == "café"


@pytest.mark.parametrize(("body", "charset"), [(b"\xff", None), (b"text", "not-a-real-charset")])
def test_decode_web_content_rejects_unreliable_decoding(body: bytes, charset: str | None) -> None:
    result = decode_web_content(body, declared_charset=charset)

    assert isinstance(result, FetchError)
    assert result.code is FetchErrorCode.UNSUPPORTED_ENCODING
