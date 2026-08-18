"""Feature-neutral text rendering primitives for CLI output."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Mapping

MAX_OUTPUT_LINE_CHARS = 4_000
TRUNCATED_TEXT_MARKER = "...<truncated>"
C0_CONTROL_END_EXCLUSIVE = 32
DELETE_CONTROL = 127
C1_CONTROL_START = 128
C1_CONTROL_END = 159


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
    """Write raw already-formatted text and append a trailing newline when missing."""
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")


def format_metadata(metadata: Mapping[str, object]) -> str:
    """Format untrusted observation metadata as sorted bounded diagnostic fields."""
    if not metadata:
        return ""
    return bound_text(" ".join(f"{key}={value!s}" for key, value in sorted(metadata.items())))


def bound_text(text: str) -> str:
    """Return text escaped and bounded to one terminal-safe diagnostic line."""
    escaped_units = [_escape_diagnostic_character(character) for character in text]
    single_line_text = "".join(escaped_units)
    if len(single_line_text) <= MAX_OUTPUT_LINE_CHARS:
        return single_line_text
    content_length = MAX_OUTPUT_LINE_CHARS - len(TRUNCATED_TEXT_MARKER)
    return f"{_truncate_escaped_units(escaped_units, max_chars=content_length)}{TRUNCATED_TEXT_MARKER}"


def _escape_diagnostic_character(character: str) -> str:
    codepoint = ord(character)
    if character == "\n":
        return r"\n"
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


def _truncate_escaped_units(escaped_units: list[str], *, max_chars: int) -> str:
    truncated_units: list[str] = []
    current_length = 0
    for unit in escaped_units:
        next_length = current_length + len(unit)
        if next_length > max_chars:
            break
        truncated_units.append(unit)
        current_length = next_length
    return "".join(truncated_units)


__all__ = [
    "MAX_OUTPUT_LINE_CHARS",
    "TRUNCATED_TEXT_MARKER",
    "bound_text",
    "format_metadata",
    "write_line",
    "write_text",
]
