"""Capability-gated POSIX filesystem primitives for workspace reading."""

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.classification import (
    WorkspaceFileClassification,
    classify_file_bytes,
)
from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.helper_process import (
    PosixHelperProcessFileReader,
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

__all__ = [
    "ImageFileTooLargeError",
    "OpenedWorkspaceFile",
    "PosixHelperProcessFileReader",
    "PosixImageFileReader",
    "PosixTextFileReader",
    "TextFileTooLargeError",
    "UnsupportedImageFileError",
    "UnsupportedTextEncodingError",
    "WorkspaceFileClassification",
    "WorkspacePathResolutionError",
    "classify_file_bytes",
    "has_supported_image_extension",
    "open_workspace_file",
]
