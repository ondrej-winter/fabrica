"""Explicit output limiting for individual web-content responses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LimitedWebContent:
    """Head-preserved content with its complete truncation metadata."""

    content: str
    content_chars: int
    returned_chars: int
    truncated: bool


def limit_web_content(content: str, *, max_chars: int) -> LimitedWebContent:
    """Preserve the first max_chars characters and make truncation explicit."""
    if not isinstance(content, str):
        msg = "content must be a string"
        raise TypeError(msg)
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1:
        msg = "max_chars must be a positive integer"
        raise ValueError(msg)
    content_chars = len(content)
    returned = content[:max_chars]
    return LimitedWebContent(
        content=returned,
        content_chars=content_chars,
        returned_chars=len(returned),
        truncated=content_chars > max_chars,
    )


__all__ = ["LimitedWebContent", "limit_web_content"]
