"""Descriptor-rooted native filesystem operations for POSIX patch mutation."""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_DARWIN_RENAME_EXCL = 0x00000004
_DARWIN_RENAME_NOFOLLOW_ANY = 0x00000010
_LINUX_RENAME_NOREPLACE = 1
_DIRECTORY_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class NativePatchOperationError(OSError):
    """Raised when a required native patch operation is unavailable or unsafe."""


def native_no_replace_backend_available() -> bool:
    """Return whether this host exposes the selected no-replace backend."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        return hasattr(libc, "renameatx_np")
    if sys.platform == "linux":
        return hasattr(libc, "renameat2")
    return False


def prove_native_no_replace(workspace_root: Path) -> None:
    """Prove that the selected backend rejects overwriting an existing destination."""
    probe_name = ".fabrica-ap-02-no-replace-probe"
    probe_root = workspace_root / probe_name
    probe_root.mkdir(mode=0o700)
    try:
        source = f"{probe_name}/source"
        destination = f"{probe_name}/destination"
        (workspace_root / source).write_bytes(b"source")
        rename_no_replace(workspace_root, source, destination)
        (workspace_root / source).write_bytes(b"replacement")
        try:
            rename_no_replace(workspace_root, source, destination)
        except FileExistsError as err:
            if (workspace_root / destination).read_bytes() != b"source":
                msg = "native no-replace rename modified an existing destination"
                raise NativePatchOperationError(errno.EIO, msg) from err
        else:
            msg = "native no-replace rename overwrote an existing destination"
            raise NativePatchOperationError(errno.EIO, msg)
    finally:
        for child in probe_root.iterdir() if probe_root.exists() else ():
            child.unlink()
        if probe_root.exists():
            probe_root.rmdir()


def create_directory(workspace_root: Path, relative_path: str, *, mode: int) -> os.stat_result:
    """Create one absent directory through its pinned, no-follow parent descriptor."""
    with _opened_parent(workspace_root, relative_path) as (parent_fd, name):
        os.mkdir(name, mode=mode, dir_fd=parent_fd)
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)


def unlink_file(workspace_root: Path, relative_path: str) -> None:
    """Unlink one file through its pinned, no-follow parent descriptor."""
    with _opened_parent(workspace_root, relative_path) as (parent_fd, name):
        os.unlink(name, dir_fd=parent_fd)


def rename_no_replace(workspace_root: Path, source_path: str, destination_path: str) -> None:
    """Atomically rename an entry only when its destination is absent."""
    _require_native_no_replace_backend()
    with (
        _opened_parent(workspace_root, source_path) as (source_parent_fd, source_name),
        _opened_parent(workspace_root, destination_path) as (destination_parent_fd, destination_name),
    ):
        if sys.platform == "darwin":
            _darwin_renameatx_no_replace(source_parent_fd, source_name, destination_parent_fd, destination_name)
        else:
            _linux_renameat2_no_replace(source_parent_fd, source_name, destination_parent_fd, destination_name)


def rename_replace(workspace_root: Path, source_path: str, destination_path: str) -> None:
    """Rename an already-validated staged payload through pinned parent descriptors."""
    with (
        _opened_parent(workspace_root, source_path) as (source_parent_fd, source_name),
        _opened_parent(workspace_root, destination_path) as (destination_parent_fd, destination_name),
    ):
        os.rename(source_name, destination_name, src_dir_fd=source_parent_fd, dst_dir_fd=destination_parent_fd)


@contextmanager
def _opened_parent(workspace_root: Path, relative_path: str) -> Iterator[tuple[int, str]]:
    components = _path_components(relative_path)
    root_fd = os.open(workspace_root, _DIRECTORY_OPEN_FLAGS)
    descriptors = [root_fd]
    try:
        for component in components[:-1]:
            descriptors.append(os.open(component, _DIRECTORY_OPEN_FLAGS, dir_fd=descriptors[-1]))
        yield descriptors[-1], components[-1]
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _path_components(relative_path: str) -> tuple[str, ...]:
    components = tuple(component for component in relative_path.split("/") if component)
    if not components or any(component in {".", ".."} for component in components):
        msg = "native patch paths must be non-empty workspace-relative paths"
        raise ValueError(msg)
    return components


def _require_native_no_replace_backend() -> None:
    if not native_no_replace_backend_available():
        msg = "selected native no-replace patch backend is unavailable"
        raise NativePatchOperationError(errno.ENOTSUP, msg)


def _linux_renameat2_no_replace(source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
    """Perform atomic Linux renameat2 with RENAME_NOREPLACE."""
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = libc.renameat2
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_fd,
        os.fsencode(source_name),
        destination_fd,
        os.fsencode(destination_name),
        _LINUX_RENAME_NOREPLACE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), destination_name)


def _darwin_renameatx_no_replace(source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameatx_np = libc.renameatx_np
    renameatx_np.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameatx_np.restype = ctypes.c_int
    result = renameatx_np(
        source_fd,
        os.fsencode(source_name),
        destination_fd,
        os.fsencode(destination_name),
        _DARWIN_RENAME_EXCL | _DARWIN_RENAME_NOFOLLOW_ANY,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), destination_name)


__all__ = [
    "NativePatchOperationError",
    "create_directory",
    "native_no_replace_backend_available",
    "prove_native_no_replace",
    "rename_no_replace",
    "rename_replace",
    "unlink_file",
]
