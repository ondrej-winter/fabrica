"""Tests for read-only git ref/range context subprocess behavior."""

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

EXPECTED_AHEAD_COUNT = 3
EXPECTED_BEHIND_COUNT = 2
EXPECTED_VALIDATION_CALL_COUNT = 3


@dataclass
class FakeGitRunner:
    """Deterministic fake for ref context git subprocess calls."""

    results: list[GitCommandResult]
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        return self.results.pop(0)


def test_ref_changed_files_validates_refs_before_listing_three_dot_name_status() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="head\n"),
            GitCommandResult(returncode=0, stdout="M\tsrc/file.py\nR100\told.py\tnew.py\n"),
        ]
    )

    changed_files = GitContextSubprocessLoader(working_directory=Path("repo"), runner=runner).list_ref_changed_files(
        "origin/main", "HEAD"
    )

    assert [(file.status.value, file.path, file.old_path) for file in changed_files.files] == [
        ("M", "src/file.py", None),
        ("R", "new.py", "old.py"),
    ]
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "origin/main^{commit}"), Path("repo"), 10.0),
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"), Path("repo"), 10.0),
        (("git", "--no-pager", "diff", "--name-status", "origin/main...HEAD"), Path("repo"), 10.0),
    ]


def test_ref_diff_validates_refs_and_returns_bounded_diff_with_narrowing_suggestion() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="head\n"),
            GitCommandResult(returncode=0, stdout="diff --git a/src/file.py b/src/file.py\n+change\n"),
        ]
    )

    diff = GitContextSubprocessLoader(runner=runner).load_ref_diff("origin/main", "HEAD")

    assert diff.text == "diff --git a/src/file.py b/src/file.py\n+change\n"
    assert diff.metadata["suggestion"] == (
        "Use git_ref_changed_files followed by git_ref_file_diff to inspect a narrower change."
    )
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "origin/main^{commit}"), None, 10.0),
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"), None, 10.0),
        (("git", "--no-pager", "diff", "--no-ext-diff", "origin/main...HEAD"), None, 10.0),
    ]


def test_ref_file_diff_validates_refs_path_and_changed_file_membership() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="head\n"),
            GitCommandResult(returncode=0, stdout="M\tsrc/file.py\nR100\told.py\tnew.py\n"),
            GitCommandResult(returncode=0, stdout="diff --git a/old.py b/new.py\n+change\n"),
        ]
    )

    diff = GitContextSubprocessLoader(runner=runner).load_ref_file_diff("origin/main", "HEAD", "new.py")

    assert diff.text == "diff --git a/old.py b/new.py\n+change\n"
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "origin/main^{commit}"), None, 10.0),
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"), None, 10.0),
        (("git", "--no-pager", "diff", "--name-status", "origin/main...HEAD"), None, 10.0),
        (("git", "--no-pager", "diff", "--no-ext-diff", "origin/main...HEAD", "--", "new.py"), None, 10.0),
    ]


def test_ref_file_diff_rejects_old_rename_path_before_diffing() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="head\n"),
            GitCommandResult(returncode=0, stdout="R100\told.py\tnew.py\n"),
        ]
    )

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).load_ref_file_diff("origin/main", "HEAD", "old.py")

    assert exc_info.value.category is GitContextFailureCategory.NO_MATCHING_CHANGES
    assert len(runner.calls) == EXPECTED_VALIDATION_CALL_COUNT


def test_branch_ahead_behind_defaults_to_upstream_without_fetching() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="## feature/read-only...origin/main [ahead 1, behind 2]\n"),
            GitCommandResult(returncode=0, stdout="abc1234\n"),
            GitCommandResult(returncode=0, stdout="2\t1\n"),
        ]
    )

    ahead_behind = GitContextSubprocessLoader(runner=runner).load_branch_ahead_behind()

    assert ahead_behind.current_branch == "feature/read-only"
    assert ahead_behind.base_ref == "origin/main"
    assert ahead_behind.ahead_count == 1
    assert ahead_behind.behind_count == EXPECTED_BEHIND_COUNT
    assert runner.calls == [
        (("git", "--no-pager", "status", "--short", "--branch"), None, 10.0),
        (("git", "--no-pager", "rev-parse", "--short", "HEAD"), None, 10.0),
        (("git", "--no-pager", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"), None, 10.0),
    ]


def test_branch_ahead_behind_validates_explicit_base_ref() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="## feature/read-only\n"),
            GitCommandResult(returncode=0, stdout="abc1234\n"),
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="0\t3\n"),
        ]
    )

    ahead_behind = GitContextSubprocessLoader(runner=runner).load_branch_ahead_behind("origin/main")

    assert ahead_behind.base_ref == "origin/main"
    assert ahead_behind.ahead_count == EXPECTED_AHEAD_COUNT
    assert ahead_behind.behind_count == 0
    assert runner.calls == [
        (("git", "--no-pager", "status", "--short", "--branch"), None, 10.0),
        (("git", "--no-pager", "rev-parse", "--short", "HEAD"), None, 10.0),
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "origin/main^{commit}"), None, 10.0),
        (("git", "--no-pager", "rev-list", "--left-right", "--count", "origin/main...HEAD"), None, 10.0),
    ]


def test_merge_base_validates_refs_before_loading_hashes() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="head\n"),
            GitCommandResult(returncode=0, stdout="abcdef1234567890\n"),
        ]
    )

    merge_base = GitContextSubprocessLoader(runner=runner).load_merge_base("origin/main", "HEAD")

    assert merge_base.commit_hash == "abcdef1234567890"
    assert merge_base.short_hash == "abcdef1"
    assert runner.calls == [
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "origin/main^{commit}"), None, 10.0),
        (("git", "--no-pager", "rev-parse", "--verify", "--quiet", "HEAD^{commit}"), None, 10.0),
        (("git", "--no-pager", "merge-base", "origin/main", "HEAD"), None, 10.0),
    ]


def test_ref_context_maps_empty_oversized_and_malformed_outputs_safely() -> None:
    empty_runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="head\n"),
            GitCommandResult(returncode=0, stdout=""),
        ]
    )
    with pytest.raises(GitContextLoadError) as empty_exc_info:
        GitContextSubprocessLoader(runner=empty_runner).list_ref_changed_files("origin/main", "HEAD")

    assert empty_exc_info.value.category is GitContextFailureCategory.NO_MATCHING_CHANGES

    oversized_runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="head\n"),
            GitCommandResult(returncode=0, stdout="abcdef"),
        ]
    )
    with pytest.raises(GitContextLoadError) as oversized_exc_info:
        GitContextSubprocessLoader(bounds=GitContextDiffBounds(max_chars=5), runner=oversized_runner).load_ref_diff(
            "origin/main", "HEAD"
        )

    assert oversized_exc_info.value.category is GitContextFailureCategory.OVERSIZED_OUTPUT
    assert oversized_exc_info.value.metadata["suggestion"] == (
        "Use git_ref_changed_files followed by git_ref_file_diff to inspect a narrower change."
    )
    assert "abcdef" not in str(oversized_exc_info.value.metadata)

    malformed_runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="## feature/read-only...origin/main\n"),
            GitCommandResult(returncode=0, stdout="abc1234\n"),
            GitCommandResult(returncode=0, stdout="not-counts\n"),
        ]
    )
    with pytest.raises(GitContextLoadError) as malformed_exc_info:
        GitContextSubprocessLoader(runner=malformed_runner).load_branch_ahead_behind()

    assert malformed_exc_info.value.category is GitContextFailureCategory.GIT_FAILED


def test_ref_changed_files_maps_oversized_file_list_safely() -> None:
    output = "".join(f"M\tsrc/file_{index}.py\n" for index in range(201))
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="base\n"),
            GitCommandResult(returncode=0, stdout="head\n"),
            GitCommandResult(returncode=0, stdout=output),
        ]
    )

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).list_ref_changed_files("origin/main", "HEAD")

    assert exc_info.value.category is GitContextFailureCategory.OVERSIZED_OUTPUT
    assert "src/file_" not in str(exc_info.value.metadata)


def test_ref_context_rejects_invalid_ref_before_inspection_without_raw_stderr() -> None:
    runner = FakeGitRunner(results=[GitCommandResult(returncode=1, stderr="fatal: private ref")])

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).load_ref_diff("missing", "HEAD")

    assert exc_info.value.category is GitContextFailureCategory.INVALID_REF
    assert "private ref" not in str(exc_info.value.metadata)
    assert runner.calls == [(("git", "--no-pager", "rev-parse", "--verify", "--quiet", "missing^{commit}"), None, 10.0)]


@pytest.mark.parametrize("ref", ["", "--all", "HEAD\nmain"])
def test_ref_context_rejects_unsafe_ref_before_calling_git(ref: str) -> None:
    runner = FakeGitRunner(results=[])

    with pytest.raises(GitContextLoadError) as exc_info:
        GitContextSubprocessLoader(runner=runner).load_ref_diff(ref, "HEAD")

    assert exc_info.value.category is GitContextFailureCategory.INVALID_REF
    assert runner.calls == []
