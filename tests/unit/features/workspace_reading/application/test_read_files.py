"""Tests for bounded workspace-reading batch orchestration."""

import asyncio
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fabrica.features.workspace_reading.application.dtos import (
    ReadFileError,
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFileResult,
    ReadFilesCommand,
    ReadFilesLimits,
    TextFileResult,
)
from fabrica.features.workspace_reading.application.ports import WorkspaceReadContext
from fabrica.features.workspace_reading.application.use_cases import ReadFiles

MAXIMUM_PARALLEL_READS = 2


class MutableCancellation:
    """Test cancellation signal controlled by the reader fake."""

    def __init__(self) -> None:
        self.cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled


class DelayedReader:
    """Fake reader that records concurrency and releases all active reads together."""

    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self.paths: list[str] = []
        self.release = asyncio.Event()
        self.started = asyncio.Event()

    async def read_file(self, request: ReadFileRequest, context: WorkspaceReadContext) -> TextFileResult:
        del context
        self.paths.append(request.path)
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        if self.active == MAXIMUM_PARALLEL_READS:
            self.started.set()
        try:
            await self.release.wait()
            return _success(request)
        finally:
            self.active -= 1


class SequencedReader:
    """Fake reader with independent scripted outcomes for each request path."""

    def __init__(self, outcomes: dict[str, tuple[ReadFileResult | OSError, ...]]) -> None:
        self.outcomes = {path: deque(sequence) for path, sequence in outcomes.items()}
        self.calls: defaultdict[str, int] = defaultdict(int)

    async def read_file(self, request: ReadFileRequest, context: WorkspaceReadContext) -> ReadFileResult:
        del context
        self.calls[request.path] += 1
        outcome = self.outcomes[request.path].popleft()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class CancellingReader:
    """Fake reader that triggers cancellation after the first admitted request."""

    def __init__(self, cancellation: MutableCancellation) -> None:
        self.cancellation = cancellation
        self.paths: list[str] = []

    async def read_file(self, request: ReadFileRequest, context: WorkspaceReadContext) -> TextFileResult:
        del context
        self.paths.append(request.path)
        self.cancellation.cancelled = True
        return _success(request)


class BlockingReader:
    """Fake reader that only exits when the scheduler cancels it."""

    def __init__(self) -> None:
        self.cancelled = False

    async def read_file(self, request: ReadFileRequest, context: WorkspaceReadContext) -> TextFileResult:
        del request, context
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        msg = "blocking reader unexpectedly completed"
        raise AssertionError(msg)


def test_read_files_caps_concurrency_and_restores_command_order() -> None:
    reader = DelayedReader()
    context = _context(limits=ReadFilesLimits(max_files_per_call=4, max_parallel_reads=2))
    command = ReadFilesCommand(tuple(ReadFileRequest(f"src/{index}.py") for index in range(4)))

    async def run() -> tuple[ReadFileResult, ...]:
        task = asyncio.create_task(ReadFiles(reader).read(command, context))
        await reader.started.wait()
        assert reader.maximum_active == MAXIMUM_PARALLEL_READS
        reader.release.set()
        return (await task).results

    results = asyncio.run(run())

    assert reader.maximum_active == MAXIMUM_PARALLEL_READS
    assert tuple(result.path for result in results) == tuple(request.path for request in command.files)


def test_read_files_preserves_partial_success_and_retries_only_transient_io_failures() -> None:
    first = ReadFileRequest("src/first.py")
    second = ReadFileRequest("src/second.py")
    third = ReadFileRequest("src/third.py")
    reader = SequencedReader(
        {
            first.path: (_success(first),),
            second.path: (ReadFileFailure(second.path, ReadFileError(ReadFileErrorCode.NOT_FOUND)),),
            third.path: (
                ReadFileFailure(third.path, ReadFileError(ReadFileErrorCode.IO_ERROR, metadata={"transient": True})),
                _success(third),
            ),
        }
    )

    results = asyncio.run(ReadFiles(reader).read(ReadFilesCommand((first, second, third)), _context())).results

    assert tuple(result.path for result in results) == (first.path, second.path, third.path)
    assert isinstance(results[1], ReadFileFailure)
    assert results[1].error.code is ReadFileErrorCode.NOT_FOUND
    assert reader.calls == {first.path: 1, second.path: 1, third.path: 2}


def test_read_files_does_not_start_queued_work_after_cancellation() -> None:
    cancellation = MutableCancellation()
    reader = CancellingReader(cancellation)
    command = ReadFilesCommand((ReadFileRequest("src/first.py"), ReadFileRequest("src/second.py")))

    results = asyncio.run(
        ReadFiles(reader).read(
            command, _context(cancellation=cancellation, limits=ReadFilesLimits(max_parallel_reads=1))
        )
    ).results

    assert reader.paths == ["src/first.py"]
    assert isinstance(results[1], ReadFileFailure)
    assert results[1].error.code is ReadFileErrorCode.READ_CANCELLED


def test_read_files_cancels_active_work_and_suppresses_queue_after_tool_deadline() -> None:
    reader = BlockingReader()
    command = ReadFilesCommand((ReadFileRequest("src/first.py"), ReadFileRequest("src/second.py")))
    limits = ReadFilesLimits(max_parallel_reads=1, per_file_deadline_seconds=0.01, tool_deadline_seconds=0.01)

    results = asyncio.run(ReadFiles(reader).read(command, _context(limits=limits))).results

    assert reader.cancelled is True
    assert all(isinstance(result, ReadFileFailure) for result in results)
    assert tuple(result.error.code for result in results if isinstance(result, ReadFileFailure)) == (
        ReadFileErrorCode.READ_TIMEOUT,
        ReadFileErrorCode.READ_TIMEOUT,
    )


def _context(
    *,
    cancellation: MutableCancellation | None = None,
    limits: ReadFilesLimits | None = None,
) -> WorkspaceReadContext:
    return WorkspaceReadContext(
        external_read_authorized=True,
        image_input_supported=False,
        cancellation=cancellation or MutableCancellation(),
        deadline_at=datetime.now(UTC) + timedelta(seconds=5),
        limits=limits or ReadFilesLimits(),
    )


def _success(request: ReadFileRequest) -> TextFileResult:
    return TextFileResult(
        path=request.path,
        content="1 | source",
        start_line=1,
        end_line=1,
        complete=True,
        next_start_line=None,
        total_lines=1,
        total_lines_exact=True,
    )
