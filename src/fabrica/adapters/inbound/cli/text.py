"""Feature-neutral text formatting primitives for CLI adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Mapping

MAX_OUTPUT_LINE_CHARS = 4_000


def write_line(stream: TextIO, text: str) -> None:
    """Write one bounded text line to a CLI stream."""
    bounded = bound_text(text)
    stream.write(bounded)
    if not bounded.endswith("\n"):
        stream.write("\n")


def write_text(stream: TextIO, text: str) -> None:
    """Write text to a CLI stream and terminate it with a newline when missing."""
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")


def format_metadata(metadata: Mapping[str, object]) -> str:
    """Format safe observation metadata as sorted key-value fields."""
    if not metadata:
        return ""
    return " ".join(f"{key}={bound_text(str(value))}" for key, value in sorted(metadata.items()))


def bound_text(text: str) -> str:
    """Return text bounded to one safe CLI output line."""
    if len(text) <= MAX_OUTPUT_LINE_CHARS:
        return text
    return f"{text[:MAX_OUTPUT_LINE_CHARS]}...<truncated>"


__all__ = [
    "MAX_OUTPUT_LINE_CHARS",
    "bound_text",
    "format_metadata",
    "write_line",
    "write_text",
]
