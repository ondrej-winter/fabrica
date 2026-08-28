"""Integration tests for descriptor-based POSIX workspace path resolution."""

import os
import sys
from pathlib import Path

import pytest

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import (
    WorkspacePathResolutionError,
    open_workspace_file,
)

pytestmark = pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="POSIX adapter targets macOS/Linux")


def test_open_workspace_file_opens_nested_regular_file(tmp_path: Path) -> None:
    path = tmp_path / "src" / "app.py"
    path.parent.mkdir()
    path.write_bytes(b"value = 1\n")

    with open_workspace_file(tmp_path, "src/app.py") as opened:
        assert os.read(opened.file_descriptor, 100) == b"value = 1\n"


@pytest.mark.parametrize(
    ("path", "expected_code"),
    [("/etc/passwd", "INVALID_PATH"), ("../outside.txt", "PATH_OUTSIDE_WORKSPACE")],
)
def test_open_workspace_file_rejects_invalid_or_escaping_paths(tmp_path: Path, path: str, expected_code: str) -> None:
    with pytest.raises(WorkspacePathResolutionError) as exc_info:
        open_workspace_file(tmp_path, path)

    assert exc_info.value.code == expected_code


def test_open_workspace_file_rejects_directories_and_escaping_symlinks(tmp_path: Path) -> None:
    (tmp_path / "directory").mkdir()
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (tmp_path / "escape.txt").symlink_to(outside)

    with pytest.raises(WorkspacePathResolutionError) as directory_error:
        open_workspace_file(tmp_path, "directory")
    with pytest.raises(WorkspacePathResolutionError) as symlink_error:
        open_workspace_file(tmp_path, "escape.txt")

    assert directory_error.value.code == "NOT_A_FILE"
    assert symlink_error.value.code == "PATH_OUTSIDE_WORKSPACE"


def test_open_workspace_file_allows_an_internal_relative_symlink(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "target.txt"
    target.parent.mkdir()
    target.write_bytes(b"inside")
    (tmp_path / "link.txt").symlink_to("nested/target.txt")

    with open_workspace_file(tmp_path, "link.txt") as opened:
        assert os.read(opened.file_descriptor, 100) == b"inside"


def test_open_workspace_file_allows_an_internal_directory_symlink(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "target.txt"
    target.parent.mkdir()
    target.write_bytes(b"inside")
    (tmp_path / "directory-link").symlink_to("nested", target_is_directory=True)

    with open_workspace_file(tmp_path, "directory-link/target.txt") as opened:
        assert os.read(opened.file_descriptor, 100) == b"inside"


@pytest.mark.parametrize(
    ("path", "expected_code"),
    [("missing.txt", "NOT_FOUND"), ("file/child.txt", "NOT_A_FILE")],
)
def test_open_workspace_file_translates_missing_and_non_directory_paths(
    tmp_path: Path, path: str, expected_code: str
) -> None:
    (tmp_path / "file").write_bytes(b"not a directory")

    with pytest.raises(WorkspacePathResolutionError) as exc_info:
        open_workspace_file(tmp_path, path)

    assert exc_info.value.code == expected_code


def test_opened_workspace_file_close_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "readable.txt"
    path.write_bytes(b"content")

    opened = open_workspace_file(tmp_path, "readable.txt")
    opened.close()
    opened.close()

    assert opened.file_descriptor == -1
