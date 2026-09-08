"""Tests for descriptor-rooted native POSIX patch operations."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem import native_operations
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.native_operations import (
    NativePatchOperationError,
    create_directory,
    native_no_replace_backend_available,
    prove_native_no_replace,
    rename_no_replace,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    sys.platform not in {"darwin", "linux"},
    reason="native no-replace backend targets macOS/Linux",
)


def test_native_no_replace_backend_proves_its_workspace_contract(tmp_path: Path) -> None:
    assert native_no_replace_backend_available() is True

    prove_native_no_replace(tmp_path)


def test_native_no_replace_rename_preserves_destination_created_after_planning(tmp_path: Path) -> None:
    (tmp_path / "parent").mkdir()
    source = tmp_path / "source"
    destination = tmp_path / "parent" / "destination"
    source.write_text("planned", encoding="utf-8")
    destination.write_text("external", encoding="utf-8")

    with pytest.raises(FileExistsError):
        rename_no_replace(tmp_path, "source", "parent/destination")

    assert source.read_text(encoding="utf-8") == "planned"
    assert destination.read_text(encoding="utf-8") == "external"


def test_descriptor_rooted_create_rejects_a_substituted_symlink_parent(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / "parent").symlink_to(external, target_is_directory=True)

    with pytest.raises(NotADirectoryError):
        create_directory(tmp_path, "parent/created", mode=0o700)

    assert not (external / "created").exists()


@pytest.mark.parametrize("relative_path", ["", "/", ".", "..", "parent/../created"])
def test_native_operations_reject_invalid_workspace_relative_paths(relative_path: str) -> None:
    with pytest.raises(ValueError, match="workspace-relative"):
        native_operations._path_components(relative_path)  # noqa: SLF001 - validates adapter boundary input.


def test_native_no_replace_rename_requires_an_available_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(native_operations, "native_no_replace_backend_available", lambda: False)

    with pytest.raises(NativePatchOperationError, match="unavailable"):
        rename_no_replace(tmp_path, "source", "destination")


@pytest.mark.parametrize(
    ("platform", "expected_backend"),
    [("darwin", "darwin"), ("linux", "linux")],
)
def test_native_no_replace_rename_dispatches_to_the_selected_platform_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, expected_backend: str
) -> None:
    source = tmp_path / "source"
    source.write_text("source", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(native_operations, "native_no_replace_backend_available", lambda: True)
    monkeypatch.setattr(native_operations.sys, "platform", platform)
    monkeypatch.setattr(
        native_operations,
        "_darwin_renameatx_no_replace",
        lambda *_args: calls.append("darwin"),
    )
    monkeypatch.setattr(
        native_operations,
        "_linux_renameat2_no_replace",
        lambda *_args: calls.append("linux"),
    )

    rename_no_replace(tmp_path, "source", "destination")

    assert calls == [expected_backend]


def test_linux_native_no_replace_translates_nonzero_syscall_result(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RenameAt2:
        argtypes: object
        restype: object

        def __call__(self, *_args: object) -> int:
            return -1

    class _Libc:
        renameat2 = _RenameAt2()

    monkeypatch.setattr(native_operations.ctypes, "CDLL", lambda *_args, **_kwargs: _Libc())
    monkeypatch.setattr(native_operations.ctypes, "get_errno", lambda: 17)

    with pytest.raises(FileExistsError):
        native_operations._linux_renameat2_no_replace(1, "source", 2, "destination")  # noqa: SLF001
