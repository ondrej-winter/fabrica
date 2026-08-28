"""Integration tests for streamed POSIX workspace text reading."""

import sys
from pathlib import Path

import pytest

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import (
    PosixTextFileReader,
    open_workspace_file,
)
from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits

pytestmark = pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX adapter targets macOS/Linux")

THIRD_LINE = 3


def test_reader_preserves_line_numbers_for_bom_crlf_unicode_and_no_terminal_newline(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_bytes("\ufefffirst\r\nsecond 😀\r\nthird".encode())

    with open_workspace_file(tmp_path, "source.txt") as opened:
        result = PosixTextFileReader().read(
            opened, path="source.txt", start_line=2, end_line=None, limits=ReadFilesLimits()
        )

    assert result.content == "2 | second 😀\n3 | third"
    assert (result.start_line, result.end_line) == (2, 3)
    assert result.total_lines == THIRD_LINE
    assert result.total_lines_exact is True


def test_reader_enforces_output_and_line_caps_with_explicit_pagination(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_text("first\nsecond\nabcdefgh", encoding="utf-8")
    limits = ReadFilesLimits(max_output_chars_per_file=20)

    with open_workspace_file(tmp_path, "source.txt") as opened:
        result = PosixTextFileReader().read(opened, path="source.txt", start_line=None, end_line=None, limits=limits)

    assert result.content == "1 | first\n2 | second"
    assert result.complete is False
    assert result.next_start_line == THIRD_LINE
    assert result.truncated_lines == ()


@pytest.mark.parametrize(
    ("line_count", "expected_total", "expected_exactness"),
    [(3, 3, "exact"), (4, 3, "inexact")],
)
def test_reader_bounds_total_line_scanning_at_metadata_ceiling(
    tmp_path: Path, line_count: int, expected_total: int, expected_exactness: str
) -> None:
    path = tmp_path / "source.txt"
    path.write_text("\n".join(f"line {number}" for number in range(1, line_count + 1)), encoding="utf-8")
    limits = ReadFilesLimits(max_metadata_scan_lines=3)

    with open_workspace_file(tmp_path, "source.txt") as opened:
        result = PosixTextFileReader().read(opened, path="source.txt", start_line=1, end_line=1, limits=limits)

    assert result.content == "1 | line 1"
    assert result.total_lines == expected_total
    assert result.total_lines_exact is (expected_exactness == "exact")


def test_reader_marks_long_lines_without_making_an_eof_read_incomplete(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    path.write_text("abcdefgh", encoding="utf-8")

    with open_workspace_file(tmp_path, "source.txt") as opened:
        result = PosixTextFileReader().read(
            opened,
            path="source.txt",
            start_line=None,
            end_line=None,
            limits=ReadFilesLimits(max_line_chars=3),
        )

    assert result.content == "1 | abc … [line truncated]"
    assert result.complete is True
    assert result.truncated_lines == (1,)
