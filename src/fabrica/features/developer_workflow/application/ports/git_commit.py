"""Application-owned port for approved git commit creation."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.developer_workflow.application.dtos import (
    CreateGitCommitCommand,
    GitCommitResult,
    SafeGitStagedChangesMetadataValue,
)


class GitCommitError(Exception):
    """Application-safe failure raised when approved git commit creation fails."""

    def __init__(
        self,
        message: str,
        *,
        metadata: Mapping[str, SafeGitStagedChangesMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})


class GitCommitCreator(Protocol):
    """Outbound port for creating a git commit from an approved message."""

    def create_commit(self, command: CreateGitCommitCommand) -> GitCommitResult:
        """Create a git commit from the already-approved commit message."""
        ...
