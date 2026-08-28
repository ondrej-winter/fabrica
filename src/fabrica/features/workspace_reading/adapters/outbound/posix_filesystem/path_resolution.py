"""Descriptor-based, fail-closed workspace file opening for POSIX hosts."""

import errno
import os
import stat
import sys
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Self

PATH_OUTSIDE_WORKSPACE_CODE = "PATH_OUTSIDE_WORKSPACE"
PATH_ESCAPES_WORKSPACE_MESSAGE = "path escapes the workspace"
NOT_A_FILE_CODE = "NOT_A_FILE"
NOT_A_FILE_MESSAGE = "path does not identify a file"
INVALID_PATH_CODE = "INVALID_PATH"
INVALID_PATH_MESSAGE = "path must be workspace-relative"
IO_ERROR_CODE = "IO_ERROR"
UNSUPPORTED_PLATFORM_MESSAGE = "secure POSIX workspace reading is unsupported on this platform"


@dataclass(slots=True)
class WorkspacePathResolutionError(Exception):
    """Stable category for a failed secure workspace file open."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class OpenedWorkspaceFile:
    """A regular file descriptor opened under a pinned workspace root."""

    file_descriptor: int
    stat_result: os.stat_result

    def close(self) -> None:
        """Close the owned file descriptor exactly once."""
        if self.file_descriptor >= 0:
            os.close(self.file_descriptor)
            self.file_descriptor = -1

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def open_workspace_file(workspace_root: Path, relative_path: str) -> OpenedWorkspaceFile:
    """Open one regular workspace file without resolve-then-open containment checks.

    Every traversed directory is pinned by descriptor. Symlinks are read explicitly
    and their targets are expanded only within that descriptor-rooted traversal.
    """
    _require_supported_capabilities()
    root_fd = _open_root(workspace_root)
    directory_fds = [root_fd]
    pending = deque(_validate_relative_path(relative_path))
    try:
        while pending:
            component = pending.popleft()
            is_final_component = not pending
            if component == ".":
                continue
            if component == "..":
                if len(directory_fds) == 1:
                    raise WorkspacePathResolutionError(PATH_OUTSIDE_WORKSPACE_CODE, PATH_ESCAPES_WORKSPACE_MESSAGE)
                os.close(directory_fds.pop())
                continue
            if is_final_component:
                opened = _open_final_component(directory_fds[-1], component, pending)
                if opened is not None:
                    return opened
                continue
            _open_directory_component(directory_fds, component, pending)
        raise WorkspacePathResolutionError(NOT_A_FILE_CODE, NOT_A_FILE_MESSAGE)
    finally:
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)


def _require_supported_capabilities() -> None:
    required = ("O_DIRECTORY", "O_NOFOLLOW")
    if sys.platform not in {"darwin", "linux"} or any(not hasattr(os, capability) for capability in required):
        raise WorkspacePathResolutionError(IO_ERROR_CODE, UNSUPPORTED_PLATFORM_MESSAGE)


def _open_root(workspace_root: Path) -> int:
    try:
        return os.open(workspace_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as err:
        raise _translate_os_error(err) from err


def _open_directory_component(directory_fds: list[int], component: str, pending: deque[str]) -> None:
    parent_fd = directory_fds[-1]
    try:
        child_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except OSError as err:
        if err.errno in {errno.ELOOP, errno.ENOTDIR} and _try_expand_symlink_target(parent_fd, component, pending):
            return
        raise _translate_os_error(err) from err
    directory_fds.append(child_fd)


def _open_final_component(parent_fd: int, component: str, pending: deque[str]) -> OpenedWorkspaceFile | None:
    try:
        file_descriptor = os.open(component, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except OSError as err:
        if err.errno == errno.ELOOP and _try_expand_symlink_target(parent_fd, component, pending):
            return None
        raise _translate_os_error(err) from err
    try:
        stat_result = os.fstat(file_descriptor)
    except OSError as err:
        os.close(file_descriptor)
        raise _translate_os_error(err) from err
    if not stat.S_ISREG(stat_result.st_mode):
        os.close(file_descriptor)
        raise _not_a_regular_file_error()
    return OpenedWorkspaceFile(file_descriptor=file_descriptor, stat_result=stat_result)


def _try_expand_symlink_target(parent_fd: int, component: str, pending: deque[str]) -> bool:
    try:
        target = os.readlink(component, dir_fd=parent_fd)
    except OSError as err:
        if err.errno == errno.EINVAL:
            return False
        raise _translate_os_error(err) from err
    if target.startswith("/"):
        message = "absolute symlink targets are not allowed"
        raise WorkspacePathResolutionError(PATH_OUTSIDE_WORKSPACE_CODE, message)
    target_components = tuple(part for part in target.split("/") if part not in {"", "."})
    if not target_components:
        code = "INVALID_PATH"
        message = "symlink target is empty"
        raise WorkspacePathResolutionError(code, message)
    pending.extendleft(reversed(target_components))
    return True


def _validate_relative_path(relative_path: str) -> Iterable[str]:
    if not relative_path or relative_path.startswith("/") or "\\" in relative_path:
        raise WorkspacePathResolutionError(INVALID_PATH_CODE, INVALID_PATH_MESSAGE)
    return tuple(part for part in relative_path.split("/") if part)


def _translate_os_error(err: OSError) -> WorkspacePathResolutionError:
    if isinstance(err, FileNotFoundError):
        return WorkspacePathResolutionError("NOT_FOUND", "workspace path does not exist")
    if isinstance(err, PermissionError):
        return WorkspacePathResolutionError("PERMISSION_DENIED", "workspace path cannot be read")
    if err.errno in {errno.ENOTDIR, errno.EISDIR}:
        return WorkspacePathResolutionError(NOT_A_FILE_CODE, NOT_A_FILE_MESSAGE)
    return WorkspacePathResolutionError("IO_ERROR", "workspace path could not be opened safely")


def _not_a_regular_file_error() -> WorkspacePathResolutionError:
    return WorkspacePathResolutionError(NOT_A_FILE_CODE, "path does not identify a regular file")


__all__ = ["OpenedWorkspaceFile", "WorkspacePathResolutionError", "open_workspace_file"]
