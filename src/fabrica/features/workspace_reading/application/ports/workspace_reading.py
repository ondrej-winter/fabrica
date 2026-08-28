"""Application-owned ports for bounded workspace file reading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from fabrica.features.workspace_reading.application.dtos import (
        ReadFileRequest,
        ReadFileResult,
        ReadFilesCommand,
        ReadFilesLimits,
        ReadFilesResult,
    )


class WorkspaceReadCancellationSignal(Protocol):
    """Cancellation boundary that read execution must observe."""

    @property
    def is_cancelled(self) -> bool:
        """Return whether the host has requested cancellation."""
        ...


@dataclass(frozen=True, slots=True)
class WorkspaceReadContext:
    """Host-supplied authorization, capability, and execution bounds for one batch."""

    external_read_authorized: bool
    image_input_supported: bool
    cancellation: WorkspaceReadCancellationSignal
    deadline_at: datetime | None
    limits: ReadFilesLimits

    def __post_init__(self) -> None:
        if self.deadline_at is not None and self.deadline_at.tzinfo is None:
            msg = "deadline_at must be timezone-aware"
            raise ValueError(msg)


class ReadFilesPort(Protocol):
    """Inbound port for reading one normalized batch of workspace files."""

    async def read(self, command: ReadFilesCommand, context: WorkspaceReadContext) -> ReadFilesResult:
        """Read the requested files under host-supplied policy and limits."""
        ...


class WorkspaceFileReader(Protocol):
    """Outbound port for reading one normalized workspace file request."""

    async def read_file(self, request: ReadFileRequest, context: WorkspaceReadContext) -> ReadFileResult:
        """Read one request and return either its content or a structured failure."""
        ...


__all__ = [
    "ReadFilesPort",
    "WorkspaceFileReader",
    "WorkspaceReadCancellationSignal",
    "WorkspaceReadContext",
]
