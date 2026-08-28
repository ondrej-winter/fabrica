"""Tests for provider-neutral workspace file classification."""

import errno

import pytest

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import (
    WorkspaceFileClassification,
    classify_file_bytes,
)
from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem.path_resolution import (
    WorkspacePathResolutionError,
    _translate_os_error,
    _validate_relative_path,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (b"plain text\n", WorkspaceFileClassification.TEXT),
        (b"\xef\xbb\xbfplain text\n", WorkspaceFileClassification.TEXT),
        (b"\x89PNG\r\n\x1a\ncontent", WorkspaceFileClassification.PNG),
        (b"\xff\xd8\xff\xe0content", WorkspaceFileClassification.JPEG),
        (b"GIF89acontent", WorkspaceFileClassification.GIF),
        (b"RIFF\x00\x00\x00\x00WEBPcontent", WorkspaceFileClassification.WEBP),
        (b"\xff\xfeh\x00i\x00", WorkspaceFileClassification.UNSUPPORTED_ENCODING),
        (b"fake.png\x00archive", WorkspaceFileClassification.BINARY),
        (b"\xff", WorkspaceFileClassification.UNSUPPORTED_ENCODING),
    ],
)
def test_classify_file_bytes_uses_verified_content_not_filename(
    source: bytes, expected: WorkspaceFileClassification
) -> None:
    result = classify_file_bytes(source)

    assert result.kind is expected


def test_classification_exposes_media_type_only_for_verified_images() -> None:
    assert classify_file_bytes(b"\x89PNG\r\n\x1a\ncontent").media_type == "image/png"
    assert classify_file_bytes(b"text").media_type is None


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (FileNotFoundError(), "NOT_FOUND"),
        (PermissionError(), "PERMISSION_DENIED"),
        (NotADirectoryError(errno.ENOTDIR, "not a directory"), "NOT_A_FILE"),
        (OSError(), "IO_ERROR"),
    ],
)
def test_path_resolution_translates_os_errors_to_stable_codes(error: OSError, expected_code: str) -> None:
    assert _translate_os_error(error).code == expected_code


def test_path_resolution_errors_render_messages_and_reject_invalid_paths() -> None:
    error = WorkspacePathResolutionError("INVALID_PATH", "invalid")

    assert str(error) == "invalid"
    with pytest.raises(WorkspacePathResolutionError, match="workspace-relative"):
        _validate_relative_path("/absolute.txt")
