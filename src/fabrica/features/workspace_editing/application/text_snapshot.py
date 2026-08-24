"""Text byte decoding and rendering primitives for apply-patch planning."""

from dataclasses import dataclass
from enum import StrEnum

from fabrica.features.workspace_editing.application.errors import patch_error


class PatchTextEncoding(StrEnum):
    """Supported source text encodings distinguished at the byte boundary."""

    UTF8 = "utf-8"
    UTF8_BOM = "utf-8-bom"


class PatchLineEnding(StrEnum):
    """Uniform line-ending style used by one decoded text snapshot."""

    LF = "lf"
    CRLF = "crlf"


@dataclass(frozen=True, slots=True)
class PatchTextSnapshot:
    """Decoded UTF-8 file content with exact rendering semantics."""

    lines: tuple[str, ...]
    encoding: PatchTextEncoding
    line_ending: PatchLineEnding
    has_terminal_newline: bool

    def render(self, lines: tuple[str, ...] | None = None, *, has_terminal_newline: bool | None = None) -> bytes:
        """Render replacement lines using this snapshot's byte-level conventions."""
        rendered_lines = self.lines if lines is None else tuple(lines)
        rendered_has_terminal_newline = (
            self.has_terminal_newline if has_terminal_newline is None else has_terminal_newline
        )
        text = self.line_ending_text.join(rendered_lines)
        if rendered_has_terminal_newline and rendered_lines:
            text += self.line_ending_text
        prefix = b"\xef\xbb\xbf" if self.encoding is PatchTextEncoding.UTF8_BOM else b""
        return prefix + text.encode("utf-8")

    @property
    def line_ending_text(self) -> str:
        """Return the concrete line separator represented by the snapshot."""
        return "\r\n" if self.line_ending is PatchLineEnding.CRLF else "\n"


class PatchTextDecodingError(ValueError):
    """Structured rejection raised when source bytes are not supported text."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error = patch_error(code, message=message)


def decode_patch_text(source: bytes) -> PatchTextSnapshot:
    """Decode supported apply-patch source bytes without normalizing content."""
    if b"\x00" in source:
        code = "BINARY_FILE"
        message = "NUL bytes are not supported in patchable text files"
        raise PatchTextDecodingError(code, message)

    encoding = PatchTextEncoding.UTF8_BOM if source.startswith(b"\xef\xbb\xbf") else PatchTextEncoding.UTF8
    payload = source[3:] if encoding is PatchTextEncoding.UTF8_BOM else source
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as err:
        code = "UNSUPPORTED_ENCODING"
        message = "source bytes must be valid UTF-8"
        raise PatchTextDecodingError(code, message) from err

    line_ending = _detect_line_ending(text)
    lines, has_terminal_newline = _split_text_lines(text, line_ending)
    return PatchTextSnapshot(
        lines=lines,
        encoding=encoding,
        line_ending=line_ending,
        has_terminal_newline=has_terminal_newline,
    )


def render_added_text(lines: tuple[str, ...], *, line_ending: PatchLineEnding = PatchLineEnding.LF) -> bytes:
    """Render an Add File payload using v1 defaults: UTF-8, LF, no BOM."""
    if not lines:
        return b""
    separator = "\r\n" if line_ending is PatchLineEnding.CRLF else "\n"
    return separator.join(lines).encode("utf-8") + _ending_bytes(line_ending)


def _detect_line_ending(text: str) -> PatchLineEnding:
    contains_lf = "\n" in text
    contains_crlf = "\r\n" in text
    bare_lf_count = text.count("\n") - text.count("\r\n")
    if "\r" in text.replace("\r\n", "") or (contains_crlf and bare_lf_count > 0):
        code = "MIXED_LINE_ENDINGS_UNSUPPORTED"
        message = "mixed or bare-CR line endings are unsupported"
        raise PatchTextDecodingError(code, message)
    if contains_crlf:
        return PatchLineEnding.CRLF
    if contains_lf:
        return PatchLineEnding.LF
    return PatchLineEnding.LF


def _split_text_lines(text: str, line_ending: PatchLineEnding) -> tuple[tuple[str, ...], bool]:
    separator = "\r\n" if line_ending is PatchLineEnding.CRLF else "\n"
    if text == "":
        return (), False
    has_terminal_newline = text.endswith(separator)
    pieces = text.split(separator)
    if has_terminal_newline:
        pieces = pieces[:-1]
    return tuple(pieces), has_terminal_newline


def _ending_bytes(line_ending: PatchLineEnding) -> bytes:
    return b"\r\n" if line_ending is PatchLineEnding.CRLF else b"\n"


__all__ = [
    "PatchLineEnding",
    "PatchTextDecodingError",
    "PatchTextEncoding",
    "PatchTextSnapshot",
    "decode_patch_text",
    "render_added_text",
]
