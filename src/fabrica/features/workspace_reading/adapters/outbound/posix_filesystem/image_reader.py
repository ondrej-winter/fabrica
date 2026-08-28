"""Read verified provider-neutral images from securely opened workspace descriptors."""

import os
from dataclasses import dataclass
from pathlib import PurePosixPath

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.classification import classify_file_bytes
from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.path_resolution import OpenedWorkspaceFile
from fabrica.features.workspace_reading.application.dtos import ImageContent, ImageFileResult, ReadFilesLimits


class ImageFileTooLargeError(ValueError):
    """Raised before loading an image that exceeds the configured byte bound."""

    def __init__(self, *, size_bytes: int, max_size_bytes: int) -> None:
        """Initialize stable image-size failure details."""
        super().__init__("image file exceeds the configured byte limit")
        self.size_bytes = size_bytes
        self.max_size_bytes = max_size_bytes


class UnsupportedImageFileError(ValueError):
    """Raised when complete bytes do not verify as a supported image."""

    def __init__(self) -> None:
        """Initialize the stable unsupported-image failure."""
        super().__init__("file bytes are not a supported image")


@dataclass(frozen=True, slots=True)
class PosixImageFileReader:
    """Return a bounded, magic-byte-verified image from an opened descriptor."""

    def read(self, opened_file: OpenedWorkspaceFile, *, path: str, limits: ReadFilesLimits) -> ImageFileResult:
        """Load one supported image without trusting its filename extension."""
        size_bytes = opened_file.stat_result.st_size
        if size_bytes > limits.max_image_bytes:
            raise ImageFileTooLargeError(size_bytes=size_bytes, max_size_bytes=limits.max_image_bytes)

        data = _read_all(opened_file.file_descriptor, size_bytes)
        media_type = classify_file_bytes(data).media_type
        if media_type is None:
            raise UnsupportedImageFileError
        return ImageFileResult(path=path, image=ImageContent(path=path, media_type=media_type, data=data))


def _read_all(file_descriptor: int, size_bytes: int) -> bytes:
    """Read the descriptor's known bounded size without changing its shared offset."""
    chunks: list[bytes] = []
    offset = 0
    while offset < size_bytes:
        chunk = os.pread(file_descriptor, size_bytes - offset, offset)
        if not chunk:
            msg = "image file changed while it was being read"
            raise OSError(msg)
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def has_supported_image_extension(path: str) -> bool:
    """Return whether a path claims one of the supported image formats."""
    return PurePosixPath(path).suffix.lower() in {".png", ".jpeg", ".jpg", ".gif", ".webp"}


__all__ = [
    "ImageFileTooLargeError",
    "PosixImageFileReader",
    "UnsupportedImageFileError",
    "has_supported_image_extension",
]
