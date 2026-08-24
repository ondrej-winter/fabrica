"""Byte-level tests for apply-patch text snapshot decoding and rendering."""

import pytest

from fabrica.features.workspace_editing.application import (
    PatchLineEnding,
    PatchTextDecodingError,
    PatchTextEncoding,
    decode_patch_text,
    render_added_text,
)


def test_decode_patch_text_preserves_utf8_bom_crlf_and_terminal_newline() -> None:
    source = b"\xef\xbb\xbffirst\r\nsecond\r\n"

    snapshot = decode_patch_text(source)

    assert snapshot.encoding is PatchTextEncoding.UTF8_BOM
    assert snapshot.line_ending is PatchLineEnding.CRLF
    assert snapshot.lines == ("first", "second")
    assert snapshot.has_terminal_newline is True
    assert snapshot.render(("changed",), has_terminal_newline=True) == b"\xef\xbb\xbfchanged\r\n"


def test_decode_patch_text_preserves_no_terminal_newline() -> None:
    snapshot = decode_patch_text(b"alpha\nbeta")

    assert snapshot.encoding is PatchTextEncoding.UTF8
    assert snapshot.line_ending is PatchLineEnding.LF
    assert snapshot.lines == ("alpha", "beta")
    assert snapshot.has_terminal_newline is False
    assert snapshot.render(("alpha", "gamma")) == b"alpha\ngamma"


def test_decode_patch_text_represents_empty_file_exactly() -> None:
    snapshot = decode_patch_text(b"")

    assert snapshot.lines == ()
    assert snapshot.has_terminal_newline is False
    assert snapshot.render() == b""


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        (b"text\x00tail", "BINARY_FILE"),
        (b"\xff", "UNSUPPORTED_ENCODING"),
        (b"one\ntwo\r\n", "MIXED_LINE_ENDINGS_UNSUPPORTED"),
        (b"one\rtwo", "MIXED_LINE_ENDINGS_UNSUPPORTED"),
    ],
)
def test_decode_patch_text_rejects_unsupported_source_bytes(source: bytes, expected_code: str) -> None:
    with pytest.raises(PatchTextDecodingError) as exc_info:
        decode_patch_text(source)

    assert exc_info.value.error.code == expected_code


def test_render_added_text_uses_utf8_lf_terminal_newline_by_default() -> None:
    assert render_added_text(("snowman = '☃'",)) == "snowman = '☃'\n".encode()
    assert render_added_text(()) == b""
    assert render_added_text(("a", "b"), line_ending=PatchLineEnding.CRLF) == b"a\r\nb\r\n"
