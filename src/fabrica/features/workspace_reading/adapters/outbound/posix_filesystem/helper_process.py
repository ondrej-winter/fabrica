"""Supervised one-request helper-process reader for POSIX workspace files."""

from __future__ import annotations

import asyncio
import multiprocessing
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.classification import (
    WorkspaceFileClassification,
    classify_file_bytes,
)
from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.image_reader import (
    ImageFileTooLargeError,
    PosixImageFileReader,
    UnsupportedImageFileError,
    has_supported_image_extension,
)
from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.path_resolution import (
    OpenedWorkspaceFile,
    WorkspacePathResolutionError,
    open_workspace_file,
)
from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.text_reader import (
    PosixTextFileReader,
    TextFileTooLargeError,
    UnsupportedTextEncodingError,
)
from fabrica.features.workspace_reading.application.dtos import (
    ReadFileError,
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFileResult,
    ReadFilesLimits,
)
from fabrica.features.workspace_reading.application.ports import WorkspaceFileReader, WorkspaceReadContext

if TYPE_CHECKING:
    from collections.abc import Callable

_POLL_INTERVAL_SECONDS = 0.01
_CLASSIFICATION_BYTES = 8_192


class HelperResultSender(Protocol):
    """Minimal serializable-outcome channel owned by one helper process."""

    def send(self, outcome: ReadFileResult) -> None:
        """Send the helper's sole read outcome to its supervising parent."""
        ...

    def close(self) -> None:
        """Release the helper's result channel."""
        ...


class HelperProcess(Protocol):
    """Minimal lifecycle boundary required to supervise one read helper."""

    def start(self) -> None:
        """Start the helper process."""
        ...

    def is_alive(self) -> bool:
        """Return whether the helper still requires termination."""
        ...

    def terminate(self) -> None:
        """Request helper termination during supervisor cleanup."""
        ...

    def join(self) -> None:
        """Wait for helper cleanup before returning from the read attempt."""
        ...


@dataclass(frozen=True, slots=True)
class PosixHelperProcessFileReader(WorkspaceFileReader):
    """Run one descriptor-backed file-read attempt in a terminable helper process."""

    workspace_root: Path
    process_factory: Callable[..., HelperProcess] = multiprocessing.Process

    async def read_file(self, request: ReadFileRequest, context: WorkspaceReadContext) -> ReadFileResult:
        """Read one request and always join its helper before returning or raising."""
        parent_connection, child_connection = multiprocessing.Pipe(duplex=False)
        process = self.process_factory(
            target=read_one_file_in_helper,
            args=(child_connection, str(self.workspace_root), request, context.image_input_supported, context.limits),
            daemon=True,
        )
        process.start()
        child_connection.close()
        try:
            while True:
                if parent_connection.poll():
                    outcome = parent_connection.recv()
                    if not isinstance(outcome, (ReadFileFailure,)) and not hasattr(outcome, "path"):
                        return _failure(request, ReadFileErrorCode.IO_ERROR)
                    return outcome
                if context.cancellation.is_cancelled:
                    return _failure(request, ReadFileErrorCode.READ_CANCELLED)
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        finally:
            parent_connection.close()
            if process.is_alive():
                process.terminate()
            process.join()


def read_one_file_in_helper(
    connection: HelperResultSender,
    workspace_root: str,
    request: ReadFileRequest,
    image_input_supported: bool,  # noqa: FBT001
    limits: ReadFilesLimits,
) -> None:
    """Execute one bounded text or image read and send a safe outcome to the parent."""
    try:
        with open_workspace_file(Path(workspace_root), request.path) as opened_file:
            preview = _read_preview(opened_file.file_descriptor)
            classification = classify_file_bytes(preview)
            outcome = _read_opened_file(
                opened_file,
                request=request,
                classification=classification.kind,
                image_input_supported=image_input_supported,
                limits=limits,
            )
    except WorkspacePathResolutionError as err:
        outcome = _failure(request, _error_code(err.code))
    except TextFileTooLargeError as err:
        outcome = ReadFileFailure(
            request.path,
            ReadFileError(
                ReadFileErrorCode.FILE_TOO_LARGE,
                metadata={"size_bytes": err.size_bytes, "max_size_bytes": err.max_size_bytes},
            ),
        )
    except ImageFileTooLargeError as err:
        outcome = ReadFileFailure(
            request.path,
            ReadFileError(
                ReadFileErrorCode.IMAGE_TOO_LARGE,
                metadata={"size_bytes": err.size_bytes, "max_size_bytes": err.max_size_bytes},
            ),
        )
    except UnsupportedTextEncodingError:
        outcome = _failure(request, ReadFileErrorCode.UNSUPPORTED_ENCODING)
    except UnsupportedImageFileError:
        outcome = _failure(request, ReadFileErrorCode.UNSUPPORTED_BINARY_FILE)
    except OSError:
        outcome = ReadFileFailure(request.path, ReadFileError(ReadFileErrorCode.IO_ERROR, metadata={"transient": True}))
    try:
        connection.send(outcome)
    finally:
        connection.close()


def _read_opened_file(
    opened_file: OpenedWorkspaceFile,
    *,
    request: ReadFileRequest,
    classification: WorkspaceFileClassification,
    image_input_supported: bool,
    limits: ReadFilesLimits,
) -> ReadFileResult:
    """Map verified classification and extension signals to one bounded outcome."""
    if classification in {
        WorkspaceFileClassification.PNG,
        WorkspaceFileClassification.JPEG,
        WorkspaceFileClassification.GIF,
        WorkspaceFileClassification.WEBP,
    }:
        if not image_input_supported:
            return _failure(request, ReadFileErrorCode.IMAGE_INPUT_UNSUPPORTED)
        return PosixImageFileReader().read(opened_file, path=request.path, limits=limits)
    if has_supported_image_extension(request.path) or classification is WorkspaceFileClassification.BINARY:
        return _failure(request, ReadFileErrorCode.UNSUPPORTED_BINARY_FILE)
    if classification is WorkspaceFileClassification.UNSUPPORTED_ENCODING:
        return _failure(request, ReadFileErrorCode.UNSUPPORTED_ENCODING)
    return PosixTextFileReader().read(
        opened_file,
        path=request.path,
        start_line=request.start_line,
        end_line=request.end_line,
        limits=limits,
    )


def _read_preview(file_descriptor: int) -> bytes:
    """Read a bounded classification prefix without disturbing the text reader."""
    return os.pread(file_descriptor, _CLASSIFICATION_BYTES, 0)


def _error_code(code: str) -> ReadFileErrorCode:
    """Map adapter path failures to the stable application error vocabulary."""
    try:
        return ReadFileErrorCode(code)
    except ValueError:
        return ReadFileErrorCode.IO_ERROR


def _failure(request: ReadFileRequest, code: ReadFileErrorCode) -> ReadFileFailure:
    """Create a safe one-request helper failure."""
    return ReadFileFailure(request.path, ReadFileError(code))


__all__ = ["PosixHelperProcessFileReader"]
