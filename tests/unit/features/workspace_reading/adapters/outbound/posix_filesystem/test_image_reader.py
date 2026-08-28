"""Tests for bounded POSIX provider-neutral image reading."""

from pathlib import Path

import pytest

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import (
    ImageFileTooLargeError,
    PosixImageFileReader,
    UnsupportedImageFileError,
    image_reader,
    open_workspace_file,
)
from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits


@pytest.mark.parametrize(
    ("source", "media_type"),
    [
        (b"\x89PNG\r\n\x1a\npayload", "image/png"),
        (b"\xff\xd8\xff\xe0payload", "image/jpeg"),
        (b"GIF89apayload", "image/gif"),
        (b"RIFF\x00\x00\x00\x00WEBPpayload", "image/webp"),
    ],
)
def test_reader_returns_only_magic_byte_verified_image_content(tmp_path: Path, source: bytes, media_type: str) -> None:
    path = tmp_path / "misleading.txt"
    path.write_bytes(source)

    with open_workspace_file(tmp_path, "misleading.txt") as opened:
        result = PosixImageFileReader().read(opened, path="misleading.txt", limits=ReadFilesLimits())

    assert result.image.media_type == media_type
    assert result.image.data == source


def test_reader_rejects_a_fake_image_extension_without_verified_magic_bytes(tmp_path: Path) -> None:
    (tmp_path / "fake.png").write_bytes(b"not an image")

    with open_workspace_file(tmp_path, "fake.png") as opened, pytest.raises(UnsupportedImageFileError):
        PosixImageFileReader().read(opened, path="fake.png", limits=ReadFilesLimits())


def test_reader_rejects_images_over_the_configured_size_before_loading_them(tmp_path: Path) -> None:
    (tmp_path / "large.png").write_bytes(b"\x89PNG\r\n\x1a\nmore")

    with open_workspace_file(tmp_path, "large.png") as opened, pytest.raises(ImageFileTooLargeError) as error:
        PosixImageFileReader().read(opened, path="large.png", limits=ReadFilesLimits(max_image_bytes=8))

    assert error.value.size_bytes == len(b"\x89PNG\r\n\x1a\nmore")


def test_reader_fails_when_a_bounded_image_disappears_during_read(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(image_reader.os, "pread", lambda *_args: b"")

    with open_workspace_file(tmp_path, "image.png") as opened, pytest.raises(OSError, match="changed"):
        PosixImageFileReader().read(opened, path="image.png", limits=ReadFilesLimits())
