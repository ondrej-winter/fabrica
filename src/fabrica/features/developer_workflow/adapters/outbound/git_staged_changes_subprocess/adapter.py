"""Read-only subprocess adapter for loading staged git changes."""

from __future__ import annotations

import asyncio
import subprocess
from time import monotonic
from typing import TYPE_CHECKING

from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_subprocess.command_runner import (
    GitCommandResult,
    GitCommandRunner,
    run_git_command,
)
from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_subprocess.commands import (
    DEFAULT_GIT_TIMEOUT_SECONDS,
    GIT_STAGED_DIFF_ARGV,
    GIT_STAGED_FILE_LIST_ARGV,
    git_staged_file_diff_argv,
)
from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_subprocess.errors import (
    DECODE_ERROR_MESSAGE,
    GIT_FAILED_MESSAGE,
    GIT_START_FAILED_MESSAGE,
    GIT_TIMED_OUT_MESSAGE,
    GIT_UNAVAILABLE_MESSAGE,
    NO_STAGED_CHANGES_MESSAGE,
    NOT_REPOSITORY_MESSAGE,
    OVERSIZED_DIFF_MESSAGE,
    UNSAFE_FILE_PATH_MESSAGE,
    UNSTAGED_FILE_PATH_MESSAGE,
    UNSUPPORTED_NAME_STATUS_MESSAGE,
)
from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_subprocess.parsing import (
    parse_name_status_line,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitStagedChangesFailureCategory,
    GitStagedDiff,
    GitStagedDiffBounds,
    GitStagedFileList,
)
from fabrica.features.developer_workflow.application.ports import GitStagedChangesLoadError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ["GitCommandResult", "GitCommandRunner", "GitStagedChangesSubprocessLoader"]


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
        self._runner = runner or run_git_command
        self._verbose_diagnostics = verbose_diagnostics

    def load_diff(self) -> GitStagedDiff:
        """Load currently staged git diff text without mutating repository state."""
        result, duration_seconds = self._run_git(GIT_STAGED_DIFF_ARGV)
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            message = NO_STAGED_CHANGES_MESSAGE
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
            message = OVERSIZED_DIFF_MESSAGE
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
                UNSAFE_FILE_PATH_MESSAGE,
                category=GitStagedChangesFailureCategory.GIT_FAILED,
            ) from err
        if not is_staged:
            raise self._load_error(
                UNSTAGED_FILE_PATH_MESSAGE,
                category=GitStagedChangesFailureCategory.GIT_FAILED,
            )

        result, duration_seconds = self._run_git(git_staged_file_diff_argv(path))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            message = NO_STAGED_CHANGES_MESSAGE
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
            message = OVERSIZED_DIFF_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.OVERSIZED_DIFF,
                duration_seconds=duration_seconds,
            ) from err

    async def load_file_diff_async(self, path: str) -> GitStagedDiff:
        """Load staged git diff text for one safe path without blocking the event loop."""
        return await asyncio.to_thread(self.load_file_diff, path)

    def list_files(self) -> GitStagedFileList:
        """List staged file paths and statuses without mutating repository state."""
        result, duration_seconds = self._run_git(GIT_STAGED_FILE_LIST_ARGV)
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            message = NO_STAGED_CHANGES_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.NO_STAGED_CHANGES,
                duration_seconds=duration_seconds,
            )
        try:
            files = tuple(parse_name_status_line(line) for line in stdout.splitlines() if line.strip())
            return GitStagedFileList(files=files)
        except ValueError as err:
            raise self._load_error(
                UNSUPPORTED_NAME_STATUS_MESSAGE,
                category=GitStagedChangesFailureCategory.GIT_FAILED,
                duration_seconds=duration_seconds,
            ) from err

    async def list_files_async(self) -> GitStagedFileList:
        """List staged file paths and statuses without blocking the event loop."""
        return await asyncio.to_thread(self.list_files)

    def _run_git(self, argv: Sequence[str]) -> tuple[GitCommandResult, float]:
        started = monotonic()
        try:
            result = self._runner(
                argv,
                cwd=self._working_directory,
                timeout_seconds=self._timeout_seconds,
            )
        except FileNotFoundError as err:
            message = GIT_UNAVAILABLE_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.GIT_UNAVAILABLE,
            ) from err
        except subprocess.TimeoutExpired as err:
            message = GIT_TIMED_OUT_MESSAGE
            raise self._load_error(
                message,
                category=GitStagedChangesFailureCategory.TIMED_OUT,
                duration_seconds=monotonic() - started,
            ) from err
        except OSError as err:
            message = GIT_START_FAILED_MESSAGE
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
            message = DECODE_ERROR_MESSAGE
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
        message = GIT_FAILED_MESSAGE
        stderr_lower = stderr.lower()
        if "not a git repository" in stderr_lower:
            category = GitStagedChangesFailureCategory.NOT_A_REPOSITORY
            message = NOT_REPOSITORY_MESSAGE
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
