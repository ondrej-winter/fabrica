"""Use case for evidence-first commit-message generation."""

from collections.abc import Mapping

from fabrica.features.developer_workflow.application.dtos import (
    DEFAULT_COMMIT_MESSAGE_SKILL_ID,
    DEFAULT_MAX_COMMIT_MESSAGE_STAGED_FILES,
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageEvidenceBundle,
    GenerateCommitMessageResult,
    SafeGitStagedChangesMetadataValue,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageSynthesizer,
    GitStagedChangesLoader,
    GitStagedChangesLoadError,
    StagedFileCommitMessageAnalyzer,
)


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


class GenerateCommitMessage:
    """Generate a commit-message recommendation from staged-file evidence."""

    def __init__(
        self,
        *,
        staged_changes_loader: GitStagedChangesLoader,
        analyzer: StagedFileCommitMessageAnalyzer,
        synthesizer: CommitMessageSynthesizer,
        max_staged_files: int = DEFAULT_MAX_COMMIT_MESSAGE_STAGED_FILES,
    ) -> None:
        if max_staged_files < 1:
            msg = "max_staged_files must be at least 1"
            raise ValueError(msg)
        self._staged_changes_loader = staged_changes_loader
        self._analyzer = analyzer
        self._synthesizer = synthesizer
        self._max_staged_files = max_staged_files

    def generate(self, *, skill_id: str = DEFAULT_COMMIT_MESSAGE_SKILL_ID) -> GenerateCommitMessageResult:
        """Run sequential staged-file analysis and synthesize a recommendation."""
        staged_files = self._staged_changes_loader.list_files()
        staged_file_count = len(staged_files.files)
        if staged_file_count > self._max_staged_files:
            msg = "too many staged files for commit-message generation"
            raise GenerateCommitMessageError(
                msg,
                metadata={
                    "staged_file_count": staged_file_count,
                    "max_staged_files": self._max_staged_files,
                },
            )

        evidence = []
        for staged_file in staged_files.files:
            try:
                diff = self._staged_changes_loader.load_file_diff(staged_file.path)
            except GitStagedChangesLoadError as err:
                raise GitStagedChangesLoadError(
                    str(err),
                    category=err.category,
                    metadata={**err.metadata, "path": staged_file.path},
                ) from err
            evidence.append(
                self._analyzer.analyze(
                    AnalyzeStagedFileForCommitMessageCommand(
                        staged_file=staged_file,
                        diff=diff,
                    ),
                )
            )

        try:
            evidence_bundle = CommitMessageEvidenceBundle(evidence=tuple(evidence))
        except ValueError as err:
            msg = "commit-message evidence is invalid"
            raise GenerateCommitMessageError(
                msg,
                metadata={"evidence_count": len(evidence)},
            ) from err

        recommendation = self._synthesizer.synthesize(
            SynthesizeCommitMessageCommand(evidence_bundle=evidence_bundle, skill_id=skill_id),
        )
        return GenerateCommitMessageResult(recommendation=recommendation, evidence_bundle=evidence_bundle)
