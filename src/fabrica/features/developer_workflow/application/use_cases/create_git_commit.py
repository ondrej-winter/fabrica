"""Use case for creating an already-approved git commit."""

from fabrica.features.developer_workflow.application.dtos import (
    CreateGitCommitCommand,
    GitCommitResult,
)
from fabrica.features.developer_workflow.application.ports import GitCommitCreator


class CreateGitCommit:
    """Create a git commit through the application-owned outbound port."""

    def __init__(self, *, commit_creator: GitCommitCreator) -> None:
        self._commit_creator = commit_creator

    def create(self, command: CreateGitCommitCommand) -> GitCommitResult:
        """Create a git commit from the already-approved command message."""
        result = self._commit_creator.create_commit(command)
        if not isinstance(result, GitCommitResult):
            msg = "git commit creator returned an invalid result"
            raise TypeError(msg)
        return result
