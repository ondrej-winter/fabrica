"""Tests for staged git changes DTOs."""

from dataclasses import FrozenInstanceError

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_MAX_GIT_CONTEXT_CHANGED_FILES,
    DEFAULT_MAX_STAGED_DIFF_CHARS,
    GitStagedDiff,
    GitStagedDiffBounds,
    GitStagedFile,
    GitStagedFileList,
    GitStagedFileStatus,
)


def test_staged_diff_preserves_bounded_text_and_safe_metadata() -> None:
    diff = GitStagedDiff(text="diff --git a/file.py b/file.py\n+print('hi')\n", metadata={"file_count": 1})

    assert diff.text == "diff --git a/file.py b/file.py\n+print('hi')\n"
    assert diff.metadata == {"file_count": 1}


def test_staged_diff_rejects_empty_and_oversized_text() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        GitStagedDiff(text="\n")

    with pytest.raises(ValueError, match="configured bound"):
        GitStagedDiff(text="abcd", bounds=GitStagedDiffBounds(max_chars=3))


def test_staged_diff_bounds_respect_staged_diff_limit() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        GitStagedDiffBounds(max_chars=0)

    with pytest.raises(ValueError, match="staged git diff bound"):
        GitStagedDiffBounds(max_chars=DEFAULT_MAX_STAGED_DIFF_CHARS + 1)


def test_staged_diff_is_immutable_boundary_value() -> None:
    diff = GitStagedDiff(text="diff --git a/file.py b/file.py\n")

    with pytest.raises(FrozenInstanceError):
        setattr(diff, "text", "changed")  # noqa: B010


def test_staged_file_accepts_safe_relative_path_and_status() -> None:
    staged_file = GitStagedFile(path="src/package/file.py", status=GitStagedFileStatus.MODIFIED)

    assert staged_file.path == "src/package/file.py"
    assert staged_file.status is GitStagedFileStatus.MODIFIED


@pytest.mark.parametrize(
    "path",
    ["", " file.py", "file.py ", "/absolute/file.py", "../file.py", "src/../file.py", "."],
)
def test_staged_file_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError, match="staged file path"):
        GitStagedFile(path=path, status=GitStagedFileStatus.MODIFIED)


def test_staged_file_status_is_closed_set() -> None:
    assert GitStagedFileStatus("R") is GitStagedFileStatus.RENAMED

    with pytest.raises(ValueError, match="is not a valid"):
        GitStagedFileStatus("?")


def test_staged_file_list_is_immutable_and_validates_membership() -> None:
    staged_files = GitStagedFileList(
        files=(
            GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED),
            GitStagedFile(path="tests/test_file.py", status=GitStagedFileStatus.ADDED),
        ),
    )

    assert staged_files.contains_path("src/file.py") is True
    assert staged_files.contains_path("docs/file.md") is False
    with pytest.raises(ValueError, match="staged file path"):
        staged_files.contains_path("../src/file.py")
    with pytest.raises(FrozenInstanceError):
        setattr(staged_files, "files", ())  # noqa: B010


def test_staged_file_list_rejects_empty_list() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        GitStagedFileList(files=())


def test_staged_file_list_rejects_oversized_lists() -> None:
    files = tuple(
        GitStagedFile(path=f"src/file_{index}.py", status=GitStagedFileStatus.MODIFIED)
        for index in range(DEFAULT_MAX_GIT_CONTEXT_CHANGED_FILES + 1)
    )

    with pytest.raises(ValueError, match="configured bound"):
        GitStagedFileList(files=files)
