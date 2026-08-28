"""Byte-level classification for supported workspace file content."""

from dataclasses import dataclass
from enum import StrEnum

RIFF_WEBP_HEADER_BYTES = 12


class WorkspaceFileClassification(StrEnum):
    """The safe content categories recognized before a file is exposed."""

    TEXT = "text"
    PNG = "image/png"
    JPEG = "image/jpeg"
    GIF = "image/gif"
    WEBP = "image/webp"
    BINARY = "binary"
    UNSUPPORTED_ENCODING = "unsupported_encoding"


@dataclass(frozen=True, slots=True)
class ClassifiedWorkspaceFile:
    """Classification result without filesystem or provider-specific values."""

    kind: WorkspaceFileClassification

    @property
    def media_type(self) -> str | None:
        """Return the verified media type when this is a supported image."""
        if self.kind in {
            WorkspaceFileClassification.PNG,
            WorkspaceFileClassification.JPEG,
            WorkspaceFileClassification.GIF,
            WorkspaceFileClassification.WEBP,
        }:
            return self.kind.value
        return None


def classify_file_bytes(source: bytes) -> ClassifiedWorkspaceFile:
    """Classify complete file bytes without trusting the filename extension."""
    source = bytes(source)
    image_kind = _image_kind(source)
    if image_kind is not None:
        return ClassifiedWorkspaceFile(image_kind)
    if source.startswith((b"\xff\xfe", b"\xfe\xff")):
        return ClassifiedWorkspaceFile(WorkspaceFileClassification.UNSUPPORTED_ENCODING)
    if b"\x00" in source:
        return ClassifiedWorkspaceFile(WorkspaceFileClassification.BINARY)
    try:
        source.removeprefix(b"\xef\xbb\xbf").decode("utf-8")
    except UnicodeDecodeError:
        return ClassifiedWorkspaceFile(WorkspaceFileClassification.UNSUPPORTED_ENCODING)
    return ClassifiedWorkspaceFile(WorkspaceFileClassification.TEXT)


def _image_kind(source: bytes) -> WorkspaceFileClassification | None:
    if source.startswith(b"\x89PNG\r\n\x1a\n"):
        return WorkspaceFileClassification.PNG
    if source.startswith(b"\xff\xd8\xff"):
        return WorkspaceFileClassification.JPEG
    if source.startswith((b"GIF87a", b"GIF89a")):
        return WorkspaceFileClassification.GIF
    if (
        len(source) >= RIFF_WEBP_HEADER_BYTES
        and source.startswith(b"RIFF")
        and source[8:RIFF_WEBP_HEADER_BYTES] == b"WEBP"
    ):
        return WorkspaceFileClassification.WEBP
    return None


__all__ = ["ClassifiedWorkspaceFile", "WorkspaceFileClassification", "classify_file_bytes"]
