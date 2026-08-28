"""Stream bounded UTF-8 text reads from securely opened workspace descriptors."""

import io
import os
from collections.abc import Iterator
from dataclasses import dataclass

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.path_resolution import OpenedWorkspaceFile
from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits, TextFileResult
from fabrica.features.workspace_reading.application.text_formatting import format_text_lines
from fabrica.features.workspace_reading.application.validation import normalize_text_line_range


class TextFileTooLargeError(ValueError):
    """Raised before reading a text file that exceeds the configured byte bound."""

    def __init__(self, *, size_bytes: int, max_size_bytes: int) -> None:
        """Initialize the stable size-limit failure details."""
        super().__init__("text file exceeds the configured byte limit")
        self.size_bytes = size_bytes
        self.max_size_bytes = max_size_bytes


class UnsupportedTextEncodingError(ValueError):
    """Raised when streamed source bytes are not UTF-8 or UTF-8 BOM text."""

    def __init__(self) -> None:
        """Initialize the stable text-encoding failure message."""
        super().__init__("text files must be valid UTF-8")


@dataclass(frozen=True, slots=True)
class PosixTextFileReader:
    """Read bounded text and metadata through an already-secure file descriptor."""

    def read(
        self,
        opened_file: OpenedWorkspaceFile,
        *,
        path: str,
        start_line: int | None,
        end_line: int | None,
        limits: ReadFilesLimits,
    ) -> TextFileResult:
        """Stream one UTF-8 text result without materializing the whole file."""
        size_bytes = opened_file.stat_result.st_size
        if size_bytes > limits.max_text_file_bytes:
            raise TextFileTooLargeError(size_bytes=size_bytes, max_size_bytes=limits.max_text_file_bytes)

        line_range = normalize_text_line_range(start_line, end_line)
        try:
            with _open_text_stream(opened_file.file_descriptor) as stream:
                formatted = format_text_lines(_logical_lines(stream), line_range=line_range, limits=limits)
            total_lines, total_lines_exact = _count_lines(opened_file.file_descriptor, limits=limits)
        except UnicodeDecodeError as err:
            raise UnsupportedTextEncodingError from err

        if formatted.start_line is None or formatted.end_line is None:
            return TextFileResult(
                path=path,
                content=formatted.content,
                start_line=None,
                end_line=None,
                complete=formatted.complete,
                next_start_line=formatted.next_start_line,
                total_lines=total_lines,
                total_lines_exact=total_lines_exact,
                truncated_lines=formatted.truncated_lines,
            )
        return TextFileResult(
            path=path,
            content=formatted.content,
            start_line=formatted.start_line,
            end_line=formatted.end_line,
            complete=formatted.complete,
            next_start_line=formatted.next_start_line,
            total_lines=total_lines,
            total_lines_exact=total_lines_exact,
            truncated_lines=formatted.truncated_lines,
        )


def _count_lines(file_descriptor: int, *, limits: ReadFilesLimits) -> tuple[int, bool]:
    """Count lines only until EOF or the configured metadata ceiling."""
    line_count = 0
    with _open_text_stream(file_descriptor) as stream:
        for line_number, _line in enumerate(stream, start=1):
            line_count = line_number
            if line_number == limits.max_metadata_scan_lines:
                try:
                    next(stream)
                except StopIteration:
                    return line_number, True
                return line_number, False
    return line_count, True


def _open_text_stream(file_descriptor: int) -> io.TextIOWrapper:
    """Return an independent newline-normalizing UTF-8 stream for one descriptor."""
    duplicated_descriptor = os.dup(file_descriptor)
    os.lseek(duplicated_descriptor, 0, os.SEEK_SET)
    raw_stream = os.fdopen(duplicated_descriptor, "rb")
    return io.TextIOWrapper(raw_stream, encoding="utf-8-sig", newline=None)


def _logical_lines(stream: io.TextIOWrapper) -> Iterator[str]:
    """Yield source lines without their normalized line terminators."""
    yield from (line.removesuffix("\n") for line in stream)


__all__ = ["PosixTextFileReader", "TextFileTooLargeError", "UnsupportedTextEncodingError"]
