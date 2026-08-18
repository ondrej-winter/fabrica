"""Feature-neutral text rendering primitives for CLI output."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Mapping

MAX_OUTPUT_LINE_CHARS = 4_000
TRUNCATED_TEXT_MARKER = "...<truncated>"


def write_line(stream: TextIO, text: str) -> None:
    """Write one bounded logical line to a CLI stream.

    Embedded line breaks are escaped and long content is truncated so a single
    observation or metadata field cannot create unbounded multi-line output.
    """
    bounded = bound_text(text)
    stream.write(bounded)
    if not bounded.endswith("\n"):
        stream.write("\n")


def write_text(stream: TextIO, text: str) -> None:
    """Write already-formatted text and append a trailing newline when missing."""
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")


def format_metadata(metadata: Mapping[str, object]) -> str:
    """Format safe observation metadata as sorted bounded key-value fields."""
    if not metadata:
        return ""
    return bound_text(" ".join(f"{key}={value!s}" for key, value in sorted(metadata.items())))


def bound_text(text: str) -> str:
    """Return text bounded to one safe CLI output line."""
    single_line_text = text.replace("\r", r"\r").replace("\n", r"\n")
    if len(single_line_text) <= MAX_OUTPUT_LINE_CHARS:
        return single_line_text
    content_length = MAX_OUTPUT_LINE_CHARS - len(TRUNCATED_TEXT_MARKER)
    return f"{single_line_text[:content_length]}{TRUNCATED_TEXT_MARKER}"


__all__ = [
    "MAX_OUTPUT_LINE_CHARS",
    "TRUNCATED_TEXT_MARKER",
    "bound_text",
    "format_metadata",
    "write_line",
    "write_text",
]
