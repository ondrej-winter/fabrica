"""Use case for evidence-first commit-message generation."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_COMMIT_MESSAGE_SKILL_ID,
    DEFAULT_MAX_COMMIT_MESSAGE_STAGED_FILES,
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageEvidenceBundle,
    GenerateCommitMessageResult,
    SafeGitStagedChangesMetadataValue,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    AsyncCommitMessageSynthesizer,
    AsyncGitStagedChangesLoader,
    AsyncStagedFileCommitMessageAnalyzer,
    GitStagedChangesLoader,
    GitStagedChangesLoadError,
)
from fabrica.features.query_execution.application.ports import AsyncQueryExecutor
from fabrica.features.query_execution.application.use_cases import BoundedAsyncQueryExecutor


class _SyncStagedFileCommitMessageAnalyzer(Protocol):
    def analyze(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        """Analyze one staged file diff for factual commit-message evidence."""
        ...


class _SyncCommitMessageSynthesizer(Protocol):
    def synthesize(self, command: SynthesizeCommitMessageCommand):
        """Synthesize a final Conventional Commit recommendation."""
        ...


class GenerateCommitMessageError(Exception):
    """Application-safe failure raised by commit-message workflow orchestration."""

    def __init__(
        self,
        message: str,
        *,
        metadata: Mapping[str, SafeGitStagedChangesMetadataValue] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})


@dataclass(frozen=True, slots=True)
class GenerateCommitMessageOptions:
    """Execution options for evidence-first commit-message generation."""

    max_staged_files: int = DEFAULT_MAX_COMMIT_MESSAGE_STAGED_FILES
    max_parallel_analysis: int = 4

    def __post_init__(self) -> None:
        if self.max_staged_files < 1:
            msg = "max_staged_files must be at least 1"
            raise ValueError(msg)
        if self.max_parallel_analysis < 1:
            msg = "max_parallel_analysis must be at least 1"
            raise ValueError(msg)


class GenerateCommitMessage:
    """Generate a commit-message recommendation from staged-file evidence."""

    def __init__(
        self,
        *,
        staged_changes_loader: AsyncGitStagedChangesLoader,
        analyzer: AsyncStagedFileCommitMessageAnalyzer,
        synthesizer: AsyncCommitMessageSynthesizer,
        query_executor: AsyncQueryExecutor | None = None,
        options: GenerateCommitMessageOptions | None = None,
    ) -> None:
        workflow_options = options or GenerateCommitMessageOptions()
        self._staged_changes_loader = staged_changes_loader
        self._analyzer = analyzer
        self._synthesizer = synthesizer
        self._query_executor = query_executor or BoundedAsyncQueryExecutor()
        self._options = workflow_options

    def generate(self, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID) -> GenerateCommitMessageResult:
        """Run async-first staged-file analysis from a synchronous caller."""
        return asyncio.run(self.generate_async(skill_id=skill_id))

    async def generate_async(self, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID) -> GenerateCommitMessageResult:
        """Run bounded parallel staged-file analysis and synthesize a recommendation."""
        staged_files = await self._staged_changes_loader.list_files_async()
        staged_file_count = len(staged_files.files)
        if staged_file_count > self._options.max_staged_files:
            msg = "too many staged files for commit-message generation"
            raise GenerateCommitMessageError(
                msg,
                metadata={
                    "staged_file_count": staged_file_count,
                    "max_staged_files": self._options.max_staged_files,
                },
            )

        def collect_evidence(staged_file_index: int) -> Callable[[], Awaitable[StagedFileCommitEvidence]]:
            staged_file = staged_files.files[staged_file_index]

            async def operation() -> StagedFileCommitEvidence:
                try:
                    diff = await self._staged_changes_loader.load_file_diff_async(staged_file.path)
                except GitStagedChangesLoadError as err:
                    raise GitStagedChangesLoadError(
                        str(err),
                        category=err.category,
                        metadata={**err.metadata, "path": staged_file.path},
                    ) from err
                return await self._analyzer.analyze_async(
                    AnalyzeStagedFileForCommitMessageCommand(
                        staged_file=staged_file,
                        diff=diff,
                    ),
                )

            return operation

        operations = tuple(collect_evidence(index) for index in range(staged_file_count))
        evidence = await self._query_executor.gather_ordered(
            operations,
            max_concurrency=self._options.max_parallel_analysis,
        )

        try:
            evidence_bundle = CommitMessageEvidenceBundle(evidence=evidence)
        except ValueError as err:
            msg = "commit-message evidence is invalid"
            raise GenerateCommitMessageError(
                msg,
                metadata={"evidence_count": len(evidence)},
            ) from err

        recommendation = await self._synthesizer.synthesize_async(
            SynthesizeCommitMessageCommand(evidence_bundle=evidence_bundle, skill_id=skill_id),
        )
        return GenerateCommitMessageResult(recommendation=recommendation, evidence_bundle=evidence_bundle)


class SyncGitStagedChangesLoaderAdapter:
    """Async staged-git loader adapter for legacy sync staged-git loaders."""

    def __init__(self, loader: GitStagedChangesLoader) -> None:
        self._loader = loader

    async def list_files_async(self):
        """List currently staged files without blocking the event loop."""
        return await asyncio.to_thread(self._loader.list_files)

    async def load_file_diff_async(self, path: str):
        """Load one staged file diff without blocking the event loop."""
        try:
            return await asyncio.to_thread(self._loader.load_file_diff, path)
        except GitStagedChangesLoadError as err:
            raise GitStagedChangesLoadError(
                str(err),
                category=err.category,
                metadata={**err.metadata, "path": path},
            ) from err


class SyncStagedFileCommitMessageAnalyzerAdapter:
    """Async analyzer adapter for legacy sync commit-message analyzers."""

    def __init__(self, analyzer: _SyncStagedFileCommitMessageAnalyzer) -> None:
        self._analyzer = analyzer

    async def analyze_async(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        """Analyze one staged file without blocking the event loop."""
        return await asyncio.to_thread(self._analyzer.analyze, command)


class SyncCommitMessageSynthesizerAdapter:
    """Async synthesizer adapter for legacy sync commit-message synthesizers."""

    def __init__(self, synthesizer: _SyncCommitMessageSynthesizer) -> None:
        self._synthesizer = synthesizer

    async def synthesize_async(self, command: SynthesizeCommitMessageCommand):
        """Synthesize a commit-message recommendation without blocking the event loop."""
        return await asyncio.to_thread(self._synthesizer.synthesize, command)
