"""Tests for the staged git changes subprocess adapter."""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from fabrica.features.developer_workflow.adapters.outbound.git_staged_changes_subprocess import (
    GitCommandResult,
    GitStagedChangesSubprocessLoader,
)
from fabrica.features.developer_workflow.application.dtos import (
    GitStagedChangesFailureCategory,
    GitStagedDiffBounds,
    GitStagedFileStatus,
)
from fabrica.features.developer_workflow.application.ports import GitStagedChangesLoadError


@dataclass
class FakeGitRunner:
    result: GitCommandResult | None = None
    results: list[GitCommandResult] = field(default_factory=list)
    error: BaseException | None = None
    calls: list[tuple[tuple[str, ...], Path | None, float]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        self.calls.append((tuple(argv), cwd, timeout_seconds))
        if self.error is not None:
            raise self.error
        if self.results:
            return self.results.pop(0)
        if self.result is None:
            return GitCommandResult(returncode=0, stdout="diff --git a/file.py b/file.py\n")
        return self.result


def test_adapter_invokes_read_only_staged_diff_command() -> None:
    runner = FakeGitRunner()

    diff = GitStagedChangesSubprocessLoader(
        working_directory=Path("repo"),
        timeout_seconds=2.5,
        runner=runner,
    ).load()

    assert diff.text == "diff --git a/file.py b/file.py\n"
    assert runner.calls == [(("git", "--no-pager", "diff", "--staged"), Path("repo"), 2.5)]


def test_adapter_lists_staged_files_with_statuses() -> None:
    runner = FakeGitRunner(
        result=GitCommandResult(
            returncode=0,
            stdout="M\tsrc/file.py\nA\ttests/test_file.py\nD\told.py\n",
        ),
    )

    staged_files = GitStagedChangesSubprocessLoader(
        working_directory=Path("repo"),
        timeout_seconds=2.5,
        runner=runner,
    ).list_files()

    assert [(file.status, file.path) for file in staged_files.files] == [
        (GitStagedFileStatus.MODIFIED, "src/file.py"),
        (GitStagedFileStatus.ADDED, "tests/test_file.py"),
        (GitStagedFileStatus.DELETED, "old.py"),
    ]
    assert runner.calls == [(("git", "--no-pager", "diff", "--staged", "--name-status"), Path("repo"), 2.5)]


def test_adapter_lists_rename_and_copy_records_by_canonical_new_path() -> None:
    runner = FakeGitRunner(
        result=GitCommandResult(
            returncode=0,
            stdout="R100\told.py\tnew.py\nC075\tsrc/base.py\tsrc/copy.py\n",
        ),
    )

    staged_files = GitStagedChangesSubprocessLoader(runner=runner).list_files()

    assert [(file.status, file.path) for file in staged_files.files] == [
        (GitStagedFileStatus.RENAMED, "new.py"),
        (GitStagedFileStatus.COPIED, "src/copy.py"),
    ]


def test_adapter_loads_file_diff_after_validating_path_is_staged() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="M\tsrc/file.py\n"),
            GitCommandResult(returncode=0, stdout="diff --git a/src/file.py b/src/file.py\n+change\n"),
        ],
    )

    diff = GitStagedChangesSubprocessLoader(
        working_directory=Path("repo"),
        timeout_seconds=2.5,
        runner=runner,
    ).load_file_diff("src/file.py")

    assert diff.text == "diff --git a/src/file.py b/src/file.py\n+change\n"
    assert runner.calls == [
        (("git", "--no-pager", "diff", "--staged", "--name-status"), Path("repo"), 2.5),
        (("git", "--no-pager", "diff", "--staged", "--", "src/file.py"), Path("repo"), 2.5),
    ]


@pytest.mark.parametrize("path", ["", " file.py", "/absolute/file.py", "../file.py", "src/../file.py", "."])
def test_adapter_rejects_unsafe_file_diff_paths_before_per_file_diff(path: str) -> None:
    runner = FakeGitRunner(result=GitCommandResult(returncode=0, stdout="M\tsrc/file.py\n"))

    with pytest.raises(GitStagedChangesLoadError) as exc_info:
        GitStagedChangesSubprocessLoader(runner=runner).load_file_diff(path)

    assert exc_info.value.category is GitStagedChangesFailureCategory.GIT_FAILED
    assert runner.calls == [(("git", "--no-pager", "diff", "--staged", "--name-status"), None, 10.0)]
    if path:
        assert path not in str(exc_info.value.metadata)


def test_adapter_rejects_unstaged_file_diff_path_before_per_file_diff() -> None:
    runner = FakeGitRunner(result=GitCommandResult(returncode=0, stdout="M\tsrc/file.py\n"))

    with pytest.raises(GitStagedChangesLoadError) as exc_info:
        GitStagedChangesSubprocessLoader(runner=runner).load_file_diff("docs/other.md")

    assert exc_info.value.category is GitStagedChangesFailureCategory.GIT_FAILED
    assert runner.calls == [(("git", "--no-pager", "diff", "--staged", "--name-status"), None, 10.0)]
    assert "docs/other.md" not in str(exc_info.value.metadata)


def test_adapter_keeps_file_diff_path_after_separator_so_it_cannot_be_git_flags() -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="A\t--stat\n"),
            GitCommandResult(returncode=0, stdout="diff --git a/--stat b/--stat\n+content\n"),
        ],
    )

    GitStagedChangesSubprocessLoader(runner=runner).load_file_diff("--stat")

    assert runner.calls[-1][0] == ("git", "--no-pager", "diff", "--staged", "--", "--stat")


@pytest.mark.parametrize(
    ("file_diff_result", "category"),
    [
        (GitCommandResult(returncode=0, stdout=""), GitStagedChangesFailureCategory.NO_STAGED_CHANGES),
        (GitCommandResult(returncode=0, stdout="abcdef"), GitStagedChangesFailureCategory.OVERSIZED_DIFF),
    ],
)
def test_adapter_maps_file_diff_output_failures(
    file_diff_result: GitCommandResult,
    category: GitStagedChangesFailureCategory,
) -> None:
    runner = FakeGitRunner(
        results=[
            GitCommandResult(returncode=0, stdout="M\tsrc/file.py\n"),
            file_diff_result,
        ],
    )

    with pytest.raises(GitStagedChangesLoadError) as exc_info:
        GitStagedChangesSubprocessLoader(
            bounds=GitStagedDiffBounds(max_chars=5),
            runner=runner,
        ).load_file_diff("src/file.py")

    assert exc_info.value.category is category


def test_adapter_rejects_invalid_name_status_output_without_raw_diagnostics() -> None:
    with pytest.raises(GitStagedChangesLoadError) as exc_info:
        GitStagedChangesSubprocessLoader(
            runner=FakeGitRunner(result=GitCommandResult(returncode=0, stdout="X\t../secret.py\n")),
        ).list_files()

    assert exc_info.value.category is GitStagedChangesFailureCategory.GIT_FAILED
    assert "../secret.py" not in str(exc_info.value.metadata)


@pytest.mark.parametrize(
    ("result", "category"),
    [
        (GitCommandResult(returncode=0, stdout=""), GitStagedChangesFailureCategory.NO_STAGED_CHANGES),
        (
            GitCommandResult(returncode=128, stderr="fatal: not a git repository"),
            GitStagedChangesFailureCategory.NOT_A_REPOSITORY,
        ),
        (GitCommandResult(returncode=1, stderr="fatal: unexpected"), GitStagedChangesFailureCategory.GIT_FAILED),
        (GitCommandResult(returncode=0, stdout="abcdef"), GitStagedChangesFailureCategory.OVERSIZED_DIFF),
    ],
)
def test_adapter_maps_git_result_failures(result: GitCommandResult, category: GitStagedChangesFailureCategory) -> None:
    with pytest.raises(GitStagedChangesLoadError) as exc_info:
        GitStagedChangesSubprocessLoader(
            bounds=GitStagedDiffBounds(max_chars=5),
            runner=FakeGitRunner(result=result),
        ).load()

    assert exc_info.value.category is category
    assert exc_info.value.metadata["category"] == category.value


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (FileNotFoundError("git"), GitStagedChangesFailureCategory.GIT_UNAVAILABLE),
        (
            subprocess.TimeoutExpired(cmd=["git", "diff"], timeout=1.0),
            GitStagedChangesFailureCategory.TIMED_OUT,
        ),
        (OSError("boom"), GitStagedChangesFailureCategory.GIT_FAILED),
    ],
)
def test_adapter_maps_subprocess_failures(error: BaseException, category: GitStagedChangesFailureCategory) -> None:
    with pytest.raises(GitStagedChangesLoadError) as exc_info:
        GitStagedChangesSubprocessLoader(runner=FakeGitRunner(error=error)).load()

    assert exc_info.value.category is category


def test_adapter_maps_decode_failure_without_raw_diff_diagnostics() -> None:
    with pytest.raises(GitStagedChangesLoadError) as exc_info:
        GitStagedChangesSubprocessLoader(
            runner=FakeGitRunner(result=GitCommandResult(returncode=0, stdout=b"\xff")),
        ).load()

    assert exc_info.value.category is GitStagedChangesFailureCategory.DECODE_ERROR
    assert "\xff" not in str(exc_info.value.metadata)
