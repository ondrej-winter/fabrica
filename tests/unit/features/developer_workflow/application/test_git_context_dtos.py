"""Tests for read-only git context DTOs."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_MAX_GIT_COMMIT_MESSAGE_CHARS,
    DEFAULT_MAX_GIT_CONTEXT_CHANGED_FILES,
    DEFAULT_MAX_GIT_CONTEXT_DIFF_CHARS,
    DEFAULT_MAX_GIT_CONTEXT_STATUS_PATHS,
    MAX_GIT_CONTEXT_LOG_COUNT,
    GitBranchAheadBehind,
    GitCommitDetails,
    GitCommitLog,
    GitCommitSummary,
    GitContextChangedFile,
    GitContextChangedFileList,
    GitContextChangedFileStatus,
    GitContextDiff,
    GitContextDiffBounds,
    GitContextFailureCategory,
    GitContextLogCount,
    GitMergeBase,
    GitStatusSummary,
    validate_git_context_relative_path,
)

EXPECTED_AHEAD_COUNT = 2


def mutate_metadata(metadata: object) -> None:
    """Attempt mutation through a mutable mapping view for immutability tests."""
    cast("dict[str, object]", metadata)["duration_seconds"] = 2.0


def test_git_context_path_validation_uses_context_specific_error_wording() -> None:
    assert validate_git_context_relative_path("src/file.py") == "src/file.py"

    with pytest.raises(ValueError, match="git context path"):
        validate_git_context_relative_path("../src/file.py")


@pytest.mark.parametrize("path", ["", " file.py", "file.py ", "/absolute/file.py", "src/../file.py", "."])
def test_changed_file_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError, match="git context path"):
        GitContextChangedFile(path=path, status=GitContextChangedFileStatus.MODIFIED)


def test_changed_file_represents_rename_by_destination_path_and_old_path_metadata() -> None:
    changed_file = GitContextChangedFile(
        path="new.py",
        status=GitContextChangedFileStatus.RENAMED,
        old_path="old.py",
    )

    assert changed_file.path == "new.py"
    assert changed_file.old_path == "old.py"


def test_changed_file_requires_old_path_only_for_renames_and_copies() -> None:
    with pytest.raises(ValueError, match="must include old_path"):
        GitContextChangedFile(path="new.py", status=GitContextChangedFileStatus.RENAMED)

    with pytest.raises(ValueError, match="only valid"):
        GitContextChangedFile(path="file.py", status=GitContextChangedFileStatus.MODIFIED, old_path="old.py")


def test_changed_file_list_is_immutable_and_validates_canonical_membership() -> None:
    changed_files = GitContextChangedFileList(
        files=(
            GitContextChangedFile(path="src/file.py", status=GitContextChangedFileStatus.MODIFIED),
            GitContextChangedFile(path="new.py", status=GitContextChangedFileStatus.RENAMED, old_path="old.py"),
        ),
    )

    assert changed_files.contains_path("src/file.py") is True
    assert changed_files.contains_path("new.py") is True
    assert changed_files.contains_path("old.py") is False
    with pytest.raises(ValueError, match="git context path"):
        changed_files.contains_path("../src/file.py")
    with pytest.raises(FrozenInstanceError):
        changed_files.files = ()  # ty: ignore[invalid-assignment]


def test_changed_file_list_rejects_empty_list() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        GitContextChangedFileList(files=())


def test_changed_file_list_rejects_oversized_lists() -> None:
    files = tuple(
        GitContextChangedFile(path=f"src/file_{index}.py", status=GitContextChangedFileStatus.MODIFIED)
        for index in range(DEFAULT_MAX_GIT_CONTEXT_CHANGED_FILES + 1)
    )

    with pytest.raises(ValueError, match="configured bound"):
        GitContextChangedFileList(files=files)


def test_diff_bounds_and_log_count_use_conservative_maximums() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        GitContextDiffBounds(max_chars=0)
    with pytest.raises(ValueError, match="diff bound"):
        GitContextDiffBounds(max_chars=DEFAULT_MAX_GIT_CONTEXT_DIFF_CHARS + 1)
    with pytest.raises(ValueError, match="at least 1"):
        GitContextLogCount(count=0)
    with pytest.raises(ValueError, match="log bound"):
        GitContextLogCount(count=MAX_GIT_CONTEXT_LOG_COUNT + 1)


def test_diff_preserves_bounded_text_and_safe_metadata_copy() -> None:
    metadata = {"duration_seconds": 0.1}
    diff = GitContextDiff(text="diff --git a/file.py b/file.py\n+change\n", metadata=metadata)
    metadata["duration_seconds"] = 9.9

    assert diff.text == "diff --git a/file.py b/file.py\n+change\n"
    assert diff.metadata == {"duration_seconds": 0.1}
    with pytest.raises(TypeError):
        mutate_metadata(diff.metadata)


def test_diff_rejects_empty_and_oversized_text() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        GitContextDiff(text="\n")

    with pytest.raises(ValueError, match="configured bound"):
        GitContextDiff(text="abcd", bounds=GitContextDiffBounds(max_chars=3))


def test_status_summary_validates_counts_and_untracked_paths() -> None:
    summary = GitStatusSummary(
        branch="main",
        head_short_hash="abc1234",
        staged_count=1,
        unstaged_count=2,
        untracked_count=1,
        staged_paths=("src/staged.py",),
        unstaged_paths=("src/unstaged.py",),
        untracked_paths=("notes.txt",),
    )

    assert summary.staged_paths == ("src/staged.py",)
    assert summary.unstaged_paths == ("src/unstaged.py",)
    assert summary.untracked_paths == ("notes.txt",)
    with pytest.raises(ValueError, match="staged_count"):
        GitStatusSummary(branch="main", head_short_hash="abc1234", staged_count=-1)


def test_status_summary_rejects_oversized_path_lists() -> None:
    paths = tuple(f"src/file_{index}.py" for index in range(DEFAULT_MAX_GIT_CONTEXT_STATUS_PATHS + 1))

    with pytest.raises(ValueError, match="staged_paths"):
        GitStatusSummary(branch="main", head_short_hash="abc1234", staged_paths=paths)


def test_commit_and_ref_result_dtos_are_immutable_boundary_values() -> None:
    commit = GitCommitSummary(
        commit_hash="abcdef1234567890",
        short_hash="abcdef1",
        subject="Add feature",
        author_date="2026-08-07T18:00:00+00:00",
        refs=("HEAD -> main",),
    )
    log = GitCommitLog(commits=(commit,))
    details = GitCommitDetails(
        commit_hash="abcdef1234567890",
        short_hash="abcdef1",
        parents=("1234567",),
        author="Ada <ada@example.com>",
        author_date="2026-08-07T18:00:00+00:00",
        committer_date="2026-08-07T18:01:00+00:00",
        subject="Add feature",
    )
    ahead_behind = GitBranchAheadBehind(current_branch="feature", base_ref="origin/main", ahead_count=2, behind_count=1)
    merge_base = GitMergeBase(commit_hash="1234567890abcdef", short_hash="1234567")

    assert log.commits == (commit,)
    assert details.parents == ("1234567",)
    assert ahead_behind.ahead_count == EXPECTED_AHEAD_COUNT
    assert merge_base.short_hash == "1234567"
    with pytest.raises(FrozenInstanceError):
        commit.subject = "changed"  # ty: ignore[invalid-assignment]


def test_commit_details_rejects_oversized_message_body() -> None:
    with pytest.raises(ValueError, match="body exceeds"):
        GitCommitDetails(
            commit_hash="abcdef1234567890",
            short_hash="abcdef1",
            parents=(),
            author="Ada <ada@example.com>",
            author_date="2026-08-07T18:00:00+00:00",
            committer_date="2026-08-07T18:01:00+00:00",
            subject="Add feature",
            body="x" * (DEFAULT_MAX_GIT_COMMIT_MESSAGE_CHARS + 1),
        )


def test_failure_category_distinguishes_argument_validation_from_git_failures() -> None:
    assert GitContextFailureCategory.INVALID_ARGUMENT.value == "invalid_argument"
    assert GitContextFailureCategory.NO_MATCHING_CHANGES.value == "no_matching_changes"
    assert GitContextFailureCategory.GIT_FAILED.value == "git_failed"
