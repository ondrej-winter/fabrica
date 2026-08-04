"""Staged git changes loading port for local agent runtime use cases."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import SafeRuntimeMetadataValue
from fabrica.features.developer_workflow.application.dtos import (
    GitStagedChangesFailureCategory,
    GitStagedDiff,
    GitStagedFileList,
)


class GitStagedChangesLoadError(Exception):
    """Application-safe failure raised when staged git changes cannot load."""

    def __init__(
        self,
        message: str,
        *,
        category: GitStagedChangesFailureCategory,
        metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.metadata = dict(metadata or {})


class GitStagedDiffLoader(Protocol):
    """Outbound port for loading full staged git diff context."""

    def load_diff(self) -> GitStagedDiff:
        """Load currently staged git diff text."""
        ...


class GitStagedChangesLoader(GitStagedDiffLoader, Protocol):
    """Outbound port for read-only staged git change inspection."""

    def list_files(self) -> GitStagedFileList:
        """List currently staged file paths and statuses."""
        ...

    def load_file_diff(self, path: str) -> GitStagedDiff:
        """Load currently staged git diff text for one safe relative path."""
        ...

    def load(self) -> GitStagedDiff:
        """Load currently staged git diff text using the legacy local method name."""
        ...
