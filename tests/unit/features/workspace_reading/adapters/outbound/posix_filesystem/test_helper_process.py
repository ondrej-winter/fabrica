"""Tests for one-request POSIX helper-process outcomes."""

from pathlib import Path

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import helper_process
from fabrica.features.workspace_reading.application.dtos import (
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFilesLimits,
    TextFileResult,
)


class RecordingConnection:
    """In-memory stand-in for the helper's one-result connection endpoint."""

    def __init__(self) -> None:
        self.sent: list[object] = []
        self.closed = False

    def send(self, outcome: object) -> None:
        self.sent.append(outcome)

    def close(self) -> None:
        self.closed = True


def test_helper_process_reads_one_text_request_and_closes_its_result_connection(tmp_path: Path) -> None:
    (tmp_path / "source.py").write_text("first\nsecond\n", encoding="utf-8")
    connection = RecordingConnection()

    helper_process.read_one_file_in_helper(connection, str(tmp_path), ReadFileRequest("source.py"), ReadFilesLimits())

    assert connection.closed is True
    assert len(connection.sent) == 1
    outcome = connection.sent[0]
    assert isinstance(outcome, TextFileResult)
    assert outcome.path == "source.py"
    assert outcome.content == "1 | first\n2 | second"


def test_helper_process_maps_binary_and_missing_files_to_stable_failures(tmp_path: Path) -> None:
    (tmp_path / "binary.dat").write_bytes(b"\x00payload")
    binary_connection = RecordingConnection()
    missing_connection = RecordingConnection()

    helper_process.read_one_file_in_helper(
        binary_connection, str(tmp_path), ReadFileRequest("binary.dat"), ReadFilesLimits()
    )
    helper_process.read_one_file_in_helper(
        missing_connection, str(tmp_path), ReadFileRequest("missing.txt"), ReadFilesLimits()
    )

    binary_outcome = binary_connection.sent[0]
    missing_outcome = missing_connection.sent[0]
    assert isinstance(binary_outcome, ReadFileFailure)
    assert binary_outcome.error.code is ReadFileErrorCode.UNSUPPORTED_BINARY_FILE
    assert isinstance(missing_outcome, ReadFileFailure)
    assert missing_outcome.error.code is ReadFileErrorCode.NOT_FOUND
    assert binary_connection.closed is True
    assert missing_connection.closed is True
