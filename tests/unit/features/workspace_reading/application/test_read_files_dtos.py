"""Tests for workspace-reading application DTO contracts."""

from collections.abc import Callable
from typing import cast

import pytest

from fabrica.features.workspace_reading.application.dtos import (
    DEFAULT_MAX_FILES_PER_CALL,
    DEFAULT_MAX_IMAGE_BYTES,
    DEFAULT_MAX_LINE_CHARS,
    DEFAULT_MAX_METADATA_SCAN_LINES,
    DEFAULT_MAX_PARALLEL_READS,
    DEFAULT_MAX_READ_LINES,
    DEFAULT_MAX_READ_OUTPUT_CHARS,
    DEFAULT_MAX_TEXT_FILE_BYTES,
    DEFAULT_PER_FILE_DEADLINE_SECONDS,
    DEFAULT_TOOL_DEADLINE_SECONDS,
    ImageContent,
    ImageFileResult,
    ReadFileError,
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFilesCommand,
    ReadFilesLimits,
    ReadFilesResult,
    SafeReadMetadataValue,
    TextFileResult,
)

EXPECTED_MAX_FILES_PER_CALL = 20
EXPECTED_MAX_PARALLEL_READS = 8
EXPECTED_MAX_READ_LINES = 2_000
EXPECTED_MAX_LINE_CHARS = 2_000
EXPECTED_MAX_READ_OUTPUT_CHARS = 48_000
EXPECTED_MAX_TEXT_FILE_BYTES = 100_000_000
EXPECTED_MAX_IMAGE_BYTES = 10_000_000
EXPECTED_MAX_METADATA_SCAN_LINES = 50_000
EXPECTED_PER_FILE_DEADLINE_SECONDS = 10.0
EXPECTED_TOOL_DEADLINE_SECONDS = 20.0
EXPECTED_INITIAL_SIZE_BYTES = 10
EXPECTED_INEXACT_TOTAL_LINES = 50_000
EXPECTED_NEXT_START_LINE = 51


def test_read_files_limits_match_accepted_defaults() -> None:
    limits = ReadFilesLimits()

    assert limits.max_files_per_call == DEFAULT_MAX_FILES_PER_CALL == EXPECTED_MAX_FILES_PER_CALL
    assert limits.max_parallel_reads == DEFAULT_MAX_PARALLEL_READS == EXPECTED_MAX_PARALLEL_READS
    assert limits.max_read_lines == DEFAULT_MAX_READ_LINES == EXPECTED_MAX_READ_LINES
    assert limits.max_line_chars == DEFAULT_MAX_LINE_CHARS == EXPECTED_MAX_LINE_CHARS
    assert limits.max_output_chars_per_file == DEFAULT_MAX_READ_OUTPUT_CHARS == EXPECTED_MAX_READ_OUTPUT_CHARS
    assert limits.max_text_file_bytes == DEFAULT_MAX_TEXT_FILE_BYTES == EXPECTED_MAX_TEXT_FILE_BYTES
    assert limits.max_image_bytes == DEFAULT_MAX_IMAGE_BYTES == EXPECTED_MAX_IMAGE_BYTES
    assert limits.max_metadata_scan_lines == DEFAULT_MAX_METADATA_SCAN_LINES == EXPECTED_MAX_METADATA_SCAN_LINES
    assert limits.per_file_deadline_seconds == DEFAULT_PER_FILE_DEADLINE_SECONDS == EXPECTED_PER_FILE_DEADLINE_SECONDS
    assert limits.tool_deadline_seconds == DEFAULT_TOOL_DEADLINE_SECONDS == EXPECTED_TOOL_DEADLINE_SECONDS


def test_read_files_limits_reject_non_positive_bounds_and_deadlines() -> None:
    with pytest.raises(ValueError, match="max_files_per_call must be at least 1"):
        ReadFilesLimits(max_files_per_call=0)
    with pytest.raises(ValueError, match="read deadlines must be positive"):
        ReadFilesLimits(per_file_deadline_seconds=0)


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: ReadFileRequest(""), "blank"),
        (lambda: ReadFileRequest(" ../secret"), "leading or trailing whitespace"),
        (lambda: ReadFileRequest("/etc/passwd"), "workspace-relative"),
        (lambda: ReadFileRequest("src\\app.py"), "workspace-relative"),
        (lambda: ReadFileRequest("src/app.py", start_line=0), "one-based"),
        (lambda: ReadFileRequest("src/app.py", end_line=True), "one-based"),
        (lambda: ReadFileRequest("src/app.py", start_line=3, end_line=2), "less than or equal"),
        (lambda: ReadFilesLimits(max_parallel_reads=21), "must not exceed"),
        (lambda: ReadFilesLimits(tool_deadline_seconds=2, per_file_deadline_seconds=3), "must not be shorter"),
        (lambda: ReadFilesLimits(max_retries=2), "between 0 and 1"),
    ],
)
def test_request_and_limit_dtos_reject_invalid_values(factory: Callable[[], object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_batch_command_copies_requests_and_enforces_batch_bound() -> None:
    files = [ReadFileRequest("src/app.py")]
    command = ReadFilesCommand(files=tuple(files))
    files.append(ReadFileRequest("src/extra.py"))

    assert command.files == (ReadFileRequest("src/app.py"),)
    with pytest.raises(ValueError, match="must not be empty"):
        ReadFilesCommand(files=())
    with pytest.raises(ValueError, match="safe batch bound"):
        ReadFilesCommand(files=tuple(ReadFileRequest(f"src/{index}.py") for index in range(21)))


def test_error_codes_match_complete_version_one_contract_and_metadata_is_safe() -> None:
    assert {code.value for code in ReadFileErrorCode} == {
        "INVALID_INPUT",
        "INVALID_PATH",
        "PATH_OUTSIDE_WORKSPACE",
        "NOT_FOUND",
        "NOT_A_FILE",
        "INVALID_RANGE",
        "PERMISSION_DENIED",
        "FILE_TOO_LARGE",
        "UNSUPPORTED_BINARY_FILE",
        "UNSUPPORTED_ENCODING",
        "IMAGE_TOO_LARGE",
        "IMAGE_INPUT_UNSUPPORTED",
        "READ_TIMEOUT",
        "READ_CANCELLED",
        "IO_ERROR",
    }
    metadata = {"size_bytes": 10}
    error = ReadFileError(ReadFileErrorCode.FILE_TOO_LARGE, metadata=metadata)
    metadata["size_bytes"] = 20

    assert error.metadata["size_bytes"] == EXPECTED_INITIAL_SIZE_BYTES
    with pytest.raises(TypeError, match="scalar"):
        ReadFileError(
            ReadFileErrorCode.IO_ERROR,
            metadata=cast("dict[str, SafeReadMetadataValue]", {"detail": object()}),
        )
    with pytest.raises(ValueError, match="safe identifiers"):
        ReadFileError(ReadFileErrorCode.IO_ERROR, metadata={"not safe": 1})


def test_text_result_represents_exact_and_bounded_inexact_line_totals() -> None:
    exact = TextFileResult(
        path="src/app.py",
        content="1 | value = 1",
        start_line=1,
        end_line=1,
        complete=True,
        next_start_line=None,
        total_lines=1,
        total_lines_exact=True,
    )
    inexact = TextFileResult(
        path="src/large.py",
        content="50 | value",
        start_line=50,
        end_line=50,
        complete=False,
        next_start_line=EXPECTED_NEXT_START_LINE,
        total_lines=EXPECTED_INEXACT_TOTAL_LINES,
        total_lines_exact=False,
        truncated_lines=(50,),
    )

    assert exact.total_lines_exact is True
    assert inexact.total_lines == EXPECTED_INEXACT_TOTAL_LINES
    assert inexact.next_start_line == EXPECTED_NEXT_START_LINE
    with pytest.raises(ValueError, match="pagination metadata"):
        TextFileResult(
            path="src/app.py",
            content="1 | x",
            start_line=1,
            end_line=1,
            complete=True,
            next_start_line=2,
            total_lines=1,
            total_lines_exact=True,
        )
    with pytest.raises(ValueError, match="immediately follow"):
        TextFileResult(
            path="src/app.py",
            content="1 | x",
            start_line=1,
            end_line=1,
            complete=False,
            next_start_line=3,
            total_lines=2,
            total_lines_exact=True,
        )
    with pytest.raises(ValueError, match="ordered and unique"):
        TextFileResult(
            path="src/app.py",
            content="1 | x",
            start_line=1,
            end_line=2,
            complete=True,
            next_start_line=None,
            total_lines=2,
            total_lines_exact=True,
            truncated_lines=(2, 1),
        )


def test_image_and_batch_result_dtos_keep_content_provider_neutral() -> None:
    image = ImageContent("images/diagram.png", "image/png", b"png-bytes")
    success = ImageFileResult("images/diagram.png", image)
    failure = ReadFileFailure("missing.txt", ReadFileError(ReadFileErrorCode.NOT_FOUND))
    result = ReadFilesResult((success, failure))

    assert result.results == (success, failure)
    assert success.image.data == b"png-bytes"
    with pytest.raises(ValueError, match="supported image type"):
        ImageContent("images/diagram.bmp", "image/bmp", b"bmp")
    with pytest.raises(ValueError, match="must match"):
        ImageFileResult("images/other.png", image)
    with pytest.raises(ValueError, match="must not be empty"):
        ReadFilesResult(())
