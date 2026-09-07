"""Tests for the explicit pre-commit subprocess adapter."""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess import (
    GitCommandResult,
    PreCommitSubprocessRunner,
    pre_commit,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.pre_commit_commands import pre_commit_run_argv
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.repository_snapshot_commands import (
    GIT_TRACKED_WORKTREE_DIFF_ARGV,
    GIT_WRITE_TREE_ARGV,
)
from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS,
    GitRepositorySnapshotFailureCategory,
    PreCommitFailureCategory,
    PreCommitRunCommand,
    PreCommitRunStatus,
)
from fabrica.features.developer_workflow.application.ports import GitRepositorySnapshotLoadError, PreCommitRunError

TEST_TIMEOUT_SECONDS = 2.5
INDEX_TREE_ID = "a" * 40
TRACKED_WORKTREE_DIFF = b""


@dataclass
class FakePreCommitRunner:
    results: list[GitCommandResult | BaseException] = field(default_factory=list)
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        if self.results:
            result = self.results.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return GitCommandResult(returncode=0, stdout="passed\n")


def _snapshot_results(
    *, index_tree_id: str = INDEX_TREE_ID, tracked_worktree_diff: bytes = TRACKED_WORKTREE_DIFF
) -> list[GitCommandResult]:
    return [
        GitCommandResult(returncode=0, stdout=f"{index_tree_id}\n"),
        GitCommandResult(returncode=0, stdout=tracked_worktree_diff),
    ]


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
    runner = FakePreCommitRunner(
        results=[
            *_snapshot_results(),
            GitCommandResult(returncode=0, stdout="All hooks passed\n"),
            *_snapshot_results(),
        ]
    )

    result = PreCommitSubprocessRunner(
        working_directory=Path("repo"),
        timeout_seconds=TEST_TIMEOUT_SECONDS,
        runner=runner,
    ).run_pre_commit(PreCommitRunCommand(hook_id="ruff", all_files=True))

    assert result.status is PreCommitRunStatus.PASSED
    assert result.stdout == "All hooks passed\n"
    assert result.returncode == 0
    assert runner.calls == [
        (GIT_WRITE_TREE_ARGV, Path("repo"), TEST_TIMEOUT_SECONDS),
        (GIT_TRACKED_WORKTREE_DIFF_ARGV, Path("repo"), TEST_TIMEOUT_SECONDS),
        (("uv", "run", "pre-commit", "run", "ruff", "--all-files"), Path("repo"), TEST_TIMEOUT_SECONDS),
        (GIT_WRITE_TREE_ARGV, Path("repo"), TEST_TIMEOUT_SECONDS),
        (GIT_TRACKED_WORKTREE_DIFF_ARGV, Path("repo"), TEST_TIMEOUT_SECONDS),
    ]


def test_adapter_reports_silent_tracked_worktree_mutation_as_modified_files() -> None:
    runner = FakePreCommitRunner(
        results=[
            *_snapshot_results(),
            GitCommandResult(returncode=0, stdout="unrelated hook output\n"),
            *_snapshot_results(tracked_worktree_diff=b"diff --git a/example.txt b/example.txt\n"),
        ]
    )

    result = PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert result.status is PreCommitRunStatus.MODIFIED_FILES
    assert result.returncode == 0


def test_adapter_reports_generic_hook_failure_as_failed_status() -> None:
    runner = FakePreCommitRunner(
        results=[*_snapshot_results(), GitCommandResult(returncode=1, stderr="hook failed\n"), *_snapshot_results()]
    )

    result = PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert result.status is PreCommitRunStatus.FAILED
    assert result.stderr == "hook failed\n"


def test_adapter_prioritizes_state_mutation_over_non_zero_hook_result() -> None:
    runner = FakePreCommitRunner(
        results=[
            *_snapshot_results(),
            GitCommandResult(returncode=1, stderr="hook failed\n"),
            *_snapshot_results(index_tree_id="b" * 40),
        ]
    )

    result = PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert result.status is PreCommitRunStatus.MODIFIED_FILES
    assert result.returncode == 1


def test_adapter_allows_untracked_only_artifacts_when_snapshot_is_unchanged() -> None:
    runner = FakePreCommitRunner(
        results=[*_snapshot_results(), GitCommandResult(returncode=0, stdout="created cache\n"), *_snapshot_results()]
    )

    result = PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert result.status is PreCommitRunStatus.PASSED


def test_adapter_fails_safely_when_post_hook_snapshot_cannot_load() -> None:
    runner = FakePreCommitRunner(
        results=[
            *_snapshot_results(),
            GitCommandResult(returncode=1, stderr="hook failed\n"),
            GitCommandResult(returncode=1, stderr="fatal: index failure: secret"),
        ]
    )

    with pytest.raises(GitRepositorySnapshotLoadError, match="snapshot command failed") as exc_info:
        PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is GitRepositorySnapshotFailureCategory.GIT_FAILED
    assert "secret" not in str(exc_info.value.metadata)


def test_adapter_treats_pre_commit_missing_config_error_as_generic_failure_with_injected_runner() -> None:
    runner = FakePreCommitRunner(
        results=[
            *_snapshot_results(),
            GitCommandResult(
                returncode=1,
                stdout=("An error has occurred: InvalidConfigError:\n=====> .pre-commit-config.yaml is not a file\n"),
            ),
            *_snapshot_results(),
        ]
    )

    result = PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert result.status is PreCommitRunStatus.FAILED
    assert result.returncode == 1


def test_adapter_maps_not_repository_without_raw_stderr() -> None:
    runner = FakePreCommitRunner(
        results=[
            *_snapshot_results(),
            GitCommandResult(returncode=1, stderr="fatal: not a git repository: secret"),
            *_snapshot_results(),
        ]
    )

    with pytest.raises(PreCommitRunError, match="repository") as exc_info:
        PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is PreCommitFailureCategory.NOT_A_REPOSITORY
    assert "secret" not in str(exc_info.value.metadata)


def test_adapter_includes_working_directory_in_verbose_not_repository_diagnostics() -> None:
    runner = FakePreCommitRunner(
        results=[
            *_snapshot_results(),
            GitCommandResult(returncode=1, stderr="fatal: not a git repository"),
            *_snapshot_results(),
        ]
    )

    with pytest.raises(PreCommitRunError) as exc_info:
        PreCommitSubprocessRunner(
            working_directory=Path("repo"),
            runner=runner,
            verbose_diagnostics=True,
        ).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is PreCommitFailureCategory.NOT_A_REPOSITORY
    assert exc_info.value.metadata["working_directory"] == "repo"


@pytest.mark.parametrize(
    ("stderr", "category"),
    [
        ("fatal: not a git repository", PreCommitFailureCategory.NOT_A_REPOSITORY),
        ("fatal: unexpected failure", PreCommitFailureCategory.EXECUTION_FAILED),
    ],
)
def test_default_runner_path_maps_repository_root_failures(
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
    category: PreCommitFailureCategory,
) -> None:
    runner = FakePreCommitRunner(results=[GitCommandResult(returncode=128, stderr=stderr)])
    monkeypatch.setattr(pre_commit, "run_git_command", runner)

    with pytest.raises(PreCommitRunError) as exc_info:
        PreCommitSubprocessRunner().run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is category


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
        PreCommitSubprocessRunner(runner=FakePreCommitRunner(results=[*_snapshot_results(), error])).run_pre_commit(
            PreCommitRunCommand()
        )

    assert exc_info.value.category is category


def test_adapter_maps_decode_failure_without_raw_output() -> None:
    runner = FakePreCommitRunner(
        results=[*_snapshot_results(), GitCommandResult(returncode=1, stdout=b"\xff"), *_snapshot_results()]
    )

    with pytest.raises(PreCommitRunError, match="decoded") as exc_info:
        PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is PreCommitFailureCategory.DECODE_ERROR
    assert "\xff" not in str(exc_info.value.metadata)


def test_adapter_rejects_oversized_output() -> None:
    runner = FakePreCommitRunner(
        results=[
            *_snapshot_results(),
            GitCommandResult(returncode=0, stdout="x" * (DEFAULT_MAX_PRE_COMMIT_OUTPUT_CHARS + 1)),
            *_snapshot_results(),
        ]
    )

    with pytest.raises(PreCommitRunError, match="exceeded") as exc_info:
        PreCommitSubprocessRunner(runner=runner).run_pre_commit(PreCommitRunCommand())

    assert exc_info.value.category is PreCommitFailureCategory.OVERSIZED_OUTPUT


def test_adapter_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="positive"):
        PreCommitSubprocessRunner(timeout_seconds=0)
