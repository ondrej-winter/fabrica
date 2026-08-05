"""Tests for evidence-first commit-message application ports."""

from dataclasses import dataclass, field

from fabrica.features.developer_workflow.application.dtos import (
    AnalyzeStagedFileForCommitMessageCommand,
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    GitStagedDiff,
    GitStagedFile,
    GitStagedFileStatus,
    StagedFileCommitEvidence,
    SynthesizeCommitMessageCommand,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageAnalysisError,
    CommitMessageSynthesisError,
)


@dataclass
class FakeAnalyzer:
    calls: list[AnalyzeStagedFileForCommitMessageCommand] = field(default_factory=list)

    def analyze(self, command: AnalyzeStagedFileForCommitMessageCommand) -> StagedFileCommitEvidence:
        self.calls.append(command)
        return _evidence(command.staged_file)


@dataclass
class FakeSynthesizer:
    calls: list[SynthesizeCommitMessageCommand] = field(default_factory=list)

    def synthesize(self, command: SynthesizeCommitMessageCommand) -> CommitMessageRecommendation:
        self.calls.append(command)
        return CommitMessageRecommendation(
            summary="Adds evidence contracts.",
            rationale="The evidence points to a developer-workflow application contract change.",
            commit_message="feat(developer-workflow): add commit message evidence contracts",
        )


def test_analyzer_port_shape_uses_developer_workflow_dtos() -> None:
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    command = AnalyzeStagedFileForCommitMessageCommand(
        staged_file=staged_file,
        diff=GitStagedDiff(text="diff --git a/src/file.py b/src/file.py\n+change\n"),
    )

    evidence = FakeAnalyzer().analyze(command)

    assert evidence.staged_file == staged_file


def test_synthesizer_port_shape_uses_structured_evidence_dtos() -> None:
    staged_file = GitStagedFile(path="src/file.py", status=GitStagedFileStatus.MODIFIED)
    bundle = CommitMessageEvidenceBundle(evidence=(_evidence(staged_file),))
    command = SynthesizeCommitMessageCommand(evidence_bundle=bundle)

    recommendation = FakeSynthesizer().synthesize(command)

    assert recommendation.commit_message == "feat(developer-workflow): add commit message evidence contracts"


def test_commit_message_port_errors_carry_safe_metadata() -> None:
    analysis_error = CommitMessageAnalysisError("analysis failed", metadata={"path": "src/file.py"})
    synthesis_error = CommitMessageSynthesisError("synthesis failed", metadata={"evidence_count": 1})

    assert analysis_error.metadata == {"path": "src/file.py"}
    assert synthesis_error.metadata == {"evidence_count": 1}


def _evidence(staged_file: GitStagedFile) -> StagedFileCommitEvidence:
    return StagedFileCommitEvidence(
        staged_file=staged_file,
        summary="Adds evidence-first commit-message DTOs.",
        category="architecture",
        public_contract_impact="New application DTO contract.",
        validation_relevance="DTO validation tests cover required fields.",
        migration_concern="No migration needed.",
        breaking_risk="No breaking risk identified.",
    )
