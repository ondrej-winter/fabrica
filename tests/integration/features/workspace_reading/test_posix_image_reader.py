"""Integration tests for POSIX workspace image reading."""

import sys
from pathlib import Path

import pytest

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import helper_process
from fabrica.features.workspace_reading.application.dtos import (
    ReadFileErrorCode,
    ReadFileFailure,
    ReadFileRequest,
    ReadFilesLimits,
)

pytestmark = pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX adapter targets macOS/Linux")


class RecordingConnection:
    """Capture the one serializable helper outcome for integration assertions."""

    def __init__(self) -> None:
        self.outcome: object | None = None

    def send(self, outcome: object) -> None:
        self.outcome = outcome

    def close(self) -> None:
        pass


def test_helper_rejects_invalid_image_magic_and_oversized_images(tmp_path: Path) -> None:
    (tmp_path / "fake.png").write_bytes(b"not image bytes")
    (tmp_path / "large.png").write_bytes(b"\x89PNG\r\n\x1a\npayload")
    fake_connection = RecordingConnection()
    large_connection = RecordingConnection()

    helper_process.read_one_file_in_helper(
        fake_connection,
        str(tmp_path),
        ReadFileRequest("fake.png"),
        image_input_supported=True,
        limits=ReadFilesLimits(),
    )
    helper_process.read_one_file_in_helper(
        large_connection,
        str(tmp_path),
        ReadFileRequest("large.png"),
        image_input_supported=True,
        limits=ReadFilesLimits(max_image_bytes=8),
    )

    assert isinstance(fake_connection.outcome, ReadFileFailure)
    assert fake_connection.outcome.error.code is ReadFileErrorCode.UNSUPPORTED_BINARY_FILE
    assert isinstance(large_connection.outcome, ReadFileFailure)
    assert large_connection.outcome.error.code is ReadFileErrorCode.IMAGE_TOO_LARGE
