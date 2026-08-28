"""Tests for one-request POSIX helper-process outcomes."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import helper_process
from fabrica.features.workspace_reading.application.dtos import (
    ImageFileResult,
    ReadFileError,
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFilesLimits,
    TextFileResult,
)
from fabrica.features.workspace_reading.application.ports import WorkspaceReadContext


class RecordingConnection:
    """In-memory stand-in for the helper's one-result connection endpoint."""

    def __init__(self) -> None:
        self.sent: list[object] = []
        self.closed = False

    def send(self, outcome: object) -> None:
        self.sent.append(outcome)

    def close(self) -> None:
        self.closed = True


class NeverCancelled:
    """Cancellation signal that stays inactive for one helper test."""

    @property
    def is_cancelled(self) -> bool:
        return False


class Cancelled:
    """Cancellation signal that immediately stops one helper test."""

    @property
    def is_cancelled(self) -> bool:
        return True


class ParentConnection:
    """Parent pipe endpoint with a scripted readiness and receive outcome."""

    def __init__(self, *, ready: bool | tuple[bool, ...], outcome: object | None = None) -> None:
        self.readiness = iter(ready) if isinstance(ready, tuple) else None
        self.ready = ready if isinstance(ready, bool) else False
        self.outcome = outcome
        self.closed = False

    def poll(self) -> bool:
        if self.readiness is not None:
            return next(self.readiness)
        return self.ready

    def recv(self) -> object:
        return self.outcome

    def close(self) -> None:
        self.closed = True


class ChildConnection:
    """Child pipe endpoint that records closure after process startup."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class RecordingProcess:
    """Process fake that records supervisor lifecycle operations."""

    def __init__(self, *, alive: bool = True) -> None:
        self.started = False
        self.terminated = False
        self.joined = False
        self.alive = alive

    def start(self) -> None:
        self.started = True

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminated = True

    def join(self) -> None:
        self.joined = True


def test_helper_process_reads_one_text_request_and_closes_its_result_connection(tmp_path: Path) -> None:
    (tmp_path / "source.py").write_text("first\nsecond\n", encoding="utf-8")
    connection = RecordingConnection()

    helper_process.read_one_file_in_helper(
        connection,
        str(tmp_path),
        ReadFileRequest("source.py"),
        image_input_supported=False,
        limits=ReadFilesLimits(),
    )

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
        binary_connection,
        str(tmp_path),
        ReadFileRequest("binary.dat"),
        image_input_supported=False,
        limits=ReadFilesLimits(),
    )
    helper_process.read_one_file_in_helper(
        missing_connection,
        str(tmp_path),
        ReadFileRequest("missing.txt"),
        image_input_supported=False,
        limits=ReadFilesLimits(),
    )

    binary_outcome = binary_connection.sent[0]
    missing_outcome = missing_connection.sent[0]
    assert isinstance(binary_outcome, ReadFileFailure)
    assert binary_outcome.error.code is ReadFileErrorCode.UNSUPPORTED_BINARY_FILE
    assert isinstance(missing_outcome, ReadFileFailure)
    assert missing_outcome.error.code is ReadFileErrorCode.NOT_FOUND
    assert binary_connection.closed is True
    assert missing_connection.closed is True


def test_helper_process_returns_verified_images_only_when_the_model_supports_images(tmp_path: Path) -> None:
    (tmp_path / "diagram.txt").write_bytes(b"\x89PNG\r\n\x1a\nverified")
    supported_connection = RecordingConnection()
    unsupported_connection = RecordingConnection()

    helper_process.read_one_file_in_helper(
        supported_connection,
        str(tmp_path),
        ReadFileRequest("diagram.txt"),
        image_input_supported=True,
        limits=ReadFilesLimits(),
    )
    helper_process.read_one_file_in_helper(
        unsupported_connection,
        str(tmp_path),
        ReadFileRequest("diagram.txt"),
        image_input_supported=False,
        limits=ReadFilesLimits(),
    )

    supported_outcome = supported_connection.sent[0]
    unsupported_outcome = unsupported_connection.sent[0]
    assert isinstance(supported_outcome, ImageFileResult)
    assert supported_outcome.image.media_type == "image/png"
    assert supported_outcome.image.data == b"\x89PNG\r\n\x1a\nverified"
    assert isinstance(unsupported_outcome, ReadFileFailure)
    assert unsupported_outcome.error.code is ReadFileErrorCode.IMAGE_INPUT_UNSUPPORTED


def test_supervisor_returns_helper_outcomes_and_cleans_up_process_resources(monkeypatch, tmp_path: Path) -> None:
    expected = ReadFileFailure("source.py", ReadFileError(ReadFileErrorCode.NOT_FOUND))
    parent = ParentConnection(ready=True, outcome=expected)
    child = ChildConnection()
    process = RecordingProcess()
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", _pipe_factory(parent, child))
    reader = helper_process.PosixHelperProcessFileReader(tmp_path, process_factory=lambda **_kwargs: process)

    outcome = asyncio.run(reader.read_file(ReadFileRequest("source.py"), _context(NeverCancelled())))

    assert outcome is expected
    assert process.started is True
    assert process.terminated is True
    assert process.joined is True
    assert parent.closed is True
    assert child.closed is True


def test_supervisor_waits_for_a_later_helper_outcome(monkeypatch, tmp_path: Path) -> None:
    expected = ReadFileFailure("source.py", ReadFileError(ReadFileErrorCode.NOT_FOUND))
    parent = ParentConnection(ready=(False, True), outcome=expected)
    child = ChildConnection()
    process = RecordingProcess()
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", _pipe_factory(parent, child))
    reader = helper_process.PosixHelperProcessFileReader(tmp_path, process_factory=lambda **_kwargs: process)

    outcome = asyncio.run(reader.read_file(ReadFileRequest("source.py"), _context(NeverCancelled())))

    assert outcome is expected


def test_supervisor_maps_malformed_output_and_cancellation_to_stable_failures(monkeypatch, tmp_path: Path) -> None:
    malformed_parent = ParentConnection(ready=True, outcome=object())
    cancelled_parent = ParentConnection(ready=False)
    child = ChildConnection()
    processes = [RecordingProcess(), RecordingProcess()]
    parents = [(malformed_parent, child), (cancelled_parent, ChildConnection())]
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", _queued_pipe_factory(parents))
    reader = helper_process.PosixHelperProcessFileReader(tmp_path, process_factory=lambda **_kwargs: processes.pop(0))

    malformed = asyncio.run(reader.read_file(ReadFileRequest("source.py"), _context(NeverCancelled())))
    cancelled = asyncio.run(reader.read_file(ReadFileRequest("source.py"), _context(Cancelled())))

    assert isinstance(malformed, ReadFileFailure)
    assert malformed.error.code is ReadFileErrorCode.IO_ERROR
    assert isinstance(cancelled, ReadFileFailure)
    assert cancelled.error.code is ReadFileErrorCode.READ_CANCELLED


def test_supervisor_joins_an_exited_helper_without_terminating_it(monkeypatch, tmp_path: Path) -> None:
    parent = ParentConnection(
        ready=True, outcome=ReadFileFailure("source.py", ReadFileError(ReadFileErrorCode.NOT_FOUND))
    )
    child = ChildConnection()
    process = RecordingProcess(alive=False)
    monkeypatch.setattr(helper_process.multiprocessing, "Pipe", _pipe_factory(parent, child))
    reader = helper_process.PosixHelperProcessFileReader(tmp_path, process_factory=lambda **_kwargs: process)

    asyncio.run(reader.read_file(ReadFileRequest("source.py"), _context(NeverCancelled())))

    assert process.terminated is False
    assert process.joined is True


def test_helper_maps_unsupported_encoding_and_unknown_path_errors_to_stable_codes(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "utf16.txt").write_bytes(b"\xff\xfeh\x00i\x00")
    connection = RecordingConnection()

    helper_process.read_one_file_in_helper(
        connection,
        str(tmp_path),
        ReadFileRequest("utf16.txt"),
        image_input_supported=False,
        limits=ReadFilesLimits(),
    )

    outcome = connection.sent[0]
    assert isinstance(outcome, ReadFileFailure)
    assert outcome.error.code is ReadFileErrorCode.UNSUPPORTED_ENCODING

    unknown_connection = RecordingConnection()
    error = helper_process.WorkspacePathResolutionError("UNKNOWN", "unknown")
    monkeypatch.setattr(helper_process, "open_workspace_file", lambda *_args: _raise(error))
    helper_process.read_one_file_in_helper(
        unknown_connection,
        str(tmp_path),
        ReadFileRequest("missing.txt"),
        image_input_supported=False,
        limits=ReadFilesLimits(),
    )

    unknown_outcome = unknown_connection.sent[0]
    assert isinstance(unknown_outcome, ReadFileFailure)
    assert unknown_outcome.error.code is ReadFileErrorCode.IO_ERROR


def test_helper_translates_reader_exceptions_to_stable_failures(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "source.txt").write_text("content", encoding="utf-8")

    class ReaderErrorCase:
        def __init__(self, error: Exception, expected: ReadFileErrorCode) -> None:
            self.error = error
            self.expected = expected

    cases = (
        ReaderErrorCase(
            helper_process.TextFileTooLargeError(size_bytes=9, max_size_bytes=8), ReadFileErrorCode.FILE_TOO_LARGE
        ),
        ReaderErrorCase(
            helper_process.ImageFileTooLargeError(size_bytes=9, max_size_bytes=8), ReadFileErrorCode.IMAGE_TOO_LARGE
        ),
        ReaderErrorCase(helper_process.UnsupportedTextEncodingError(), ReadFileErrorCode.UNSUPPORTED_ENCODING),
        ReaderErrorCase(helper_process.UnsupportedImageFileError(), ReadFileErrorCode.UNSUPPORTED_BINARY_FILE),
        ReaderErrorCase(OSError(), ReadFileErrorCode.IO_ERROR),
    )

    for case in cases:
        connection = RecordingConnection()
        monkeypatch.setattr(
            helper_process, "_read_opened_file", lambda *_args, error=case.error, **_kwargs: _raise(error)
        )
        helper_process.read_one_file_in_helper(
            connection,
            str(tmp_path),
            ReadFileRequest("source.txt"),
            image_input_supported=False,
            limits=ReadFilesLimits(),
        )

        outcome = connection.sent[0]
        assert isinstance(outcome, ReadFileFailure)
        assert outcome.error.code is case.expected


def _context(cancellation: NeverCancelled | Cancelled) -> WorkspaceReadContext:
    return WorkspaceReadContext(
        external_read_authorized=True,
        image_input_supported=True,
        cancellation=cancellation,
        deadline_at=datetime.now(UTC) + timedelta(seconds=1),
        limits=ReadFilesLimits(),
    )


def _pipe_factory(parent: ParentConnection, child: ChildConnection):
    def create_pipe(*, duplex: bool) -> tuple[ParentConnection, ChildConnection]:
        assert duplex is False
        return parent, child

    return create_pipe


def _queued_pipe_factory(parents: list[tuple[ParentConnection, ChildConnection]]):
    def create_pipe(*, duplex: bool) -> tuple[ParentConnection, ChildConnection]:
        assert duplex is False
        return parents.pop(0)

    return create_pipe


def _raise(error: BaseException) -> None:
    raise error
