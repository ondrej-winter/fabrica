"""Use cases for evidence-first commit-message and commit workflows."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunStatus,
    ModelCostEvidence,
    ModelUsageEvidence,
    RuntimeObservation,
)
from fabrica.features.agent_runtime.application.ports import SkillContextLoadError
from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_COMMIT_MESSAGE_SKILL_ID,
    DEFAULT_MAX_COMMIT_MESSAGE_STAGED_FILES,
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    CreateGitCommitCommand,
    GenerateCommitMessageResult,
    GitCommitResult,
    PreCommitRunCommand,
    PreCommitRunResult,
    PreCommitRunStatus,
    SafeGitStagedChangesMetadataValue,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    AsyncCommitMessageSynthesizer,
    AsyncGitStagedChangesLoader,
    AsyncStagedFileCommitMessageAnalyzer,
    CommitMessageAnalysisError,
    CommitMessageSynthesisError,
    GitCommitCreator,
    GitCommitError,
    GitStagedChangesLoader,
    GitStagedChangesLoadError,
    PreCommitRunError,
    PreCommitRunner,
)
from fabrica.features.query_execution.application.ports import AsyncQueryFanoutExecutor
from fabrica.features.query_execution.application.use_cases import BoundedAsyncQueryFanoutExecutor


class _SyncStagedFileCommitMessageAnalyzer(Protocol):
    def analyze(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        """Analyze one staged file diff for factual commit-message evidence."""
        ...


class _SyncCommitMessageSynthesizer(Protocol):
    def synthesize(self, command: SynthesizeCommitMessageCommand):
        """Synthesize a final Conventional Commit recommendation."""
        ...


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
        query_executor: AsyncQueryFanoutExecutor | None = None,
        options: GenerateCommitMessageOptions | None = None,
    ) -> None:
        workflow_options = options or GenerateCommitMessageOptions()
        self._staged_changes_loader = staged_changes_loader
        self._analyzer = analyzer
        self._synthesizer = synthesizer
        self._query_executor = query_executor or BoundedAsyncQueryFanoutExecutor()
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


class CommitMessageGenerator(Protocol):
    """Generator protocol consumed by composed commit workflows."""

    async def generate_async(self, *, skill_id: str) -> GenerateCommitMessageResult:
        """Generate one commit-message recommendation result."""


class GitCommitter(Protocol):
    """Committer protocol consumed by the confirmed commit workflow."""

    def create(self, command: CreateGitCommitCommand) -> GitCommitResult:
        """Create a git commit from an approved command."""


@dataclass(frozen=True, slots=True)
class ConfirmedCommitWorkflowResult:
    """Result of generating a recommendation and attempting an approved commit."""

    status: LocalAgentRunStatus
    recommendation: CommitMessageRecommendation | None = None
    commit_result: GitCommitResult | None = None
    output_text: str | None = None
    observations: tuple[RuntimeObservation, ...] = ()
    usage_evidence: tuple[ModelUsageEvidence, ...] = ()
    cost_evidence: tuple[ModelCostEvidence, ...] = ()
    commit_attempted: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "usage_evidence", tuple(self.usage_evidence))
        object.__setattr__(self, "cost_evidence", tuple(self.cost_evidence))

    @property
    def succeeded(self) -> bool:
        """Return whether recommendation generation and commit creation succeeded."""
        return self.status is LocalAgentRunStatus.SUCCESS


@dataclass(frozen=True, slots=True)
class ConfirmedCommitWorkflow:
    """Application workflow for an externally approved generated git commit."""

    generator: CommitMessageGenerator
    committer: GitCommitter
    pre_commit_runner: PreCommitRunner
    evidence_recorder: "CommitMessageEvidenceRecorder | None" = None

    def run(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> ConfirmedCommitWorkflowResult:
        """Generate a recommendation and create the approved git commit."""
        return asyncio.run(self.run_async(command, skill_id=skill_id))

    def generate(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> ConfirmedCommitWorkflowResult:
        """Generate a recommendation without creating a git commit."""
        return asyncio.run(self.generate_async(command, skill_id=skill_id))

    async def run_async(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> ConfirmedCommitWorkflowResult:
        """Generate a recommendation asynchronously and create the approved git commit."""
        generation_result = await self.generate_async(command, skill_id=skill_id)
        if not generation_result.succeeded or generation_result.recommendation is None:
            return generation_result
        return self.commit(
            generation_result.recommendation,
            output_text=generation_result.output_text,
            usage_evidence=generation_result.usage_evidence,
            cost_evidence=generation_result.cost_evidence,
        )

    async def generate_async(
        self, command: object | None = None, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID
    ) -> ConfirmedCommitWorkflowResult:
        """Run pre-commit, then generate a recommendation without creating a commit."""
        selected_skill_id = getattr(command, "skill_id", skill_id)
        if self.evidence_recorder is not None:
            self.evidence_recorder.reset()
        pre_commit_result = self._run_pre_commit_gate()
        if pre_commit_result is not None:
            return pre_commit_result
        try:
            result = await self.generator.generate_async(skill_id=selected_skill_id)
        except GitStagedChangesLoadError as err:
            return self._failure_result(
                LocalAgentRunStatus.CONFIGURATION_ERROR,
                RuntimeObservation(
                    message=str(err),
                    metadata={"category": err.category, **err.metadata},
                ),
            )
        except SkillContextLoadError as err:
            return self._failure_result(
                LocalAgentRunStatus.CONFIGURATION_ERROR,
                RuntimeObservation(
                    message=str(err),
                    metadata={"category": err.category, **err.metadata},
                ),
            )
        except (GenerateCommitMessageError, ValueError) as err:
            return self._failure_result(
                LocalAgentRunStatus.CONFIGURATION_ERROR,
                RuntimeObservation(
                    message=str(err),
                    metadata={
                        "category": "invalid_commit_message_input",
                        **getattr(err, "metadata", {}),
                    },
                ),
            )
        except (CommitMessageAnalysisError, CommitMessageSynthesisError) as err:
            return self._failure_result(
                LocalAgentRunStatus.MODEL_ERROR,
                RuntimeObservation(
                    message=str(err),
                    metadata={
                        "category": "commit_message_model_failure",
                        **err.metadata,
                    },
                ),
            )

        recommendation = result.recommendation
        output_text = format_commit_message_recommendation(recommendation)

        return ConfirmedCommitWorkflowResult(
            status=LocalAgentRunStatus.SUCCESS,
            recommendation=recommendation,
            output_text=output_text,
            usage_evidence=self._usage_evidence,
            cost_evidence=self._cost_evidence,
        )

    def commit(
        self,
        recommendation: CommitMessageRecommendation,
        *,
        output_text: str | None = None,
        usage_evidence: tuple[ModelUsageEvidence, ...] | None = None,
        cost_evidence: tuple[ModelCostEvidence, ...] | None = None,
    ) -> ConfirmedCommitWorkflowResult:
        """Create a git commit from an externally approved recommendation."""
        try:
            commit_result = self.committer.create(
                CreateGitCommitCommand(message=recommendation.commit_message),
            )
        except GitCommitError as err:
            return ConfirmedCommitWorkflowResult(
                status=LocalAgentRunStatus.CONFIGURATION_ERROR,
                recommendation=recommendation,
                output_text=output_text,
                observations=(
                    RuntimeObservation(
                        message=str(err),
                        metadata={
                            "category": "git_commit_failed",
                            "commit_attempted": True,
                            **err.metadata,
                        },
                    ),
                ),
                usage_evidence=usage_evidence or self._usage_evidence,
                cost_evidence=cost_evidence or self._cost_evidence,
                commit_attempted=True,
            )

        return ConfirmedCommitWorkflowResult(
            status=LocalAgentRunStatus.SUCCESS,
            recommendation=recommendation,
            commit_result=commit_result,
            output_text=output_text,
            usage_evidence=usage_evidence or self._usage_evidence,
            cost_evidence=cost_evidence or self._cost_evidence,
            commit_attempted=True,
        )

    @property
    def _usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        return self.evidence_recorder.usage_evidence if self.evidence_recorder is not None else ()

    @property
    def _cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
        return self.evidence_recorder.cost_evidence if self.evidence_recorder is not None else ()

    def _failure_result(
        self,
        status: LocalAgentRunStatus,
        observation: RuntimeObservation,
    ) -> ConfirmedCommitWorkflowResult:
        return ConfirmedCommitWorkflowResult(
            status=status,
            observations=(observation,),
            usage_evidence=self._usage_evidence,
            cost_evidence=self._cost_evidence,
        )

    def _run_pre_commit_gate(self) -> ConfirmedCommitWorkflowResult | None:
        try:
            result = self.pre_commit_runner.run_pre_commit(PreCommitRunCommand())
        except PreCommitRunError as err:
            return self._pre_commit_failure_result(
                RuntimeObservation(
                    message=str(err),
                    metadata={"category": err.category, **err.metadata},
                ),
            )
        if result.status is PreCommitRunStatus.PASSED:
            return None
        if result.status is PreCommitRunStatus.MODIFIED_FILES:
            return self._pre_commit_failure_result(
                RuntimeObservation(
                    message=(
                        "pre-commit modified files; no commit was created. "
                        "review and stage changed files before retrying."
                    ),
                    metadata={"category": "pre_commit_modified_files", **_pre_commit_metadata(result)},
                ),
            )
        return self._pre_commit_failure_result(
            RuntimeObservation(
                message="pre-commit failed; no commit was created.",
                metadata={"category": "pre_commit_failed", **_pre_commit_metadata(result)},
            ),
        )

    def _pre_commit_failure_result(self, observation: RuntimeObservation) -> ConfirmedCommitWorkflowResult:
        return ConfirmedCommitWorkflowResult(
            status=LocalAgentRunStatus.CONFIGURATION_ERROR,
            observations=(observation,),
        )


def _pre_commit_metadata(result: PreCommitRunResult) -> dict[str, str | int | float | bool | None]:
    metadata = dict(result.metadata)
    if result.returncode is not None:
        metadata["returncode"] = result.returncode
    return metadata


class CommitMessageEvidenceRecorder(Protocol):
    """Recorder for model evidence collected during a commit-message workflow run."""

    @property
    def usage_evidence(self) -> tuple[ModelUsageEvidence, ...]:
        """Return usage evidence observed during the active workflow run."""

    @property
    def cost_evidence(self) -> tuple[ModelCostEvidence, ...]:
        """Return cost evidence observed during the active workflow run."""

    def reset(self) -> None:
        """Clear evidence from previous workflow runs."""


def format_commit_message_recommendation(recommendation: CommitMessageRecommendation) -> str:
    """Format a recommendation with the stable terminal output labels."""
    return (
        f"Summary:\n{recommendation.summary}\n\n"
        f"Rationale:\n{recommendation.rationale}\n\n"
        f"Commit message:\n{recommendation.commit_message}"
    )
