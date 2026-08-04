"""Read-only subprocess adapter for loading staged git changes."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING, Protocol

from fabrica.features.developer_workflow.application.dtos import (
    GitStagedChangesFailureCategory,
    GitStagedDiff,
    GitStagedDiffBounds,
    GitStagedFile,
    GitStagedFileList,
    GitStagedFileStatus,
)
from fabrica.features.developer_workflow.application.ports import GitStagedChangesLoadError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

GIT_STAGED_DIFF_ARGV = ("git", "--no-pager", "diff", "--staged")
GIT_STAGED_NAME_STATUS_ARGV = (*GIT_STAGED_DIFF_ARGV, "--name-status")
DEFAULT_GIT_TIMEOUT_SECONDS = 10.0
_DECODE_ERROR_MESSAGE = "git staged diff output could not be decoded as UTF-8"
_GIT_FAILED_MESSAGE = "git staged diff failed"
_GIT_START_FAILED_MESSAGE = "git staged diff failed to start"
_GIT_TIMED_OUT_MESSAGE = "git staged diff timed out"
_GIT_UNAVAILABLE_MESSAGE = "git executable is unavailable"
_NO_STAGED_CHANGES_MESSAGE = "no staged git changes were found"
_NOT_REPOSITORY_MESSAGE = "current directory is not inside a git repository"
_OVERSIZED_DIFF_MESSAGE = "staged git diff exceeds the configured bound"
_UNSTAGED_FILE_PATH_MESSAGE = "requested staged file path is not currently staged"
_UNSAFE_FILE_PATH_MESSAGE = "requested staged file path is not safe"
_UNSUPPORTED_NAME_STATUS_MESSAGE = "git staged file list output is not supported"
_REGULAR_NAME_STATUS_FIELD_COUNT = 2
_RENAME_COPY_NAME_STATUS_FIELD_COUNT = 3


@dataclass(frozen=True, slots=True)
class GitCommandResult:
    """Process-shaped result returned by the injectable git command runner."""

    returncode: int
    stdout: str | bytes = ""
    stderr: str | bytes = ""


class GitCommandRunner(Protocol):
    """Adapter-local subprocess boundary for deterministic tests."""

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        """Run a git command and return captured output."""
        ...


class GitStagedChangesSubprocessLoader:
    """Load staged git diff text through a read-only git subprocess command."""

    def __init__(
        self,
        *,
        working_directory: Path | None = None,
        bounds: GitStagedDiffBounds | None = None,
        timeout_seconds: float = DEFAULT_GIT_TIMEOUT_SECONDS,
        runner: GitCommandRunner | None = None,
        verbose_diagnostics: bool = False,
    ) -> None:
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be positive"
            raise ValueError(msg)
        self._working_directory = working_directory
        self._bounds = bounds or GitStagedDiffBounds()
        self._timeout_seconds = timeout_seconds
        self._runner = runner or _run_git_command
        self._verbose_diagnostics = verbose_diagnostics

    def load(self) -> GitStagedDiff:
        """Load currently staged git diff text using the legacy local method name."""
        return self.load_diff()

    def load_diff(self) -> GitStagedDiff:
        """Load currently staged git diff text without mutating repository state."""
        result, duration_seconds = self._run_git(GIT_STAGED_DIFF_ARGV)
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            message = _NO_STAGED_CHANGES_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.NO_STAGED_CHANGES,
                duration_seconds=duration_seconds,
            )
        try:
            return GitStagedDiff(
                text=stdout,
                bounds=self._bounds,
                metadata={"duration_seconds": round(duration_seconds, 6)},
            )
        except ValueError as err:
            message = _OVERSIZED_DIFF_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.OVERSIZED_DIFF,
                duration_seconds=duration_seconds,
            ) from err

    def load_file_diff(self, path: str) -> GitStagedDiff:
        """Load staged git diff text for one currently staged safe relative path."""
        try:
            is_staged = self.list_files().contains_path(path)
        except ValueError as err:
            raise self._load_error(
                _UNSAFE_FILE_PATH_MESSAGE,
                category=GitStagedChangesFailureCategory.GIT_FAILED,
            ) from err
        if not is_staged:
            raise self._load_error(
                _UNSTAGED_FILE_PATH_MESSAGE,
                category=GitStagedChangesFailureCategory.GIT_FAILED,
            )

        result, duration_seconds = self._run_git((*GIT_STAGED_DIFF_ARGV, "--", path))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            message = _NO_STAGED_CHANGES_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.NO_STAGED_CHANGES,
                duration_seconds=duration_seconds,
            )
        try:
            return GitStagedDiff(
                text=stdout,
                bounds=self._bounds,
                metadata={"duration_seconds": round(duration_seconds, 6)},
            )
        except ValueError as err:
            message = _OVERSIZED_DIFF_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.OVERSIZED_DIFF,
                duration_seconds=duration_seconds,
            ) from err

    def list_files(self) -> GitStagedFileList:
        """List staged file paths and statuses without mutating repository state."""
        result, duration_seconds = self._run_git(GIT_STAGED_NAME_STATUS_ARGV)
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            message = _NO_STAGED_CHANGES_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.NO_STAGED_CHANGES,
                duration_seconds=duration_seconds,
            )
        try:
            files = tuple(_parse_name_status_line(line) for line in stdout.splitlines() if line.strip())
            return GitStagedFileList(files=files)
        except ValueError as err:
            raise self._load_error(
                _UNSUPPORTED_NAME_STATUS_MESSAGE,
                category=GitStagedChangesFailureCategory.GIT_FAILED,
                duration_seconds=duration_seconds,
            ) from err

    def _run_git(self, argv: Sequence[str]) -> tuple[GitCommandResult, float]:
        started = monotonic()
        try:
            result = self._runner(
                argv,
                cwd=self._working_directory,
                timeout_seconds=self._timeout_seconds,
            )
        except FileNotFoundError as err:
            message = _GIT_UNAVAILABLE_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.GIT_UNAVAILABLE,
            ) from err
        except subprocess.TimeoutExpired as err:
            message = _GIT_TIMED_OUT_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.TIMED_OUT,
                duration_seconds=monotonic() - started,
            ) from err
        except OSError as err:
            message = _GIT_START_FAILED_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.GIT_FAILED,
            ) from err
        return result, monotonic() - started

    def _decode(self, value: str | bytes) -> str:
        if isinstance(value, str):
            return value
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as err:
            message = _DECODE_ERROR_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.DECODE_ERROR,
            ) from err

    def _non_zero_error(
        self,
        *,
        stderr: str,
        returncode: int,
        duration_seconds: float,
    ) -> GitStagedChangesLoadError:
        category = GitStagedChangesFailureCategory.GIT_FAILED
        message = _GIT_FAILED_MESSAGE
        stderr_lower = stderr.lower()
        if "not a git repository" in stderr_lower:
            category = GitStagedChangesFailureCategory.NOT_A_REPOSITORY
            message = _NOT_REPOSITORY_MESSAGE
        return self._load_error(
            message,
            category=category,
            returncode=returncode,
            duration_seconds=duration_seconds,
        )

    def _load_error(
        self,
        message: str,
        *,
        category: GitStagedChangesFailureCategory,
        returncode: int | None = None,
        duration_seconds: float | None = None,
    ) -> GitStagedChangesLoadError:
        metadata: dict[str, str | int | float | bool | None] = {
            "category": category.value,
            "diagnostic_mode": "verbose" if self._verbose_diagnostics else "safe",
        }
        if returncode is not None:
            metadata["returncode"] = returncode
        if duration_seconds is not None:
            metadata["duration_seconds"] = round(duration_seconds, 6)
        if self._verbose_diagnostics and self._working_directory is not None:
            metadata["working_directory"] = str(self._working_directory)
        return GitStagedChangesLoadError(message, category=category, metadata=metadata)


def _run_git_command(argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
    completed = subprocess.run(  # noqa: S603
        list(argv),
        check=False,
        capture_output=True,
        cwd=cwd,
        shell=False,
        timeout=timeout_seconds,
    )
    return GitCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _parse_name_status_line(line: str) -> GitStagedFile:
    fields = line.split("\t")
    if len(fields) < _REGULAR_NAME_STATUS_FIELD_COUNT:
        msg = "staged name-status record must include status and path"
        raise ValueError(msg)
    status = GitStagedFileStatus(fields[0][0])
    if status in {GitStagedFileStatus.RENAMED, GitStagedFileStatus.COPIED}:
        if len(fields) != _RENAME_COPY_NAME_STATUS_FIELD_COUNT:
            msg = "rename and copy records must include old and new paths"
            raise ValueError(msg)
        path = fields[2]
    elif len(fields) == _REGULAR_NAME_STATUS_FIELD_COUNT:
        path = fields[1]
    else:
        msg = "staged name-status record has unexpected path fields"
        raise ValueError(msg)
    return GitStagedFile(path=path, status=status)
