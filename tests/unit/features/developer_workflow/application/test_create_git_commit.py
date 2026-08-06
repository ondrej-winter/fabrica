"""Tests for approved git commit creation orchestration."""

from dataclasses import dataclass, field
from typing import Any

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    CreateGitCommitCommand,
    GitCommitResult,
)
from fabrica.features.developer_workflow.application.ports import GitCommitError
from fabrica.features.developer_workflow.application.use_cases import CreateGitCommit


@dataclass
class FakeGitCommitCreator:
    result: Any = field(default_factory=lambda: GitCommitResult(short_hash="abc1234"))
    calls: list[CreateGitCommitCommand] = field(default_factory=list)
    error: GitCommitError | None = None

    def create_commit(self, command: CreateGitCommitCommand) -> GitCommitResult:
        self.calls.append(command)
        if self.error is not None:
            raise self.error
        return self.result


def test_create_git_commit_delegates_exact_approved_message_to_port() -> None:
    creator = FakeGitCommitCreator()
    command = CreateGitCommitCommand(message="feat: add boundary\n\nBody.\n")

    result = CreateGitCommit(commit_creator=creator).create(command)

    assert result == GitCommitResult(short_hash="abc1234")
    assert creator.calls == [command]
    assert creator.calls[0].message == "feat: add boundary\n\nBody.\n"


def test_create_git_commit_propagates_application_safe_port_error() -> None:
    error = GitCommitError("commit failed", metadata={"category": "git_failed", "returncode": 1})
    creator = FakeGitCommitCreator(error=error)

    with pytest.raises(GitCommitError) as error_info:
        CreateGitCommit(commit_creator=creator).create(CreateGitCommitCommand(message="feat: add boundary"))

    assert error_info.value is error
    assert error_info.value.metadata == {"category": "git_failed", "returncode": 1}


def test_create_git_commit_rejects_invalid_port_result() -> None:
    creator = FakeGitCommitCreator(result=object())

    with pytest.raises(TypeError, match="invalid result"):
        CreateGitCommit(commit_creator=creator).create(CreateGitCommitCommand(message="feat: add boundary"))


def test_git_commit_error_carries_safe_metadata_copy() -> None:
    metadata = {"category": "git_failed"}
    error = GitCommitError("commit failed", metadata=metadata)
    metadata["category"] = "changed"

    assert error.metadata == {"category": "git_failed"}
