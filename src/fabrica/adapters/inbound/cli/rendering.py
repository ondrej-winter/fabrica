"""Feature-neutral text rendering primitives for CLI output."""

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Mapping

MAX_OUTPUT_LINE_CHARS = 4_000
TRUNCATED_TEXT_MARKER = "...<truncated>"
C0_CONTROL_END_EXCLUSIVE = 32
DELETE_CONTROL = 127
C1_CONTROL_START = 128
C1_CONTROL_END = 159
MAX_METADATA_FIELDS = 50


def write_line(stream: TextIO, text: str) -> None:
    """Write one bounded diagnostic line to a CLI stream.

    Embedded line breaks and terminal controls are escaped, and long content is
    truncated so a single observation or metadata field cannot create unbounded
    or terminal-active output.
    """
    bounded = bound_text(text)
    stream.write(bounded)
    if not bounded.endswith("\n"):
        stream.write("\n")


def write_text(stream: TextIO, text: str) -> None:
    """Write terminal-safe text and append a trailing newline when missing."""
    rendered = terminal_safe_text(text)
    stream.write(rendered)
    if not rendered.endswith("\n"):
        stream.write("\n")


def format_metadata(metadata: Mapping[str, object]) -> str:
    """Format untrusted observation metadata as sorted bounded diagnostic fields."""
    if not metadata:
        return ""
    fields = (f"{key}={value!s}" for key, value in bounded_metadata_items(metadata))
    suffix = " metadata_fields_truncated=true" if len(metadata) > MAX_METADATA_FIELDS else ""
    return bound_text(f"{' '.join(fields)}{suffix}")


def bound_text(text: str) -> str:
    """Return text escaped and bounded to one terminal-safe diagnostic line."""
    return _bound_text(text, max_chars=MAX_OUTPUT_LINE_CHARS, preserve_line_breaks=False)


def bound_multiline_text(text: str) -> str:
    """Return escaped terminal-safe text while preserving ordinary newlines."""
    return _bound_text(text, max_chars=MAX_OUTPUT_LINE_CHARS, preserve_line_breaks=True)


def terminal_safe_text(text: str) -> str:
    """Return unbounded text with terminal-active control characters escaped."""
    return "".join(_escape_diagnostic_character(character, preserve_line_breaks=True) for character in text)


def _bound_text(text: str, *, max_chars: int, preserve_line_breaks: bool) -> str:
    bounded_units: list[str] = []
    current_length = 0
    for character in text:
        unit = _escape_diagnostic_character(character, preserve_line_breaks=preserve_line_breaks)
        next_length = current_length + len(unit)
        if next_length > max_chars:
            while bounded_units and current_length + len(TRUNCATED_TEXT_MARKER) > max_chars:
                removed_unit = bounded_units.pop()
                current_length -= len(removed_unit)
            bounded_units.append(TRUNCATED_TEXT_MARKER)
            break
        bounded_units.append(unit)
        current_length = next_length
    return "".join(bounded_units)


def bounded_metadata_items(metadata: Mapping[str, object]) -> list[tuple[str, object]]:
    """Return deterministic metadata items without materializing every sorted field."""
    return heapq.nsmallest(MAX_METADATA_FIELDS, metadata.items(), key=lambda item: item[0])


def _escape_diagnostic_character(character: str, *, preserve_line_breaks: bool = False) -> str:
    codepoint = ord(character)
    if character == "\n":
        return "\n" if preserve_line_breaks else r"\n"
    if character == "\r":
        return r"\r"
    if character == "\t":
        return r"\t"
    if (
        codepoint < C0_CONTROL_END_EXCLUSIVE
        or codepoint == DELETE_CONTROL
        or C1_CONTROL_START <= codepoint <= C1_CONTROL_END
    ):
        return f"\\x{codepoint:02x}"
    return character


__all__ = [
    "MAX_OUTPUT_LINE_CHARS",
    "TRUNCATED_TEXT_MARKER",
    "bound_multiline_text",
    "bound_text",
    "format_metadata",
    "terminal_safe_text",
    "write_line",
    "write_text",
]
