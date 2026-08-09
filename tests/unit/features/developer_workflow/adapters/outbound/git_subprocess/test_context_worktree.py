"""Tests for read-only git worktree context subprocess behavior."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_subprocess import (
    GitCommandResult,
    GitContextSubprocessLoader,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitContextDiffBounds,
    GitContextFailureCategory,
)
from fabrica.features.developer_workflow.application.ports import GitContextLoadError


@dataclass
class FakeGitRunner:
    """Deterministic fake for worktree context git subprocess calls."""

    results: list[GitCommandResult]
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        return self.results.pop(0)


def test_worktree_status_summary_loads_status_and_head_hash_with_configured_runner() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(
                returncode=0,
                stdout="## feature/read-only...origin/feature/read-only [ahead 1]\n"
                "M  staged.py\n"
                " M unstaged.py\n"
                "?? notes.txt\n",
            ),
            GitCommandResult(returncode=0, stdout="abc1234\n"),
        ]
    )

    summary = GitContextSubprocessLoader(
        working_directory=Path("repo"),
        timeout_seconds=2.5,
        runner=runner,
    ).load_status_summary()

    assert summary.branch == "feature/read-only"
    assert summary.upstream == "origin/feature/read-only"
    assert summary.head_short_hash == "abc1234"
    assert summary.staged_count == 1
    assert summary.unstaged_count == 1
    assert summary.untracked_count == 1
    assert summary.staged_paths == ("staged.py",)
    assert summary.unstaged_paths == ("unstaged.py",)
    assert summary.untracked_paths == ("notes.txt",)
    assert runner.calls == [
        (("git", "--no-pager", "status", "--short", "--branch"), Path("repo"), 2.5),
        (("git", "--no-pager", "rev-parse", "--short", "HEAD"), Path("repo"), 2.5),
    ]


def test_worktree_unstaged_files_lists_tracked_unstaged_changes() -> None:
    runner = FakeGitRunner(results=[GitCommandResult(returncode=0, stdout="M\tsrc/file.py\nR100\told.py\tnew.py\n")])

    files = GitContextSubprocessLoader(runner=runner).list_unstaged_files()

    assert [(file.status.value, file.path, file.old_path) for file in files.files] == [
        ("M", "src/file.py", None),
        ("R", "new.py", "old.py"),
    ]
    assert runner.calls == [(("git", "--no-pager", "diff", "--name-status"), None, 10.0)]


def test_worktree_unstaged_files_maps_oversized_file_list_safely() -> None:
    output = "".join(f"M\tsrc/file_{index}.py\n" for index in range(201))

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(
            runner=FakeGitRunner(results=[GitCommandResult(returncode=0, stdout=output)])
        ).list_unstaged_files()

    assert exc_info.value.category is GitContextFailureCategory.OVERSIZED_OUTPUT
    assert "src/file_" not in str(exc_info.value.metadata)


@pytest.mark.parametrize("method_name", ["list_unstaged_files", "load_unstaged_diff"])
def test_worktree_unstaged_context_fails_when_no_tracked_unstaged_changes(method_name: str) -> None:
    runner = FakeGitRunner(results=[GitCommandResult(returncode=0, stdout="")])

    with pytest.raises(GitContextLoadError) as exc_info:
        getattr(GitContextSubprocessLoader(runner=runner), method_name)()

    assert exc_info.value.category is GitContextFailureCategory.NO_MATCHING_CHANGES


def test_worktree_unstaged_diff_returns_bounded_diff_with_narrowing_suggestion() -> None:
    diff_text = "diff --git a/src/file.py b/src/file.py\n+change\n"

    diff = GitContextSubprocessLoader(
        runner=FakeGitRunner(results=[GitCommandResult(returncode=0, stdout=diff_text)])
    ).load_unstaged_diff()

    assert diff.text == diff_text
    assert diff.metadata["suggestion"] == (
        "Use git_unstaged_files followed by git_unstaged_file_diff to inspect a narrower change."
    )


def test_worktree_unstaged_diff_maps_oversized_output_safely() -> None:
    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(
            bounds=GitContextDiffBounds(max_chars=5),
            runner=FakeGitRunner(results=[GitCommandResult(returncode=0, stdout="abcdef")]),
        ).load_unstaged_diff()

    assert exc_info.value.category is GitContextFailureCategory.OVERSIZED_OUTPUT
    assert exc_info.value.metadata["suggestion"] == (
        "Use git_unstaged_files followed by git_unstaged_file_diff to inspect a narrower change."
    )
    assert "abcdef" not in str(exc_info.value.metadata)


def test_worktree_unstaged_file_diff_validates_membership_before_diffing() -> None:
    diff_text = "diff --git a/src/file.py b/src/file.py\n+change\n"
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="M\tsrc/file.py\n"),
            GitCommandResult(returncode=0, stdout=diff_text),
        ]
    )

    diff = GitContextSubprocessLoader(runner=runner).load_unstaged_file_diff("src/file.py")

    assert diff.text == diff_text
    assert runner.calls == [
        (("git", "--no-pager", "diff", "--name-status"), None, 10.0),
        (("git", "--no-pager", "diff", "--", "src/file.py"), None, 10.0),
    ]


@pytest.mark.parametrize(
    ("path", "category"),
    [
        ("../secret.py", GitContextFailureCategory.INVALID_ARGUMENT),
        ("docs/other.md", GitContextFailureCategory.NO_MATCHING_CHANGES),
    ],
)
def test_worktree_unstaged_file_diff_rejects_unsafe_or_unmatched_paths(
    path: str,
    category: GitContextFailureCategory,
) -> None:
    runner = FakeGitRunner(results=[GitCommandResult(returncode=0, stdout="M\tsrc/file.py\n")])

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).load_unstaged_file_diff(path)

    assert exc_info.value.category is category
    assert len(runner.calls) == 1


def test_worktree_context_maps_git_failure_without_raw_stderr() -> None:
    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(
            runner=FakeGitRunner(results=[GitCommandResult(returncode=128, stderr="fatal: private path")])
        ).load_status_summary()

    assert exc_info.value.category is GitContextFailureCategory.GIT_FAILED
    assert "private path" not in str(exc_info.value.metadata)
