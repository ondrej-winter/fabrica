"""Tests for bounded descriptor-backed UTF-8 text reading."""

from pathlib import Path

import pytest

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import (
    PosixTextFileReader,
    TextFileTooLargeError,
    UnsupportedTextEncodingError,
    open_workspace_file,
)
from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits

MAX_SIZE_BYTES = 4
SOURCE_SIZE_BYTES = 5


def test_reader_reports_empty_complete_result_when_start_line_is_past_eof(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_text("only line", encoding="utf-8")

    with open_workspace_file(tmp_path, "source.txt") as opened:
        result = PosixTextFileReader().read(
            opened, path="source.txt", start_line=2, end_line=None, limits=ReadFilesLimits()
        )

    assert result.content == ""
    assert result.start_line is None
    assert result.end_line is None
    assert result.complete is True
    assert result.total_lines == 1
    assert result.total_lines_exact is True


def test_reader_rejects_oversized_files_before_decoding(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(b"12345")

    with open_workspace_file(tmp_path, "source.txt") as opened, pytest.raises(TextFileTooLargeError) as exc_info:
        PosixTextFileReader().read(
            opened,
            path="source.txt",
            start_line=None,
            end_line=None,
            limits=ReadFilesLimits(max_text_file_bytes=MAX_SIZE_BYTES),
        )

    assert exc_info.value.size_bytes == SOURCE_SIZE_BYTES
    assert exc_info.value.max_size_bytes == MAX_SIZE_BYTES


def test_reader_translates_invalid_utf8_from_streaming_decode(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes(b"valid\n\xff")

    with open_workspace_file(tmp_path, "source.txt") as opened, pytest.raises(UnsupportedTextEncodingError):
        PosixTextFileReader().read(opened, path="source.txt", start_line=None, end_line=None, limits=ReadFilesLimits())
