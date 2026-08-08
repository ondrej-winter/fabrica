"""Tests for read-only git commit context subprocess behavior."""

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
    GitContextLogCount,
)
from fabrica.features.developer_workflow.application.ports import GitContextLoadError


@dataclass
class FakeGitRunner:
    """Deterministic fake for commit context git subprocess calls."""

    results: list[GitCommandResult]
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        return self.results.pop(0)


def test_commit_log_loads_default_bounded_recent_commit_metadata() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(
                returncode=0,
                stdout="abcdef123456\x1fabcdef1\x1fAdd context\x1f2026-08-07T18:00:00+00:00\x1fHEAD -> main\x1e",
            )
        ]
    )

    log = GitContextSubprocessLoader(working_directory=Path("repo"), runner=runner).list_commits()

    assert [(commit.short_hash, commit.subject, commit.refs) for commit in log.commits] == [
        ("abcdef1", "Add context", ("HEAD -> main",)),
    ]
    assert runner.calls == [
        (
            (
                "git",
                "--no-pager",
                "log",
                "--max-count=20",
                "--format=%H%x1f%h%x1f%s%x1f%aI%x1f%D%x1e",
                "HEAD",
            ),
            Path("repo"),
            10.0,
        )
    ]


def test_commit_log_uses_explicit_bounded_count() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(
                returncode=0,
                stdout="abcdef123456\x1fabcdef1\x1fAdd context\x1f2026-08-07T18:00:00+00:00\x1f\x1e",
            )
        ]
    )

    GitContextSubprocessLoader(runner=runner).list_commits(GitContextLogCount(count=3))

    assert runner.calls == [
        (
            (
                "git",
                "--no-pager",
                "log",
                "--max-count=3",
                "--format=%H%x1f%h%x1f%s%x1f%aI%x1f%D%x1e",
                "HEAD",
            ),
            None,
            10.0,
        )
    ]


def test_commit_details_validates_commit_before_loading_metadata_and_message() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(
                returncode=0,
                stdout="abcdef123456\x1fabcdef1\x1fparent1 parent2\x1fAda <ada@example.com>\x1f"
                "2026-08-07T18:00:00+00:00\x1f2026-08-07T18:01:00+00:00\x1f"
                "Add context\x1fHEAD -> main\x1fBody line 1\nBody line 2",
            ),
        ]
    )

    details = GitContextSubprocessLoader(
        working_directory=Path("repo"), timeout_seconds=2.5, runner=runner
    ).load_commit_details("HEAD~1")

    assert details.commit_hash == "abcdef123456"
    assert details.short_hash == "abcdef1"
    assert details.parents == ("parent1", "parent2")
    assert details.author == "Ada <ada@example.com>"
    assert details.author_date == "2026-08-07T18:00:00+00:00"
    assert details.committer_date == "2026-08-07T18:01:00+00:00"
    assert details.subject == "Add context"
    assert details.refs == ("HEAD -> main",)
    assert details.body == "Body line 1\nBody line 2"
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD~1^{commit}"), Path("repo"), 2.5),
        (
            (
                "git",
                "--no-pager",
                "show",
                "--no-patch",
                "--format=%H%x1f%h%x1f%P%x1f%an <%ae>%x1f%aI%x1f%cI%x1f%s%x1f%D%x1f%B",
                "HEAD~1",
            ),
            Path("repo"),
            2.5,
        ),
    ]


def test_commit_changed_files_validates_commit_before_listing_name_status() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(returncode=0, stdout="M\tsrc/file.py\nR100\told.py\tnew.py\n"),
        ]
    )

    changed_files = GitContextSubprocessLoader(working_directory=Path("repo"), runner=runner).list_commit_changed_files(
        "HEAD~1"
    )

    assert [(file.status.value, file.path, file.old_path) for file in changed_files.files] == [
        ("M", "src/file.py", None),
        ("R", "new.py", "old.py"),
    ]
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD~1^{commit}"), Path("repo"), 10.0),
        (
            ("git", "--no-pager", "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD~1"),
            Path("repo"),
            10.0,
        ),
    ]


def test_commit_diff_validates_commit_and_returns_bounded_diff_with_narrowing_suggestion() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(returncode=0, stdout="diff --git a/src/file.py b/src/file.py\n+change\n"),
        ]
    )

    diff = GitContextSubprocessLoader(runner=runner).load_commit_diff("HEAD")

    assert diff.text == "diff --git a/src/file.py b/src/file.py\n+change\n"
    assert diff.metadata["suggestion"] == (
        "Use git_commit_changed_files followed by git_commit_file_diff to inspect a narrower change."
    )
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"), None, 10.0),
        (("git", "--no-pager", "show", "--format=", "--no-ext-diff", "HEAD"), None, 10.0),
    ]


def test_commit_file_diff_validates_commit_path_and_changed_file_membership() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(returncode=0, stdout="M\tsrc/file.py\nR100\told.py\tnew.py\n"),
            GitCommandResult(returncode=0, stdout="diff --git a/old.py b/new.py\n+change\n"),
        ]
    )

    diff = GitContextSubprocessLoader(runner=runner).load_commit_file_diff("HEAD", "new.py")

    assert diff.text == "diff --git a/old.py b/new.py\n+change\n"
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"), None, 10.0),
        (("git", "--no-pager", "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD"), None, 10.0),
        (("git", "--no-pager", "show", "--format=", "--no-ext-diff", "HEAD", "--", "new.py"), None, 10.0),
    ]


def test_commit_file_diff_rejects_old_rename_path_before_diffing() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(returncode=0, stdout="R100\told.py\tnew.py\n"),
        ]
    )

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).load_commit_file_diff("HEAD", "old.py")

    assert exc_info.value.category is GitContextFailureCategory.NO_MATCHING_CHANGES
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"), None, 10.0),
        (("git", "--no-pager", "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD"), None, 10.0),
    ]


def test_commit_details_rejects_invalid_commit_before_loading_details() -> None:
    runner = FakeGitRunner(results=[GitCommandResult(returncode=1, stderr="fatal: bad revision private/ref")])

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).load_commit_details("missing")

    assert exc_info.value.category is GitContextFailureCategory.INVALID_COMMIT
    assert "private/ref" not in str(exc_info.value.metadata)
    assert runner.calls == [(("git", "--no-pager", "rev-parse", "--verify", "--quiet", "missing^{commit}"), None, 10.0)]


@pytest.mark.parametrize("commit", ["", "--all", "HEAD\nmain"])
def test_commit_context_rejects_unsafe_commitish_before_calling_git(commit: str) -> None:
    runner = FakeGitRunner(results=[])

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).load_commit_details(commit)

    assert exc_info.value.category is GitContextFailureCategory.INVALID_COMMIT
    assert runner.calls == []


@pytest.mark.parametrize(
    "method_name",
    ["list_commits", "load_commit_details", "list_commit_changed_files"],
)
def test_commit_context_maps_malformed_output_safely(method_name: str) -> None:
    results = [GitCommandResult(returncode=0, stdout="malformed")]
    loader = GitContextSubprocessLoader(runner=FakeGitRunner(results=results))
    if method_name == "load_commit_details":
        results.insert(0, GitCommandResult(returncode=0, stdout="abcdef123456\n"))
        action = lambda_load_commit_details(loader)
    elif method_name == "list_commit_changed_files":
        results.insert(0, GitCommandResult(returncode=0, stdout="abcdef123456\n"))
        action = lambda_list_commit_changed_files(loader)
    else:
        action = loader.list_commits

    with pytest.raises(GitContextLoadError) as exc_info:
        action()

    assert exc_info.value.category is GitContextFailureCategory.GIT_FAILED
    assert "malformed" not in str(exc_info.value.metadata)


def test_commit_changed_files_fails_when_commit_has_no_matching_changes() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(returncode=0, stdout=""),
        ]
    )

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).list_commit_changed_files("HEAD")

    assert exc_info.value.category is GitContextFailureCategory.NO_MATCHING_CHANGES


def test_commit_diff_maps_empty_and_oversized_output_safely() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(returncode=0, stdout="abcd"),
        ]
    )

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(bounds=GitContextDiffBounds(max_chars=3), runner=runner).load_commit_diff("HEAD")

    assert exc_info.value.category is GitContextFailureCategory.OVERSIZED_OUTPUT
    assert exc_info.value.metadata["suggestion"] == (
        "Use git_commit_changed_files followed by git_commit_file_diff to inspect a narrower change."
    )

    empty_runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="abcdef123456\n"),
            GitCommandResult(returncode=0, stdout=""),
        ]
    )
    with pytest.raises(GitContextLoadError) as empty_exc_info:
        GitContextSubprocessLoader(runner=empty_runner).load_commit_diff("HEAD")

    assert empty_exc_info.value.category is GitContextFailureCategory.NO_MATCHING_CHANGES


def lambda_load_commit_details(loader: GitContextSubprocessLoader):
    """Return a no-argument action that loads HEAD commit details."""

    def load_head_details() -> object:
        return loader.load_commit_details("HEAD")

    return load_head_details


def lambda_list_commit_changed_files(loader: GitContextSubprocessLoader):
    """Return a no-argument action that lists HEAD commit changed files."""

    def list_head_changed_files() -> object:
        return loader.list_commit_changed_files("HEAD")

    return list_head_changed_files


def test_commit_log_maps_non_zero_git_failure_without_raw_stderr() -> None:
    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(
            runner=FakeGitRunner(results=[GitCommandResult(returncode=128, stderr="fatal: private path")])
        ).list_commits()

    assert exc_info.value.category is GitContextFailureCategory.GIT_FAILED
    assert "private path" not in str(exc_info.value.metadata)
