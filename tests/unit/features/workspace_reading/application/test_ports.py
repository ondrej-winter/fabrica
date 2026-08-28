"""Tests for workspace-reading application ports and orchestration."""

import asyncio
import inspect
from datetime import UTC, datetime, timedelta

import pytest

from fabrica.features.workspace_reading.application import ports
from fabrica.features.workspace_reading.application.dtos import (
    ReadFileError,
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFilesCommand,
    ReadFilesLimits,
)
from fabrica.features.workspace_reading.application.ports import WorkspaceReadContext
from fabrica.features.workspace_reading.application.use_cases import ReadFiles


class NeverCancelled:
    """Test cancellation signal that never requests cancellation."""

    @property
    def is_cancelled(self) -> bool:
        return False


class RecordingFileReader:
    """Application-port fake that records normalized requests."""

    def __init__(self) -> None:
        self.requests: list[ReadFileRequest] = []
        self.contexts: list[WorkspaceReadContext] = []

    async def read_file(self, request: ReadFileRequest, context: WorkspaceReadContext) -> ReadFileFailure:
        self.requests.append(request)
        self.contexts.append(context)
        return ReadFileFailure(request.path, ReadFileError(ReadFileErrorCode.NOT_FOUND))


def test_workspace_reading_ports_are_application_owned_without_adapter_types() -> None:
    exported_names = set(ports.__all__)

    assert {
        "ReadFilesPort",
        "WorkspaceFileReader",
        "WorkspaceReadCancellationSignal",
        "WorkspaceReadContext",
    } <= exported_names
    for name in exported_names:
        exported = getattr(ports, name)
        assert inspect.isclass(exported)
        assert "fabrica.features.workspace_reading.application.ports" in exported.__module__

    source = inspect.getsource(ports)

    assert ".adapters" not in source
    assert "pathlib" not in source
    assert "open(" not in source


def test_workspace_read_context_requires_an_aware_deadline() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        WorkspaceReadContext(
            external_read_authorized=True,
            image_input_supported=False,
            cancellation=NeverCancelled(),
            deadline_at=datetime.fromtimestamp(0, tz=UTC).replace(tzinfo=None),
            limits=ReadFilesLimits(),
        )


def test_read_files_delegates_each_request_in_command_order_with_the_host_context() -> None:
    reader = RecordingFileReader()
    context = WorkspaceReadContext(
        external_read_authorized=True,
        image_input_supported=True,
        cancellation=NeverCancelled(),
        deadline_at=datetime.now(UTC) + timedelta(seconds=5),
        limits=ReadFilesLimits(),
    )
    command = ReadFilesCommand((ReadFileRequest("src/first.py"), ReadFileRequest("src/second.py", start_line=4)))

    result = asyncio.run(ReadFiles(reader).read(command, context))

    assert tuple(request.path for request in reader.requests) == ("src/first.py", "src/second.py")
    assert reader.contexts == [context, context]
    assert tuple(outcome.path for outcome in result.results) == ("src/first.py", "src/second.py")
