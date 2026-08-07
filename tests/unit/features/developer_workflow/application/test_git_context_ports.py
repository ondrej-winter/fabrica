"""Tests for read-only git context application ports."""

from fabrica.features.developer_workflow.application.dtos import (
    GitBranchAheadBehind,
    GitCommitDetails,
    GitCommitLog,
    GitContextChangedFileList,
    GitContextDiff,
    GitContextFailureCategory,
    GitContextLogCount,
    GitMergeBase,
    GitStatusSummary,
)
from fabrica.features.developer_workflow.application.ports import (
    GitCommitContextLoader,
    GitContextLoadError,
    GitRefContextLoader,
    GitWorktreeContextLoader,
)


def test_git_context_error_carries_category_and_safe_metadata_copy() -> None:
    metadata = {"category": "invalid_argument", "argument": "path"}

    error = GitContextLoadError(
        "invalid git context path",
        category=GitContextFailureCategory.INVALID_ARGUMENT,
        metadata=metadata,
    )
    metadata["argument"] = "changed"

    assert error.category is GitContextFailureCategory.INVALID_ARGUMENT
    assert error.metadata == {"category": "invalid_argument", "argument": "path"}


def test_worktree_context_port_uses_application_boundary_types() -> None:
    annotations = GitWorktreeContextLoader.load_unstaged_file_diff.__annotations__
    assert annotations == {"path": str, "return": GitContextDiff}
    assert GitWorktreeContextLoader.load_status_summary.__annotations__["return"] is GitStatusSummary
    assert GitWorktreeContextLoader.list_unstaged_files.__annotations__["return"] is GitContextChangedFileList


def test_commit_context_port_uses_application_boundary_types() -> None:
    assert GitCommitContextLoader.list_commits.__annotations__ == {
        "count": GitContextLogCount | None,
        "return": GitCommitLog,
    }
    assert GitCommitContextLoader.load_commit_details.__annotations__ == {
        "commit": str,
        "return": GitCommitDetails,
    }
    assert GitCommitContextLoader.list_commit_changed_files.__annotations__["return"] is GitContextChangedFileList
    assert GitCommitContextLoader.load_commit_diff.__annotations__["return"] is GitContextDiff
    assert GitCommitContextLoader.load_commit_file_diff.__annotations__ == {
        "commit": str,
        "path": str,
        "return": GitContextDiff,
    }


def test_ref_context_port_uses_application_boundary_types() -> None:
    assert GitRefContextLoader.list_ref_changed_files.__annotations__["return"] is GitContextChangedFileList
    assert GitRefContextLoader.load_ref_diff.__annotations__["return"] is GitContextDiff
    assert GitRefContextLoader.load_ref_file_diff.__annotations__ == {
        "base_ref": str,
        "head_ref": str,
        "path": str,
        "return": GitContextDiff,
    }
    assert GitRefContextLoader.load_branch_ahead_behind.__annotations__ == {
        "base_ref": str | None,
        "return": GitBranchAheadBehind,
    }
    assert GitRefContextLoader.load_merge_base.__annotations__ == {
        "base_ref": str,
        "head_ref": str,
        "return": GitMergeBase,
    }


def test_git_context_ports_are_exported_from_application_ports_package() -> None:
    assert GitWorktreeContextLoader.__name__ == "GitWorktreeContextLoader"
    assert GitCommitContextLoader.__name__ == "GitCommitContextLoader"
    assert GitRefContextLoader.__name__ == "GitRefContextLoader"


def test_git_context_port_return_types_are_imported_application_dtos() -> None:
    assert GitStatusSummary.__name__ == "GitStatusSummary"
    assert GitContextChangedFileList.__name__ == "GitContextChangedFileList"
    assert GitContextDiff.__name__ == "GitContextDiff"
    assert GitContextLogCount.__name__ == "GitContextLogCount"
    assert GitCommitLog.__name__ == "GitCommitLog"
    assert GitCommitDetails.__name__ == "GitCommitDetails"
    assert GitBranchAheadBehind.__name__ == "GitBranchAheadBehind"
    assert GitMergeBase.__name__ == "GitMergeBase"
