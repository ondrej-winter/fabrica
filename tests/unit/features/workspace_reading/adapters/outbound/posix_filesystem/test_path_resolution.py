"""Unit tests for POSIX descriptor-based path-resolution failure boundaries."""

import errno
from collections import deque

import pytest

from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import path_resolution


def test_path_resolution_rejects_unsupported_host_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(path_resolution.sys, "platform", "win32")

    with pytest.raises(path_resolution.WorkspacePathResolutionError, match="unsupported") as exc_info:
        path_resolution._require_supported_capabilities()  # noqa: SLF001 - validates host capability boundary.

    assert exc_info.value.code == "IO_ERROR"


def test_path_resolution_rejects_empty_symlink_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(path_resolution.os, "readlink", lambda *_args, **_kwargs: ".")

    with pytest.raises(path_resolution.WorkspacePathResolutionError, match="empty") as exc_info:
        path_resolution._try_expand_symlink_target(1, "link", deque())  # noqa: SLF001 - validates symlink expansion boundary.

    assert exc_info.value.code == "INVALID_PATH"


def test_path_resolution_translates_symlink_read_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_readlink(*_args: object, **_kwargs: object) -> str:
        raise PermissionError(errno.EACCES, "denied")

    monkeypatch.setattr(path_resolution.os, "readlink", fail_readlink)

    with pytest.raises(path_resolution.WorkspacePathResolutionError) as exc_info:
        path_resolution._try_expand_symlink_target(1, "link", deque())  # noqa: SLF001 - validates symlink expansion boundary.

    assert exc_info.value.code == "PERMISSION_DENIED"


def test_path_resolution_closes_file_descriptor_when_final_stat_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    closed_descriptors: list[int] = []
    monkeypatch.setattr(path_resolution.os, "open", lambda *_args, **_kwargs: 42)

    def record_close(descriptor: int) -> None:
        closed_descriptors.append(descriptor)

    monkeypatch.setattr(path_resolution.os, "close", record_close)

    def fail_fstat(_descriptor: int) -> object:
        raise OSError(errno.EIO, "failed")

    monkeypatch.setattr(path_resolution.os, "fstat", fail_fstat)

    with pytest.raises(path_resolution.WorkspacePathResolutionError) as exc_info:
        path_resolution._open_final_component(1, "file.txt", deque())  # noqa: SLF001 - validates descriptor cleanup boundary.

    assert exc_info.value.code == "IO_ERROR"
    assert closed_descriptors == [42]
