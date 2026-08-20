"""Subprocess adapter for explicit pre-commit execution."""

from __future__ import annotations

import subprocess
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.command_runner import (
    GitCommandResult,
    GitCommandRunner,
    run_git_command,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.pre_commit_commands import (
    DEFAULT_PRE_COMMIT_TIMEOUT_SECONDS,
    GIT_REV_PARSE_SHOW_TOPLEVEL_ARGV,
    pre_commit_run_argv,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.pre_commit_errors import (
    DECODE_ERROR_MESSAGE,
    NOT_REPOSITORY_MESSAGE,
    OVERSIZED_OUTPUT_MESSAGE,
    PRE_COMMIT_START_FAILED_MESSAGE,
    PRE_COMMIT_TIMED_OUT_MESSAGE,
    PRE_COMMIT_UNAVAILABLE_MESSAGE,
)
from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS,
    PreCommitFailureCategory,
    PreCommitRunCommand,
    PreCommitRunResult,
    PreCommitRunStatus,
)
from fabrica.features.developer_workflow.application.ports import PreCommitRunError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["PreCommitSubprocessRunner"]

_MISSING_PRE_COMMIT_CONFIG_METADATA = "no_pre_commit_config"


class PreCommitSubprocessRunner:
    """Run pre-commit through safe non-shell subprocess calls."""

    def __init__(
        self,
        *,
        working_directory: Path | None = None,
        timeout_seconds: float = DEFAULT_PRE_COMMIT_TIMEOUT_SECONDS,
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

    def run_pre_commit(self, command: PreCommitRunCommand) -> PreCommitRunResult:
        """Run one narrow pre-commit invocation."""
        missing_config_result = self._missing_config_result()
        if missing_config_result is not None:
            return missing_config_result
        result, duration_seconds = self._run(pre_commit_run_argv(command))
        stdout = self._decode(result.stdout)
        stderr = self._decode(result.stderr)
        if "not a git repository" in stderr.lower():
            raise self._error(
                NOT_REPOSITORY_MESSAGE,
                category=PreCommitFailureCategory.NOT_A_REPOSITORY,
                returncode=result.returncode,
                duration_seconds=duration_seconds,
            )
        return PreCommitRunResult(
            status=_status_from_result(result.returncode, stdout=stdout, stderr=stderr),
            stdout=self._bounded_output(stdout, duration_seconds=duration_seconds),
            stderr=self._bounded_output(stderr, duration_seconds=duration_seconds),
            returncode=result.returncode,
            metadata={
                "duration_seconds": round(duration_seconds, 6),
                "side_effects": "pre-commit hooks may modify files or caches",
            },
        )

    def _run(self, argv: Sequence[str]) -> tuple[GitCommandResult, float]:
        started = monotonic()
        try:
            result = self._runner(argv, cwd=self._working_directory, timeout_seconds=self._timeout_seconds)
        except FileNotFoundError as err:
            raise self._error(
                PRE_COMMIT_UNAVAILABLE_MESSAGE,
                category=PreCommitFailureCategory.PRE_COMMIT_UNAVAILABLE,
            ) from err
        except subprocess.TimeoutExpired as err:
            raise self._error(
                PRE_COMMIT_TIMED_OUT_MESSAGE,
                category=PreCommitFailureCategory.TIMED_OUT,
                duration_seconds=monotonic() - started,
            ) from err
        except OSError as err:
            raise self._error(
                PRE_COMMIT_START_FAILED_MESSAGE,
                category=PreCommitFailureCategory.EXECUTION_FAILED,
            ) from err
        return result, monotonic() - started

    def _missing_config_result(self) -> PreCommitRunResult | None:
        if self._runner is not run_git_command:
            return None
        repository_root = self._repository_root()
        if not (repository_root / ".pre-commit-config.yaml").is_file():
            return PreCommitRunResult(
                status=PreCommitRunStatus.SKIPPED,
                metadata={
                    "configuration": _MISSING_PRE_COMMIT_CONFIG_METADATA,
                    "side_effects": "pre-commit was not run because no configuration file was found",
                },
            )
        return None

    def _repository_root(self) -> Path:
        result, duration_seconds = self._run(GIT_REV_PARSE_SHOW_TOPLEVEL_ARGV)
        stdout = self._decode(result.stdout).strip()
        stderr = self._decode(result.stderr)
        if result.returncode != 0:
            if "not a git repository" in stderr.lower():
                raise self._error(
                    NOT_REPOSITORY_MESSAGE,
                    category=PreCommitFailureCategory.NOT_A_REPOSITORY,
                    returncode=result.returncode,
                    duration_seconds=duration_seconds,
                )
            raise self._error(
                PRE_COMMIT_START_FAILED_MESSAGE,
                category=PreCommitFailureCategory.EXECUTION_FAILED,
                returncode=result.returncode,
                duration_seconds=duration_seconds,
            )
        return Path(stdout)

    def _decode(self, value: str | bytes) -> str:
        if isinstance(value, str):
            return value
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as err:
            raise self._error(DECODE_ERROR_MESSAGE, category=PreCommitFailureCategory.DECODE_ERROR) from err

    def _bounded_output(self, value: str, *, duration_seconds: float) -> str:
        if len(value) <= DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS:
            return value
        raise self._error(
            OVERSIZED_OUTPUT_MESSAGE,
            category=PreCommitFailureCategory.OVERSIZED_OUTPUT,
            duration_seconds=duration_seconds,
        )

    def _error(
        self,
        message: str,
        *,
        category: PreCommitFailureCategory,
        returncode: int | None = None,
        duration_seconds: float | None = None,
    ) -> PreCommitRunError:
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
        return PreCommitRunError(message, category=category, metadata=metadata)


def _status_from_result(returncode: int, *, stdout: str, stderr: str) -> PreCommitRunStatus:
    if returncode == 0:
        return PreCommitRunStatus.PASSED
    combined_output = f"{stdout}\n{stderr}".lower()
    if "files were modified by this hook" in combined_output:
        return PreCommitRunStatus.MODIFIED_FILES
    return PreCommitRunStatus.FAILED
