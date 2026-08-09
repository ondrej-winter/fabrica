"""Tests for the explicit pre-commit subprocess adapter."""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess import (
    GitCommandResult,
    PreCommitSubprocessRunner,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.pre_commit_commands import pre_commit_run_argv
from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS,
    PreCommitFailureCategory,
    PreCommitRunCommand,
    PreCommitRunStatus,
)
from fabrica.features.developer_workflow.application.ports import PreCommitRunError

TEST_TIMEOUT_SECONDS = 2.5


@dataclass
class FakePreCommitRunner:
    result: GitCommandResult | None = None
    error: BaseException | None = None
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.result or GitCommandResult(returncode=0, stdout="passed\n")


def test_pre_commit_command_uses_fixed_argv_and_explicit_options() -> None:
    assert pre_commit_run_argv(PreCommitRunCommand()) == ("uv", "run", "pre-commit", "run")
    assert pre_commit_run_argv(PreCommitRunCommand(hook_id="ruff", all_files=True)) == (
        "uv",
        "run",
        "pre-commit",
        "run",
        "ruff",
        "--all-files",
    )


@pytest.mark.parametrize("hook_id", ["", " ruff", "ruff ", "--all-files", "ruff;rm"])
def test_pre_commit_command_rejects_unsafe_hook_ids(hook_id: str) -> None:
    with pytest.raises(ValueError, match="hook id"):
        PreCommitRunCommand(hook_id=hook_id)


def test_adapter_runs_pre_commit_with_composition_owned_working_directory() -> None:
    runner = FakePreCommitRunner(result=GitCommandResult(returncode=0, stdout="All hooks passed\n"))

    result = PreCommitSubprocessRunner(
        working_directory=Path("repo"),
        timeout_seconds=TEST_TIMEOUT_SECONDS,
        runner=runner,
    ).run_pre_commit(PreCommitRunCommand(hook_id="ruff", all_files=True))

    assert result.status is PreCommitRunStatus.PASSED
    assert result.stdout == "All hooks passed\n"
    assert result.returncode == 0
    assert runner.calls == [
        (("uv", "run", "pre-commit", "run", "ruff", "--all-files"), Path("repo"), TEST_TIMEOUT_SECONDS),
    ]


def test_adapter_reports_modified_files_as_non_success_status() -> None:
    runner = FakePreCommitRunner(
        result=GitCommandResult(
            returncode=1,
            stdout="ruff-format................................Failed\n- files were modified by this hook\n",
        )
    )

    result = PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert result.status is PreCommitRunStatus.MODIFIED_FILES
    assert result.returncode == 1


def test_adapter_reports_generic_hook_failure_as_failed_status() -> None:
    runner = FakePreCommitRunner(result=GitCommandResult(returncode=1, stderr="hook failed\n"))

    result = PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert result.status is PreCommitRunStatus.FAILED
    assert result.stderr == "hook failed\n"


def test_adapter_maps_not_repository_without_raw_stderr() -> None:
    runner = FakePreCommitRunner(result=GitCommandResult(returncode=1, stderr="fatal: not a git repository: secret"))

    with pytest.raises(PreCommitRunError, match="repository") as exc_info:
        PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is PreCommitFailureCategory.NOT_A_REPOSITORY
    assert "secret" not in str(exc_info.value.metadata)


@pytest.mark.parametrize(
    ("error", "category", "message"),
    [
        (FileNotFoundError("uv"), PreCommitFailureCategory.PRE_COMMIT_UNAVAILABLE, "unavailable"),
        (
            subprocess.TimeoutExpired(cmd=["uv", "run", "pre-commit"], timeout=1.0),
            PreCommitFailureCategory.TIMED_OUT,
            "timed out",
        ),
        (OSError("boom"), PreCommitFailureCategory.EXECUTION_FAILED, "failed to start"),
    ],
)
def test_adapter_maps_subprocess_failures(
    error: BaseException, category: PreCommitFailureCategory, message: str
) -> None:
    with pytest.raises(PreCommitRunError, match=message) as exc_info:
        PreCommitSubprocessRunner(runner=FakePreCommitRunner(error=error)).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is category


def test_adapter_maps_decode_failure_without_raw_output() -> None:
    runner = FakePreCommitRunner(result=GitCommandResult(returncode=1, stdout=b"\xff"))

    with pytest.raises(PreCommitRunError, match="decoded") as exc_info:
        PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is PreCommitFailureCategory.DECODE_ERROR
    assert "\xff" not in str(exc_info.value.metadata)


def test_adapter_rejects_oversized_output() -> None:
    runner = FakePreCommitRunner(
        result=GitCommandResult(returncode=0, stdout="x" * (DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS + 1))
    )

    with pytest.raises(PreCommitRunError, match="exceeded") as exc_info:
        PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is PreCommitFailureCategory.OVERSIZED_OUTPUT


def test_adapter_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="positive"):
        PreCommitSubprocessRunner(timeout_seconds=0)
