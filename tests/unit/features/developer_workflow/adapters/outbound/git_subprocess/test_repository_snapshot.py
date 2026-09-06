"""Tests for the repository snapshot subprocess adapter."""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess import (
    GitCommandResult,
    GitRepositorySnapshotSubprocessReader,
)
from fabrica.features.developer_workflow.adapters.outbound.git_subprocess.repository_snapshot_commands import (
    DEFAULT_MAX_GIT_REPOSITORY_SNAPSHOT_OUTPUT_BYTES,
    GIT_TRACKED_WORKTREE_DIFF_ARGV,
    GIT_WRITE_TREE_ARGV,
)
from fabrica.features.developer_workflow.application.dtos import GitRepositorySnapshotFailureCategory
from fabrica.features.developer_workflow.application.ports import GitRepositorySnapshotLoadError

TEST_TIMEOUT_SECONDS = 2.5
INDEX_TREE_ID = "a" * 40


@dataclass
class FakeGitRunner:
    results: list[GitCommandResult] = field(default_factory=list)
    error: BaseException | None = None
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.results.pop(0)


def test_snapshot_commands_use_fixed_tracked_only_git_arguments() -> None:
    assert GIT_WRITE_TREE_ARGV == ("git", "--no-pager", "write-tree")
    assert GIT_TRACKED_WORKTREE_DIFF_ARGV == (
        "git",
        "-c",
        "core.pager=cat",
        "-c",
        "core.quotePath=false",
        "-c",
        "color.ui=false",
        "--no-pager",
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--no-color",
        "--binary",
        "--ignore-submodules=none",
    )


def test_adapter_loads_index_and_tracked_worktree_snapshot_with_composition_directory() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout=f"{INDEX_TREE_ID}\n"),
            GitCommandResult(returncode=0, stdout=b"diff --git a/file.py b/file.py\n"),
        ]
    )

    snapshot = GitRepositorySnapshotSubprocessReader(
        working_directory=Path("repo"),
        timeout_seconds=TEST_TIMEOUT_SECONDS,
        runner=runner,
    ).load_snapshot()

    assert snapshot.index_tree_id == INDEX_TREE_ID
    assert snapshot.tracked_worktree_id == sha256(b"diff --git a/file.py b/file.py\n").hexdigest()
    assert runner.calls == [
        (GIT_WRITE_TREE_ARGV, Path("repo"), TEST_TIMEOUT_SECONDS),
        (GIT_TRACKED_WORKTREE_DIFF_ARGV, Path("repo"), TEST_TIMEOUT_SECONDS),
    ]


def test_adapter_load_index_tree_id_runs_only_the_index_command() -> None:
    runner = FakeGitRunner(results=[GitCommandResult(returncode=0, stdout=f"{INDEX_TREE_ID}\n")])

    assert GitRepositorySnapshotSubprocessReader(runner=runner).load_index_tree_id() == INDEX_TREE_ID
    assert [call[0] for call in runner.calls] == [GIT_WRITE_TREE_ARGV]


def test_adapter_hash_changes_when_tracked_worktree_diff_changes() -> None:
    first_runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout=f"{INDEX_TREE_ID}\n"),
            GitCommandResult(returncode=0, stdout=b""),
        ]
    )
    second_runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout=f"{INDEX_TREE_ID}\n"),
            GitCommandResult(
                returncode=0, stdout=b"diff --git a/file.py b/file.py\nold mode 100644\nnew mode 100755\n"
            ),
        ]
    )

    first = GitRepositorySnapshotSubprocessReader(runner=first_runner).load_snapshot()
    second = GitRepositorySnapshotSubprocessReader(runner=second_runner).load_snapshot()

    assert first.index_tree_id == second.index_tree_id
    assert first.tracked_worktree_id != second.tracked_worktree_id


@pytest.mark.parametrize("output", ["", "A" * 40 + "\n", "g" * 40 + "\n", f"{INDEX_TREE_ID}\nextra\n"])
def test_adapter_rejects_malformed_index_tree_output_without_raw_diagnostics(output: str) -> None:
    runner = FakeGitRunner(results=[GitCommandResult(returncode=0, stdout=output)])

    with pytest.raises(GitRepositorySnapshotLoadError, match="malformed") as exc_info:
        GitRepositorySnapshotSubprocessReader(runner=runner).load_index_tree_id()

    assert exc_info.value.category is GitRepositorySnapshotFailureCategory.MALFORMED_OUTPUT
    assert "extra" not in str(exc_info.value.metadata)


@pytest.mark.parametrize(
    ("result", "method", "category"),
    [
        (
            GitCommandResult(returncode=128, stderr="fatal: not a git repository: /private/secret"),
            "load_index_tree_id",
            GitRepositorySnapshotFailureCategory.NOT_A_REPOSITORY,
        ),
        (
            GitCommandResult(returncode=1, stderr="fatal: index failure: secret"),
            "load_index_tree_id",
            GitRepositorySnapshotFailureCategory.GIT_FAILED,
        ),
        (
            GitCommandResult(returncode=0, stdout=b"\xff"),
            "load_index_tree_id",
            GitRepositorySnapshotFailureCategory.DECODE_ERROR,
        ),
    ],
)
def test_adapter_maps_index_command_failures_safely(
    result: GitCommandResult,
    method: str,
    category: GitRepositorySnapshotFailureCategory,
) -> None:
    runner = FakeGitRunner(results=[result])

    with pytest.raises(GitRepositorySnapshotLoadError) as exc_info:
        getattr(GitRepositorySnapshotSubprocessReader(runner=runner), method)()

    assert exc_info.value.category is category
    assert "secret" not in str(exc_info.value.metadata)
    assert "/private" not in str(exc_info.value.metadata)


def test_adapter_rejects_oversized_tracked_worktree_output_before_hashing() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout=f"{INDEX_TREE_ID}\n"),
            GitCommandResult(
                returncode=0,
                stdout=b"x" * (DEFAULT_MAX_GIT_REPOSITORY_SNAPSHOT_OUTPUT_BYTES + 1),
            ),
        ]
    )

    with pytest.raises(GitRepositorySnapshotLoadError, match="exceeded") as exc_info:
        GitRepositorySnapshotSubprocessReader(runner=runner).load_snapshot()

    assert exc_info.value.category is GitRepositorySnapshotFailureCategory.MALFORMED_OUTPUT


def test_adapter_maps_non_zero_tracked_worktree_command_failure() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout=f"{INDEX_TREE_ID}\n"),
            GitCommandResult(returncode=1, stderr="fatal: tracked diff failed"),
        ]
    )

    with pytest.raises(GitRepositorySnapshotLoadError) as exc_info:
        GitRepositorySnapshotSubprocessReader(runner=runner).load_snapshot()

    assert exc_info.value.category is GitRepositorySnapshotFailureCategory.GIT_FAILED


def test_adapter_includes_working_directory_only_in_verbose_diagnostics() -> None:
    with pytest.raises(GitRepositorySnapshotLoadError) as exc_info:
        GitRepositorySnapshotSubprocessReader(
            working_directory=Path("repo"),
            verbose_diagnostics=True,
            runner=FakeGitRunner(results=[GitCommandResult(returncode=1, stderr="fatal: failed")]),
        ).load_index_tree_id()

    assert exc_info.value.metadata["working_directory"] == "repo"


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (FileNotFoundError("git"), GitRepositorySnapshotFailureCategory.GIT_UNAVAILABLE),
        (
            subprocess.TimeoutExpired(cmd=["git", "write-tree"], timeout=1.0),
            GitRepositorySnapshotFailureCategory.TIMED_OUT,
        ),
        (OSError("boom"), GitRepositorySnapshotFailureCategory.GIT_FAILED),
    ],
)
def test_adapter_maps_subprocess_failures(error: BaseException, category: GitRepositorySnapshotFailureCategory) -> None:
    with pytest.raises(GitRepositorySnapshotLoadError) as exc_info:
        GitRepositorySnapshotSubprocessReader(runner=FakeGitRunner(error=error)).load_index_tree_id()

    assert exc_info.value.category is category


def test_adapter_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="positive"):
        GitRepositorySnapshotSubprocessReader(timeout_seconds=0)
