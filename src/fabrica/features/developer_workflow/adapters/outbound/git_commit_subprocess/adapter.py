"""Subprocess adapter for creating approved git commits."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

from fabrica.features.developer_workflow.adapters.outbound.git_commit_subprocess.command_runner import (
    GitCommitCommandResult,
    GitCommitCommandRunner,
    run_git_commit_command,
)
from fabrica.features.developer_workflow.adapters.outbound.git_commit_subprocess.commands import (
    DEFAULT_GIT_COMMIT_TIMEOUT_SECONDS,
    GIT_REV_PARSE_SHORT_HEAD_ARGV,
    git_commit_file_argv,
)
from fabrica.features.developer_workflow.adapters.outbound.git_commit_subprocess.errors import (
    DECODE_ERROR_MESSAGE,
    GIT_COMMIT_FAILED_MESSAGE,
    GIT_COMMIT_START_FAILED_MESSAGE,
    GIT_COMMIT_TIMED_OUT_MESSAGE,
    GIT_UNAVAILABLE_MESSAGE,
    NO_STAGED_CHANGES_MESSAGE,
    NOT_REPOSITORY_MESSAGE,
)
from fabrica.features.developer_workflow.application.dtos import CreateGitCommitCommand, GitCommitResult
from fabrica.features.developer_workflow.application.ports import GitCommitError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["GitCommitCommandResult", "GitCommitSubprocessCreator"]


class GitCommitSubprocessCreator:
    """Create approved git commits through safe non-shell subprocess calls."""

    def __init__(
        self,
        *,
        working_directory: Path | None = None,
        timeout_seconds: float = DEFAULT_GIT_COMMIT_TIMEOUT_SECONDS,
        runner: GitCommitCommandRunner | None = None,
        verbose_diagnostics: bool = False,
    ) -> None:
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be positive"
            raise ValueError(msg)
        self._working_directory = working_directory
        self._timeout_seconds = timeout_seconds
        self._runner = runner or run_git_commit_command
        self._verbose_diagnostics = verbose_diagnostics

    def create_commit(self, command: CreateGitCommitCommand) -> GitCommitResult:
        """Create a git commit from an already-approved commit message."""
        with tempfile.TemporaryDirectory(prefix="fabrica-commit-message-") as temp_directory:
            message_file_path = Path(temp_directory) / "COMMIT_EDITMSG"
            message_file_path.write_text(command.message, encoding="utf-8")

            result, duration_seconds = self._run_git(git_commit_file_argv(str(message_file_path)))
            stderr = self._decode(result.stderr)
            if result.returncode != 0:
                raise self._non_zero_error(
                    stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds
                )

        return GitCommitResult(short_hash=self._load_short_hash())

    def _load_short_hash(self) -> str | None:
        try:
            result, _duration_seconds = self._run_git(GIT_REV_PARSE_SHORT_HEAD_ARGV)
            if result.returncode != 0:
                return None
            short_hash = self._decode(result.stdout).strip()
        except GitCommitError:
            return None
        return short_hash or None

    def _run_git(self, argv: Sequence[str]) -> tuple[GitCommitCommandResult, float]:
        started = monotonic()
        try:
            result = self._runner(
                argv,
                cwd=self._working_directory,
                timeout_seconds=self._timeout_seconds,
            )
        except FileNotFoundError as err:
            raise self._commit_error(
                GIT_UNAVAILABLE_MESSAGE,
                category="git_unavailable",
            ) from err
        except subprocess.TimeoutExpired as err:
            raise self._commit_error(
                GIT_COMMIT_TIMED_OUT_MESSAGE,
                category="timed_out",
                duration_seconds=monotonic() - started,
            ) from err
        except OSError as err:
            raise self._commit_error(
                GIT_COMMIT_START_FAILED_MESSAGE,
                category="git_failed",
            ) from err
        return result, monotonic() - started

    def _decode(self, value: str | bytes) -> str:
        if isinstance(value, str):
            return value
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as err:
            raise self._commit_error(DECODE_ERROR_MESSAGE, category="decode_error") from err

    def _non_zero_error(
        self,
        *,
        stderr: str,
        returncode: int,
        duration_seconds: float,
    ) -> GitCommitError:
        category = "git_failed"
        message = GIT_COMMIT_FAILED_MESSAGE
        stderr_lower = stderr.lower()
        if "not a git repository" in stderr_lower:
            category = "not_a_repository"
            message = NOT_REPOSITORY_MESSAGE
        elif "nothing to commit" in stderr_lower or "no changes added to commit" in stderr_lower:
            category = "no_staged_changes"
            message = NO_STAGED_CHANGES_MESSAGE
        return self._commit_error(
            message,
            category=category,
            returncode=returncode,
            duration_seconds=duration_seconds,
        )

    def _commit_error(
        self,
        message: str,
        *,
        category: str,
        returncode: int | None = None,
        duration_seconds: float | None = None,
    ) -> GitCommitError:
        metadata: dict[str, str | int | float | bool | None] = {
            "category": category,
            "diagnostic_mode": "verbose" if self._verbose_diagnostics else "safe",
        }
        if returncode is not None:
            metadata["returncode"] = returncode
        if duration_seconds is not None:
            metadata["duration_seconds"] = round(duration_seconds, 6)
        if self._verbose_diagnostics and self._working_directory is not None:
            metadata["working_directory"] = str(self._working_directory)
        return GitCommitError(message, metadata=metadata)
