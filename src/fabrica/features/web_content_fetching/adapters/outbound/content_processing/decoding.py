"""Strict response-text decoding for public web content."""

from __future__ import annotations

from codecs import BOM_UTF8, BOM_UTF16_BE, BOM_UTF16_LE, BOM_UTF32_BE, BOM_UTF32_LE

from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode


def decode_web_content(body: bytes, *, declared_charset: str | None) -> str | FetchError:
    """Decode bytes using BOM, then declared charset, then UTF-8 without replacement."""
    if not isinstance(body, bytes):
        msg = "body must be bytes"
        raise TypeError(msg)
    if declared_charset is not None and not isinstance(declared_charset, str):
        msg = "declared_charset must be a string or None"
        raise TypeError(msg)

    encoding = _bom_encoding(body) or declared_charset or "utf-8"
    try:
        return body.decode(encoding)
    except LookupError, UnicodeDecodeError:
        return FetchError(
            code=FetchErrorCode.UNSUPPORTED_ENCODING,
            message="The response body could not be decoded reliably",
        )


def _bom_encoding(body: bytes) -> str | None:
    """Return the Unicode encoding identified by a leading byte-order marker."""
    if body.startswith(BOM_UTF8):
        return "utf-8-sig"
    if body.startswith((BOM_UTF32_LE, BOM_UTF32_BE)):
        return "utf-32"
    if body.startswith((BOM_UTF16_LE, BOM_UTF16_BE)):
        return "utf-16"
    return None


__all__ = ["decode_web_content"]
