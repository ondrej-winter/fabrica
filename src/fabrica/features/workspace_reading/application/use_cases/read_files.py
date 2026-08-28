"""Application orchestration for bounded workspace file reads."""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic

from fabrica.features.workspace_reading.application.dtos import (
    ReadFileError,
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFileResult,
    ReadFilesCommand,
    ReadFilesResult,
)
from fabrica.features.workspace_reading.application.ports import (
    ReadFilesPort,
    WorkspaceFileReader,
    WorkspaceReadContext,
)


@dataclass(frozen=True, slots=True)
class ReadFiles(ReadFilesPort):
    """Coordinate bounded, ordered, retry-aware workspace file reads."""

    file_reader: WorkspaceFileReader

    async def read(self, command: ReadFilesCommand, context: WorkspaceReadContext) -> ReadFilesResult:
        """Read a batch while preserving order and isolating request failures."""
        deadline = _deadline_monotonic(context)
        results: list[ReadFileResult | None] = [None] * len(command.files)
        queued = deque(enumerate(command.files))
        active: dict[asyncio.Task[ReadFileResult], tuple[int, ReadFileRequest]] = {}

        while active or queued:
            if context.cancellation.is_cancelled:
                _cancel_active(active)
                _fill_remaining(results, queued, ReadFileErrorCode.READ_CANCELLED)
                await _collect_cancelled(active, results, ReadFileErrorCode.READ_CANCELLED)
                break
            if monotonic() >= deadline:
                _cancel_active(active)
                _fill_remaining(results, queued, ReadFileErrorCode.READ_TIMEOUT)
                await _collect_cancelled(active, results, ReadFileErrorCode.READ_TIMEOUT)
                break

            while len(active) < context.limits.max_parallel_reads:
                if not queued:
                    break
                index, request = queued.popleft()
                task = asyncio.create_task(self._read_one(request, context, deadline))
                active[task] = (index, request)

            if not active:
                break
            timeout = min(0.01, max(0.0, deadline - monotonic()))
            done, _ = await asyncio.wait(active, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                index, request = active.pop(task)
                results[index] = _task_outcome(task, request)

        if any(result is None for result in results):
            msg = "read scheduler did not produce an outcome for every request"
            raise RuntimeError(msg)
        return ReadFilesResult(results=tuple(result for result in results if result is not None))

    async def _read_one(
        self,
        request: ReadFileRequest,
        context: WorkspaceReadContext,
        deadline: float,
    ) -> ReadFileResult:
        """Execute one request with remaining deadline budget and one retry."""
        for attempt in range(context.limits.max_retries + 1):
            remaining = min(context.limits.per_file_deadline_seconds, deadline - monotonic())
            if remaining <= 0:
                return _failure(request, ReadFileErrorCode.READ_TIMEOUT)
            try:
                outcome = await asyncio.wait_for(self.file_reader.read_file(request, context), timeout=remaining)
            except TimeoutError:
                outcome = _failure(request, ReadFileErrorCode.READ_TIMEOUT)
            except asyncio.CancelledError:
                raise
            except OSError:
                outcome = _failure(request, ReadFileErrorCode.IO_ERROR, transient=True)
            if not _is_retryable(outcome) or attempt == context.limits.max_retries:
                return outcome
        msg = "read retry loop exhausted unexpectedly"
        raise RuntimeError(msg)


def _deadline_monotonic(context: WorkspaceReadContext) -> float:
    """Return the earliest host or configured tool deadline on the monotonic clock."""
    configured = monotonic() + context.limits.tool_deadline_seconds
    if context.deadline_at is None:
        return configured
    host_remaining = (context.deadline_at - datetime.now(UTC)).total_seconds()
    return min(configured, monotonic() + max(host_remaining, 0.0))


def _failure(request: ReadFileRequest, code: ReadFileErrorCode, *, transient: bool = False) -> ReadFileFailure:
    """Create a safe scheduler-generated per-request failure."""
    metadata = {"transient": True} if transient else {}
    return ReadFileFailure(path=request.path, error=ReadFileError(code=code, metadata=metadata))


def _is_retryable(outcome: ReadFileResult) -> bool:
    """Allow one retry only for an adapter-classified transient I/O failure."""
    return (
        isinstance(outcome, ReadFileFailure)
        and outcome.error.code is ReadFileErrorCode.IO_ERROR
        and outcome.error.metadata.get("transient") is True
    )


def _task_outcome(task: asyncio.Task[ReadFileResult], request: ReadFileRequest) -> ReadFileResult:
    """Translate an unexpected task termination into a stable outcome."""
    if task.cancelled():
        return _failure(request, ReadFileErrorCode.READ_CANCELLED)
    return task.result()


def _cancel_active(active: dict[asyncio.Task[ReadFileResult], tuple[int, ReadFileRequest]]) -> None:
    """Request cancellation from every active one-request execution."""
    for task in active:
        task.cancel()


def _fill_remaining(
    results: list[ReadFileResult | None],
    queued: deque[tuple[int, ReadFileRequest]],
    code: ReadFileErrorCode,
) -> None:
    """Fill all queued request positions after a batch-wide stop condition."""
    for index, request in queued:
        results[index] = _failure(request, code)
    queued.clear()


async def _collect_cancelled(
    active: dict[asyncio.Task[ReadFileResult], tuple[int, ReadFileRequest]],
    results: list[ReadFileResult | None],
    code: ReadFileErrorCode,
) -> None:
    """Await active cleanup before returning stable stop-condition outcomes."""
    cancelled = tuple(active)
    await asyncio.gather(*cancelled, return_exceptions=True)
    for index, request in active.values():
        results[index] = _failure(request, code)
