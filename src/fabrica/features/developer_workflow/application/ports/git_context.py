"""Application-owned ports for read-only git context inspection."""

from collections.abc import Mapping
from typing import Protocol

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
    SafeGitContextMetadataValue,
)


class GitContextLoadError(Exception):
    """Application-safe failure raised when read-only git context cannot load."""

    def __init__(
        self,
        message: str,
        *,
        category: GitContextFailureCategory,
        metadata: Mapping[str, SafeGitContextMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.metadata = dict(metadata or {})


class GitWorktreeContextLoader(Protocol):
    """Outbound port for read-only worktree context inspection."""

    def load_status_summary(self) -> GitStatusSummary:
        """Load a bounded summary of the current repository worktree state."""
        ...

    def list_unstaged_files(self) -> GitContextChangedFileList:
        """List tracked files with unstaged changes."""
        ...

    def load_unstaged_diff(self) -> GitContextDiff:
        """Load the bounded full unstaged tracked-file diff."""
        ...

    def load_unstaged_file_diff(self, path: str) -> GitContextDiff:
        """Load the bounded unstaged diff for one validated changed path."""
        ...


class GitCommitContextLoader(Protocol):
    """Outbound port for read-only commit history and commit diff inspection."""

    def list_commits(self, count: GitContextLogCount | None = None) -> GitCommitLog:
        """List recent commits from HEAD with bounded metadata."""
        ...

    def load_commit_details(self, commit: str) -> GitCommitDetails:
        """Load metadata and message details for one validated commit-ish."""
        ...

    def list_commit_changed_files(self, commit: str) -> GitContextChangedFileList:
        """List files changed by one validated commit-ish without raw diff output."""
        ...

    def load_commit_diff(self, commit: str) -> GitContextDiff:
        """Load the bounded full diff for one validated commit-ish."""
        ...

    def load_commit_file_diff(self, commit: str, path: str) -> GitContextDiff:
        """Load the bounded diff for one file changed by one validated commit-ish."""
        ...


class GitRefContextLoader(Protocol):
    """Outbound port for read-only ref and range context inspection."""

    def list_ref_changed_files(self, base_ref: str, head_ref: str) -> GitContextChangedFileList:
        """List files changed between two validated refs without raw diff output."""
        ...

    def load_ref_diff(self, base_ref: str, head_ref: str) -> GitContextDiff:
        """Load the bounded full diff between two validated refs."""
        ...

    def load_ref_file_diff(self, base_ref: str, head_ref: str, path: str) -> GitContextDiff:
        """Load the bounded diff for one file changed between two validated refs."""
        ...

    def load_branch_ahead_behind(self, base_ref: str | None = None) -> GitBranchAheadBehind:
        """Load current branch ahead/behind counts against upstream or a validated base ref."""
        ...

    def load_merge_base(self, base_ref: str, head_ref: str) -> GitMergeBase:
        """Load merge-base hashes for two validated refs."""
        ...
