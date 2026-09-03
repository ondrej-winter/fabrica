"""Read-only subprocess adapter for best-effort repository snapshots."""

from __future__ import annotations

import subprocess
from hashlib import sha256
from time import monotonic
from typing import TYPE_CHECKING

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.command_runner import (
    GitCommandResult,
    GitCommandRunner,
    run_git_command,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.repository_snapshot_commands import (
    DEFAULT_GIT_REPOSITORY_SNAPSHOT_TIMEOUT_SECONDS,
    DEFAULT_MAX_GIT_REPOSITORY_SNAPSHOT_OUTPUT_BYTES,
    GIT_TRACKED_WORKTREE_DIFF_ARGV,
    GIT_WRITE_TREE_ARGV,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.repository_snapshot_errors import (
    DECODE_ERROR_MESSAGE,
    GIT_FAILED_MESSAGE,
    GIT_START_FAILED_MESSAGE,
    GIT_TIMED_OUT_MESSAGE,
    GIT_UNAVAILABLE_MESSAGE,
    MALFORMED_OUTPUT_MESSAGE,
    NOT_REPOSITORY_MESSAGE,
    OVERSIZED_OUTPUT_MESSAGE,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitRepositorySnapshot,
    GitRepositorySnapshotFailureCategory,
)
from fabrica.features.developer_workflow.application.ports import GitRepositorySnapshotLoadError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ["GitRepositorySnapshotSubprocessReader"]


class GitRepositorySnapshotSubprocessReader:
    """Observe index and tracked-worktree state through fixed git commands."""

    def __init__(
        self,
        *,
        working_directory: Path | None = None,
        timeout_seconds: float = DEFAULT_GIT_REPOSITORY_SNAPSHOT_TIMEOUT_SECONDS,
        runner: GitCommandRunner | None = None,
        verbose_diagnostics: bool = False,
    ) -> None:
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be positive"
            raise ValueError(msg)
        self._working_directory = working_directory
        self._timeout_seconds = timeout_seconds
        self._runner = runner or run_git_command
        self._verbose_diagnostics = verbose_diagnostics

    def load_snapshot(self) -> GitRepositorySnapshot:
        """Load a best-effort snapshot of index and tracked-worktree state."""
        return GitRepositorySnapshot(
            index_tree_id=self.load_index_tree_id(),
            tracked_worktree_id=self._load_tracked_worktree_id(),
        )

    def load_index_tree_id(self) -> str:
        """Load the current index tree identity without modifying repository state."""
        result, duration_seconds = self._run_git(GIT_WRITE_TREE_ARGV)
        stdout = self._decode_bounded_output(result.stdout, duration_seconds=duration_seconds)
        stderr = self._decode_bounded_output(result.stderr, duration_seconds=duration_seconds)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        return self._validate_index_tree_id(stdout, duration_seconds=duration_seconds)

    def _load_tracked_worktree_id(self) -> str:
        result, duration_seconds = self._run_git(GIT_TRACKED_WORKTREE_DIFF_ARGV)
        stdout = self._bounded_bytes(result.stdout, duration_seconds=duration_seconds)
        stderr = self._decode_bounded_output(result.stderr, duration_seconds=duration_seconds)
        if result.returncode != 0:
            raise self._non_zero_error(stderr=stderr, returncode=result.returncode, duration_seconds=duration_seconds)
        return sha256(stdout).hexdigest()

    def _run_git(self, argv: Sequence[str]) -> tuple[GitCommandResult, float]:
        started = monotonic()
        try:
            result = self._runner(argv, cwd=self._working_directory, timeout_seconds=self._timeout_seconds)
        except FileNotFoundError as err:
            raise self._load_error(
                GIT_UNAVAILABLE_MESSAGE,
                category=GitRepositorySnapshotFailureCategory.GIT_UNAVAILABLE,
            ) from err
        except subprocess.TimeoutExpired as err:
            raise self._load_error(
                GIT_TIMED_OUT_MESSAGE,
                category=GitRepositorySnapshotFailureCategory.TIMED_OUT,
                duration_seconds=monotonic() - started,
            ) from err
        except OSError as err:
            raise self._load_error(
                GIT_START_FAILED_MESSAGE,
                category=GitRepositorySnapshotFailureCategory.GIT_FAILED,
            ) from err
        return result, monotonic() - started

    def _bounded_bytes(self, value: str | bytes, *, duration_seconds: float) -> bytes:
        output = value.encode("utf-8") if isinstance(value, str) else value
        if len(output) > DEFAULT_MAX_GIT_REPOSITORY_SNAPSHOT_OUTPUT_BYTES:
            raise self._load_error(
                OVERSIZED_OUTPUT_MESSAGE,
                category=GitRepositorySnapshotFailureCategory.MALFORMED_OUTPUT,
                duration_seconds=duration_seconds,
            )
        return output

    def _decode_bounded_output(self, value: str | bytes, *, duration_seconds: float) -> str:
        output = self._bounded_bytes(value, duration_seconds=duration_seconds)
        try:
            return output.decode("utf-8")
        except UnicodeDecodeError as err:
            raise self._load_error(
                DECODE_ERROR_MESSAGE,
                category=GitRepositorySnapshotFailureCategory.DECODE_ERROR,
                duration_seconds=duration_seconds,
            ) from err

    def _validate_index_tree_id(self, output: str, *, duration_seconds: float) -> str:
        identifier = output.removesuffix("\n")
        if "\n" in identifier:
            raise self._malformed_output_error(duration_seconds=duration_seconds)
        try:
            return GitRepositorySnapshot(index_tree_id=identifier, tracked_worktree_id="0" * 64).index_tree_id
        except ValueError as err:
            raise self._malformed_output_error(duration_seconds=duration_seconds) from err

    def _non_zero_error(
        self,
        *,
        stderr: str,
        returncode: int,
        duration_seconds: float,
    ) -> GitRepositorySnapshotLoadError:
        if "not a git repository" in stderr.lower():
            return self._load_error(
                NOT_REPOSITORY_MESSAGE,
                category=GitRepositorySnapshotFailureCategory.NOT_A_REPOSITORY,
                returncode=returncode,
                duration_seconds=duration_seconds,
            )
        return self._load_error(
            GIT_FAILED_MESSAGE,
            category=GitRepositorySnapshotFailureCategory.GIT_FAILED,
            returncode=returncode,
            duration_seconds=duration_seconds,
        )

    def _malformed_output_error(self, *, duration_seconds: float) -> GitRepositorySnapshotLoadError:
        return self._load_error(
            MALFORMED_OUTPUT_MESSAGE,
            category=GitRepositorySnapshotFailureCategory.MALFORMED_OUTPUT,
            duration_seconds=duration_seconds,
        )

    def _load_error(
        self,
        message: str,
        *,
        category: GitRepositorySnapshotFailureCategory,
        returncode: int | None = None,
        duration_seconds: float | None = None,
    ) -> GitRepositorySnapshotLoadError:
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
        return GitRepositorySnapshotLoadError(message, category=category, metadata=metadata)
