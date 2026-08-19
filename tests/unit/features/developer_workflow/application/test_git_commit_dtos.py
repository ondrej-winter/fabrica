"""Tests for approved git commit creation DTOs."""

from dataclasses import FrozenInstanceError

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    CreateGitCommitCommand,
    GitCommitResult,
)


def test_create_git_commit_command_preserves_approved_message_exactly() -> None:
    message = "\nfeat(developer-workflow): add confirmed commit boundary\n\nBody text.\n"

    command = CreateGitCommitCommand(message=message)

    assert command.message == message


@pytest.mark.parametrize("message", ["", " ", "\n\t"])
def test_create_git_commit_command_rejects_empty_message(message: str) -> None:
    with pytest.raises(ValueError, match="commit message must not be empty"):
        CreateGitCommitCommand(message=message)


def test_git_commit_result_allows_missing_or_valid_short_hash() -> None:
    assert GitCommitResult().short_hash is None
    assert GitCommitResult(short_hash=" abc123 ").short_hash == "abc123"


def test_git_commit_result_rejects_empty_short_hash() -> None:
    with pytest.raises(ValueError, match="short_hash must not be empty"):
        GitCommitResult(short_hash=" ")


def test_git_commit_dtos_are_immutable_boundary_values() -> None:
    command = CreateGitCommitCommand(message="feat: add boundary")

    with pytest.raises(FrozenInstanceError):
        command.message = "changed"  # ty: ignore[invalid-assignment]
