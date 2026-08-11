"""Commit-message generation ports for developer workflow use cases."""

from collections.abc import Mapping
from typing import Protocol

from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageRecommendation,
    SafeGitStagedChangesMetadataValue,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)


class CommitMessageAnalysisError(Exception):
    """Application-safe failure raised when per-file evidence analysis fails."""

    def __init__(
        self,
        message: str,
        *,
        metadata: Mapping[str, SafeGitStagedChangesMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})


class CommitMessageSynthesisError(Exception):
    """Application-safe failure raised when final commit-message synthesis fails."""

    def __init__(
        self,
        message: str,
        *,
        metadata: Mapping[str, SafeGitStagedChangesMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})


class CommitMessageSkillContextLoadError(Exception):
    """Application-safe failure raised when commit-message skill context cannot load."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        metadata: Mapping[str, SafeGitStagedChangesMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.metadata = dict(metadata or {})


class StagedFileCommitMessageAnalyzer(Protocol):
    """Outbound port for analyzing one staged file into structured evidence."""

    def analyze(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        """Analyze one staged file diff for factual commit-message evidence."""
        ...


class AsyncStagedFileCommitMessageAnalyzer(Protocol):
    """Async outbound port for analyzing one staged file into structured evidence."""

    async def analyze_async(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        """Analyze one staged file diff for factual commit-message evidence."""
        ...


class CommitMessageSynthesizer(Protocol):
    """Outbound port for synthesizing a recommendation from structured evidence."""

    def synthesize(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        """Synthesize a final Conventional Commit recommendation."""
        ...


class AsyncCommitMessageSynthesizer(Protocol):
    """Async outbound port for synthesizing a recommendation from structured evidence."""

    async def synthesize_async(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        """Synthesize a final Conventional Commit recommendation."""
        ...


__all__ = [
    "AsyncCommitMessageSynthesizer",
    "AsyncStagedFileCommitMessageAnalyzer",
    "CommitMessageAnalysisError",
    "CommitMessageSkillContextLoadError",
    "CommitMessageSynthesisError",
    "CommitMessageSynthesizer",
    "StagedFileCommitMessageAnalyzer",
]
