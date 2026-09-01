"""Classify response content before it crosses into the web-content core."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from enum import StrEnum

from fabrica.features.web_content_fetching.application.dtos import FetchError, FetchErrorCode

_BINARY_SAMPLE_BYTES = 4_096
_ASCII_HORIZONTAL_TAB = 9
_ASCII_CARRIAGE_RETURN = 13
_ASCII_SPACE = 32
_MAX_BINARY_CONTROL_BYTE_RATIO = 0.05
_BINARY_MEDIA_TYPE_PREFIXES = (
    "audio/",
    "font/",
    "image/",
    "video/",
)
_BINARY_MEDIA_TYPES = frozenset(
    {
        "application/epub+zip",
        "application/gzip",
        "application/octet-stream",
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.ms-word",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/wasm",
        "application/x-7z-compressed",
        "application/x-bzip2",
        "application/x-rar-compressed",
        "application/x-tar",
        "application/x-zip-compressed",
        "application/zip",
    }
)


class WebContentKind(StrEnum):
    """Textual content families with dedicated extraction behavior."""

    HTML = "html"
    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"
    XML = "xml"


@dataclass(frozen=True, slots=True)
class ClassifiedWebContent:
    """Normalized media metadata for an accepted textual response."""

    media_type: str
    charset: str | None
    kind: WebContentKind


def classify_web_content(content_type: str, body: bytes) -> ClassifiedWebContent | FetchError:
    """Classify an HTTP body while rejecting binary or unsupported content."""
    if not isinstance(content_type, str):
        msg = "Content-Type must be a string"
        raise TypeError(msg)
    if not isinstance(body, bytes):
        msg = "body must be bytes"
        raise TypeError(msg)

    media_type, charset = _parse_content_type(content_type)
    kind = _content_kind(media_type)
    if kind is None or _is_declared_binary(media_type) or _looks_binary(body):
        return FetchError(
            code=FetchErrorCode.UNSUPPORTED_CONTENT_TYPE,
            message="The response content type is not supported as safe textual content",
            metadata={"media_type": media_type},
        )
    return ClassifiedWebContent(media_type=media_type, charset=charset, kind=kind)


def _parse_content_type(content_type: str) -> tuple[str, str | None]:
    """Parse header syntax without allowing parameter syntax to affect media type."""
    message = Message()
    message["content-type"] = content_type
    media_type = message.get_content_type().lower()
    charset = message.get_content_charset()
    return media_type, charset.lower() if charset is not None else None


def _content_kind(media_type: str) -> WebContentKind | None:
    """Return the processing family accepted for a normalized media type."""
    if media_type in {"text/html", "application/xhtml+xml"}:
        return WebContentKind.HTML
    if media_type == "application/json" or media_type.endswith("+json"):
        return WebContentKind.JSON
    if media_type in {"application/xml", "text/xml"} or media_type.endswith("+xml"):
        return WebContentKind.XML
    if media_type in {"text/markdown", "text/x-markdown", "text/md"}:
        return WebContentKind.MARKDOWN
    return WebContentKind.TEXT if media_type.startswith("text/") else None


def _is_declared_binary(media_type: str) -> bool:
    """Return whether a declared media type is never accepted as text."""
    return media_type in _BINARY_MEDIA_TYPES or media_type.startswith(_BINARY_MEDIA_TYPE_PREFIXES)


def _looks_binary(body: bytes) -> bool:
    """Detect obvious binary bytes without attempting content extraction."""
    sample = body[:_BINARY_SAMPLE_BYTES]
    if b"\x00" in sample:
        return True
    if not sample:
        return False
    control_bytes = sum(byte < _ASCII_HORIZONTAL_TAB or _ASCII_CARRIAGE_RETURN < byte < _ASCII_SPACE for byte in sample)
    return control_bytes / len(sample) > _MAX_BINARY_CONTROL_BYTE_RATIO


__all__ = ["ClassifiedWebContent", "WebContentKind", "classify_web_content"]
