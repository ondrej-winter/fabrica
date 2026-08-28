"""Capability-gated POSIX filesystem primitives for workspace reading."""

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.classification import (
    WorkspaceFileClassification,
    classify_file_bytes,
)
from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.path_resolution import (
    OpenedWorkspaceFile,
    WorkspacePathResolutionError,
    open_workspace_file,
)

__all__ = [
    "OpenedWorkspaceFile",
    "WorkspaceFileClassification",
    "WorkspacePathResolutionError",
    "classify_file_bytes",
    "open_workspace_file",
]
