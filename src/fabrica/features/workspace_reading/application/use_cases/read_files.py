"""Application orchestration for normalized workspace file reads."""

from dataclasses import dataclass

from fabrica.features.workspace_reading.application.dtos import ReadFilesCommand, ReadFilesResult
from fabrica.features.workspace_reading.application.ports import (
    ReadFilesPort,
    WorkspaceFileReader,
    WorkspaceReadContext,
)


@dataclass(frozen=True, slots=True)
class ReadFiles(ReadFilesPort):
    """Delegate normalized file requests to the application-owned reader port.

    This use case intentionally preserves request order without selecting
    scheduling, retry, cancellation, or deadline mechanics. Those policies are
    owned by the later batch-execution coordinator.
    """

    file_reader: WorkspaceFileReader

    async def read(self, command: ReadFilesCommand, context: WorkspaceReadContext) -> ReadFilesResult:
        """Read each normalized request in command order."""
        results = [await self.file_reader.read_file(request, context) for request in command.files]
        return ReadFilesResult(results=tuple(results))
