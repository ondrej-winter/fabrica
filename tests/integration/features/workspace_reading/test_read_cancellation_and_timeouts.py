"""Integration tests for real helper-process cleanup after read interruption."""

import asyncio
import errno
import multiprocessing
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from multiprocessing.synchronize import Event as MultiprocessingEvent
from pathlib import Path

import pytest

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import PosixHelperProcessFileReader
from fabrica.features.workspace_reading.application.dtos import (
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFilesCommand,
    ReadFilesLimits,
)
from fabrica.features.workspace_reading.application.ports import WorkspaceReadContext
from fabrica.features.workspace_reading.application.use_cases import ReadFiles

pytestmark = pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX adapter targets macOS/Linux")


class MutableCancellation:
    """Cancellation signal controlled by one integration test."""

    def __init__(self) -> None:
        self.cancelled = False

    @property
    def is_cancelled(self) -> bool:
        """Return the current host cancellation state."""
        return self.cancelled


class RecordingProcessFactory:
    """Start real helpers while recording the process that the reader must join."""

    def __init__(self) -> None:
        self.started = multiprocessing.Event()
        self.process: multiprocessing.Process | None = None

    def __call__(
        self,
        *,
        target: Callable[..., None],
        args: tuple[object, ...],
        daemon: bool,
    ) -> multiprocessing.Process:
        """Create a real helper that signals immediately before its read attempt."""
        self.process = multiprocessing.Process(
            target=_signal_then_run_helper,
            args=(self.started, target, args),
            daemon=daemon,
        )
        return self.process


def _signal_then_run_helper(
    started: MultiprocessingEvent,
    target: Callable[..., None],
    args: tuple[object, ...],
) -> None:
    """Signal parent supervision before entering the production helper target."""
    started.set()
    target(*args)


@pytest.mark.parametrize(
    "interruption",
    ["timeout", "cancellation"],
)
def test_read_interruption_terminates_and_joins_a_real_blocked_helper(
    tmp_path: Path,
    interruption: str,
) -> None:
    fifo_path = tmp_path / "blocked.fifo"
    os.mkfifo(fifo_path)
    cancellation = MutableCancellation()
    process_factory = RecordingProcessFactory()
    reader = PosixHelperProcessFileReader(tmp_path, process_factory=process_factory)
    limits = ReadFilesLimits(
        max_retries=0,
        per_file_deadline_seconds=1.0,
        tool_deadline_seconds=1.0,
    )
    context = WorkspaceReadContext(
        external_read_authorized=False,
        image_input_supported=False,
        cancellation=cancellation,
        deadline_at=datetime.now(UTC) + timedelta(seconds=2),
        limits=limits,
    )

    async def read() -> ReadFileFailure:
        task = asyncio.create_task(
            ReadFiles(reader).read(ReadFilesCommand((ReadFileRequest("blocked.fifo"),)), context)
        )
        assert await asyncio.to_thread(process_factory.started.wait, 1.0)
        if interruption == "cancellation":
            cancellation.cancelled = True
        result = await task
        outcome = result.results[0]
        assert isinstance(outcome, ReadFileFailure)
        return outcome

    outcome = asyncio.run(read())

    expected_code = ReadFileErrorCode.READ_TIMEOUT if interruption == "timeout" else ReadFileErrorCode.READ_CANCELLED
    assert outcome.error.code is expected_code
    assert process_factory.process is not None
    assert process_factory.process.is_alive() is False
    assert process_factory.process.exitcode is not None

    with pytest.raises(OSError, check=lambda error: error.errno == errno.ENXIO):
        os.open(fifo_path, os.O_WRONLY | os.O_NONBLOCK)
