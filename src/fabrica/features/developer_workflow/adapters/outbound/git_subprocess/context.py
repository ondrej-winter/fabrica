"""Shared subprocess foundation for read-only git context adapters."""

from __future__ import annotations

import subprocess
from time import monotonic
from typing import TYPE_CHECKING

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.command_runner import (
    GitCommandResult,
    GitCommandRunner,
    run_git_command,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.context_commands import (
    DEFAULT_GIT_CONTEXT_TIMEOUT_SECONDS,
    GIT_CONTEXT_STATUS_SUMMARY_ARGV,
    GIT_HEAD_SHORT_HASH_ARGV,
    GIT_UNSTAGED_DIFF_ARGV,
    GIT_UNSTAGED_FILE_LIST_ARGV,
    git_commit_changed_files_argv,
    git_commit_details_argv,
    git_commit_diff_argv,
    git_commit_file_diff_argv,
    git_commit_log_argv,
    git_commit_validation_argv,
    git_ref_validation_argv,
    git_unstaged_file_diff_argv,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.context_errors import (
    DECODE_ERROR_MESSAGE,
    GIT_CONTEXT_FAILED_MESSAGE,
    GIT_CONTEXT_START_FAILED_MESSAGE,
    GIT_CONTEXT_TIMED_OUT_MESSAGE,
    GIT_UNAVAILABLE_MESSAGE,
    INVALID_COMMIT_MESSAGE,
    INVALID_REF_MESSAGE,
    NO_MATCHING_CHANGES_MESSAGE,
    NOT_REPOSITORY_MESSAGE,
    OVERSIZED_OUTPUT_MESSAGE,
    UNSAFE_ARGUMENT_MESSAGE,
    UNSUPPORTED_OUTPUT_MESSAGE,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.context_parsing import (
    parse_commit_details,
    parse_commit_log,
    parse_context_name_status_line,
    parse_status_summary,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitCommitDetails,
    GitCommitLog,
    GitContextChangedFileList,
    GitContextDiff,
    GitContextDiffBounds,
    GitContextFailureCategory,
    GitContextLogCount,
    GitStatusSummary,
    validate_git_context_relative_path,
)
from fabrica.features.developer_workflow.application.ports import GitContextLoadError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ["GitContextSubprocessLoader"]


class GitContextSubprocessLoader:
    """Provide shared safe subprocess behavior for read-only git context loaders."""

    def __init__(
        self,
        *,
        working_directory: Path | None = None,
        bounds: GitContextDiffBounds | None = None,
        timeout_seconds: float = DEFAULT_GIT_CONTEXT_TIMEOUT_SECONDS,
        runner: GitCommandRunner | None = None,
        verbose_diagnostics: bool = False,
    ) -> None:
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be positive"
            raise ValueError(msg)
        self._working_directory = working_directory
        self._bounds = bounds or GitContextDiffBounds()
        self._timeout_seconds = timeout_seconds
        self._runner = runner or run_git_command
        self._verbose_diagnostics = verbose_diagnostics

    def load_status_summary(self) -> GitStatusSummary:
        """Load a bounded summary of the current repository worktree state."""
        result, duration_seconds = self._run_git(GIT_CONTEXT_STATUS_SUMMARY_ARGV)
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)

        head_short_hash = self._load_head_short_hash()
        try:
            return parse_status_summary(stdout, head_short_hash=head_short_hash)
        except ValueError as err:
            raise self._load_error(
                UNSUPPORTED_OUTPUT_MESSAGE,
                category=GitContextFailureCategory.GIT_FAILED,
                duration_seconds=duration_seconds,
            ) from err

    def list_unstaged_files(self) -> GitContextChangedFileList:
        """List tracked files with unstaged changes."""
        result, duration_seconds = self._run_git(GIT_UNSTAGED_FILE_LIST_ARGV)
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            raise self._load_error(
                NO_MATCHING_CHANGES_MESSAGE,
                category=GitContextFailureCategory.NO_MATCHING_CHANGES,
                duration_seconds=duration_seconds,
            )
        try:
            files = tuple(parse_context_name_status_line(line) for line in stdout.splitlines() if line.strip())
            return GitContextChangedFileList(files=files)
        except ValueError as err:
            raise self._load_error(
                UNSUPPORTED_OUTPUT_MESSAGE,
                category=GitContextFailureCategory.GIT_FAILED,
                duration_seconds=duration_seconds,
            ) from err

    def load_unstaged_diff(self) -> GitContextDiff:
        """Load the bounded full unstaged tracked-file diff."""
        result, duration_seconds = self._run_git(GIT_UNSTAGED_DIFF_ARGV)
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            raise self._load_error(
                NO_MATCHING_CHANGES_MESSAGE,
                category=GitContextFailureCategory.NO_MATCHING_CHANGES,
                duration_seconds=duration_seconds,
            )
        return self._bounded_diff(
            stdout,
            duration_seconds=duration_seconds,
            suggestion="Use git_unstaged_files followed by git_unstaged_file_diff to inspect a narrower change.",
        )

    def load_unstaged_file_diff(self, path: str) -> GitContextDiff:
        """Load the bounded unstaged diff for one validated changed path."""
        safe_path = self._ensure_changed_path(path, self.list_unstaged_files())
        result, duration_seconds = self._run_git(git_unstaged_file_diff_argv(safe_path))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            raise self._load_error(
                NO_MATCHING_CHANGES_MESSAGE,
                category=GitContextFailureCategory.NO_MATCHING_CHANGES,
                duration_seconds=duration_seconds,
            )
        return self._bounded_diff(stdout, duration_seconds=duration_seconds)

    def list_commits(self, count: GitContextLogCount | None = None) -> GitCommitLog:
        """List recent commits from HEAD with bounded metadata."""
        result, duration_seconds = self._run_git(git_commit_log_argv(count))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        try:
            return parse_commit_log(stdout)
        except ValueError as err:
            raise self._load_error(
                UNSUPPORTED_OUTPUT_MESSAGE,
                category=GitContextFailureCategory.GIT_FAILED,
                duration_seconds=duration_seconds,
            ) from err

    def load_commit_details(self, commit: str) -> GitCommitDetails:
        """Load metadata and message details for one validated commit-ish."""
        self._ensure_commit(commit)
        result, duration_seconds = self._run_git(git_commit_details_argv(commit))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        try:
            return parse_commit_details(stdout)
        except ValueError as err:
            raise self._load_error(
                UNSUPPORTED_OUTPUT_MESSAGE,
                category=GitContextFailureCategory.GIT_FAILED,
                duration_seconds=duration_seconds,
            ) from err

    def list_commit_changed_files(self, commit: str) -> GitContextChangedFileList:
        """List files changed by one validated commit-ish without raw diff output."""
        self._ensure_commit(commit)
        result, duration_seconds = self._run_git(git_commit_changed_files_argv(commit))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            raise self._load_error(
                NO_MATCHING_CHANGES_MESSAGE,
                category=GitContextFailureCategory.NO_MATCHING_CHANGES,
                duration_seconds=duration_seconds,
            )
        try:
            files = tuple(parse_context_name_status_line(line) for line in stdout.splitlines() if line.strip())
            return GitContextChangedFileList(files=files)
        except ValueError as err:
            raise self._load_error(
                UNSUPPORTED_OUTPUT_MESSAGE,
                category=GitContextFailureCategory.GIT_FAILED,
                duration_seconds=duration_seconds,
            ) from err

    def load_commit_diff(self, commit: str) -> GitContextDiff:
        """Load the bounded full diff for one validated commit-ish."""
        self._ensure_commit(commit)
        result, duration_seconds = self._run_git(git_commit_diff_argv(commit))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            raise self._load_error(
                NO_MATCHING_CHANGES_MESSAGE,
                category=GitContextFailureCategory.NO_MATCHING_CHANGES,
                duration_seconds=duration_seconds,
            )
        return self._bounded_diff(
            stdout,
            duration_seconds=duration_seconds,
            suggestion="Use git_commit_changed_files followed by git_commit_file_diff to inspect a narrower change.",
        )

    def load_commit_file_diff(self, commit: str, path: str) -> GitContextDiff:
        """Load the bounded diff for one file changed by one validated commit-ish."""
        safe_path = self._ensure_changed_path(path, self.list_commit_changed_files(commit))
        result, duration_seconds = self._run_git(git_commit_file_diff_argv(commit, safe_path))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        if not stdout.strip():
            raise self._load_error(
                NO_MATCHING_CHANGES_MESSAGE,
                category=GitContextFailureCategory.NO_MATCHING_CHANGES,
                duration_seconds=duration_seconds,
            )
        return self._bounded_diff(stdout, duration_seconds=duration_seconds)

    def _run_git(self, argv: Sequence[str]) -> tuple[GitCommandResult, float]:
        started = monotonic()
        try:
            result = self._runner(
                argv,
                cwd=self._working_directory,
                timeout_seconds=self._timeout_seconds,
            )
        except FileNotFoundError as err:
            raise self._load_error(GIT_UNAVAILABLE_MESSAGE, category=GitContextFailureCategory.GIT_UNAVAILABLE) from err
        except subprocess.TimeoutExpired as err:
            raise self._load_error(
                GIT_CONTEXT_TIMED_OUT_MESSAGE,
                category=GitContextFailureCategory.TIMED_OUT,
                duration_seconds=monotonic() - started,
            ) from err
        except OSError as err:
            raise self._load_error(
                GIT_CONTEXT_START_FAILED_MESSAGE, category=GitContextFailureCategory.GIT_FAILED
            ) from err
        return result, monotonic() - started

    def _decode(self, value: str | bytes) -> str:
        if isinstance(value, str):
            return value
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as err:
            raise self._load_error(DECODE_ERROR_MESSAGE, category=GitContextFailureCategory.DECODE_ERROR) from err

    def _load_head_short_hash(self) -> str | None:
        result, duration_seconds = self._run_git(GIT_HEAD_SHORT_HASH_ARGV)
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        return stdout.strip() or None

    def _ensure_commit(self, commit: str) -> None:
        result, duration_seconds = self._run_git(git_commit_validation_argv(commit))
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(
                stderr=stderr,
                returncode=result.returncode,
                duration_seconds=duration_seconds,
                invalid_category=GitContextFailureCategory.INVALID_COMMIT,
                invalid_message=INVALID_COMMIT_MESSAGE,
            )

    def _ensure_ref(self, ref: str) -> None:
        result, duration_seconds = self._run_git(git_ref_validation_argv(ref))
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            raise self._non_zero_error(
                stderr=stderr,
                returncode=result.returncode,
                duration_seconds=duration_seconds,
                invalid_category=GitContextFailureCategory.INVALID_REF,
                invalid_message=INVALID_REF_MESSAGE,
            )

    def _ensure_changed_path(self, path: str, changed_files: GitContextChangedFileList) -> str:
        try:
            safe_path = validate_git_context_relative_path(path)
        except ValueError as err:
            raise self._load_error(
                UNSAFE_ARGUMENT_MESSAGE, category=GitContextFailureCategory.INVALID_ARGUMENT
            ) from err
        if not changed_files.contains_path(safe_path):
            raise self._load_error(NO_MATCHING_CHANGES_MESSAGE, category=GitContextFailureCategory.NO_MATCHING_CHANGES)
        return safe_path

    def _bounded_diff(self, text: str, *, duration_seconds: float, suggestion: str | None = None) -> GitContextDiff:
        try:
            return GitContextDiff(
                text=text,
                bounds=self._bounds,
                metadata=self._diff_metadata(duration_seconds=duration_seconds, suggestion=suggestion),
            )
        except ValueError as err:
            raise self._load_error(
                OVERSIZED_OUTPUT_MESSAGE,
                category=GitContextFailureCategory.OVERSIZED_OUTPUT,
                duration_seconds=duration_seconds,
                suggestion=suggestion,
            ) from err

    def _non_zero_error(
        self,
        *,
        stderr: str,
        returncode: int,
        duration_seconds: float,
        invalid_category: GitContextFailureCategory | None = None,
        invalid_message: str | None = None,
    ) -> GitContextLoadError:
        category = invalid_category or GitContextFailureCategory.GIT_FAILED
        message = invalid_message or GIT_CONTEXT_FAILED_MESSAGE
        stderr_lower = stderr.lower()
        if "not a git repository" in stderr_lower:
            category = GitContextFailureCategory.NOT_A_REPOSITORY
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
        category: GitContextFailureCategory,
        returncode: int | None = None,
        duration_seconds: float | None = None,
        suggestion: str | None = None,
    ) -> GitContextLoadError:
        metadata: dict[str, str | int | float | bool | None] = {
            "category": category.value,
            "diagnostic_mode": "verbose" if self._verbose_diagnostics else "safe",
        }
        if returncode is not None:
            metadata["returncode"] = returncode
        if duration_seconds is not None:
            metadata["duration_seconds"] = round(duration_seconds, 6)
        if suggestion is not None:
            metadata["suggestion"] = suggestion
        if self._verbose_diagnostics and self._working_directory is not None:
            metadata["working_directory"] = str(self._working_directory)
        return GitContextLoadError(message, category=category, metadata=metadata)

    def _diff_metadata(
        self, *, duration_seconds: float, suggestion: str | None = None
    ) -> dict[str, str | int | float | bool | None]:
        metadata: dict[str, str | int | float | bool | None] = {"duration_seconds": round(duration_seconds, 6)}
        if suggestion is not None:
            metadata["suggestion"] = suggestion
        return metadata
