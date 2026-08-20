"""Tests for confirmed commit pre-commit gate orchestration."""

from dataclasses import dataclass, field

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    DeveloperWorkflowStatus,
    GenerateCommitMessageResult,
    GitCommitResult,
    GitStagedChangesFailureCategory,
    GitStagedFile,
    GitStagedFileStatus,
    PreCommitFailureCategory,
    PreCommitRunCommand,
    PreCommitRunResult,
    PreCommitRunStatus,
    StagedFileCommitEvidence,
)
from fabrica.features.developer_workflow.application.ports import (
    CommitMessageAnalysisError,
    CommitMessageSkillContextLoadError,
    CommitMessageSynthesisError,
    GitStagedChangesLoadError,
    PreCommitRunError,
)
from fabrica.features.developer_workflow.application.use_cases import (
    ConfirmedCommitWorkflow,
    GenerateCommitMessageError,
)


@dataclass
class FakePreCommitRunner:
    """Fake pre-commit runner recording commands without invoking hooks."""

    result: PreCommitRunResult | None = None
    error: PreCommitRunError | None = None
    commands: list[PreCommitRunCommand] = field(default_factory=list)

    def run_pre_commit(self, command: PreCommitRunCommand) -> PreCommitRunResult:
        """Record one pre-commit command and return the configured outcome."""
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.result or PreCommitRunResult(status=PreCommitRunStatus.PASSED)


@dataclass
class FakeGenerator:
    """Fake recommendation generator recording selected skill IDs."""

    result: GenerateCommitMessageResult | Exception
    skill_ids: list[str] = field(default_factory=list)

    async def generate_async(self, *, skill_id: str) -> GenerateCommitMessageResult:
        """Record the selected skill and return a deterministic recommendation."""
        self.skill_ids.append(skill_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass
class FakeCommitter:
    """Fake git committer recording approved commit commands."""

    calls: list[object] = field(default_factory=list)

    def create(self, command: object) -> GitCommitResult:
        """Record one commit attempt and return a deterministic commit result."""
        self.calls.append(command)
        return GitCommitResult(short_hash="abc1234")


def test_confirmed_commit_runs_pre_commit_before_recommendation_generation() -> None:
    pre_commit = FakePreCommitRunner(PreCommitRunResult(status=PreCommitRunStatus.PASSED))
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()

    result = ConfirmedCommitWorkflow(
        generator=generator,
        committer=committer,
        pre_commit_runner=pre_commit,
    ).generate(skill_id="team-style")

    assert result.succeeded
    assert result.recommendation == _recommendation()
    assert pre_commit.commands == [PreCommitRunCommand()]
    assert pre_commit.commands[0].all_files is False
    assert generator.skill_ids == ["team-style"]
    assert committer.calls == []


def test_confirmed_commit_continues_when_pre_commit_is_not_configured() -> None:
    pre_commit = FakePreCommitRunner(PreCommitRunResult(status=PreCommitRunStatus.SKIPPED))
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()

    result = ConfirmedCommitWorkflow(
        generator=generator,
        committer=committer,
        pre_commit_runner=pre_commit,
    ).generate(skill_id="team-style")

    assert result.succeeded
    assert result.recommendation == _recommendation()
    assert pre_commit.commands == [PreCommitRunCommand()]
    assert generator.skill_ids == ["team-style"]
    assert committer.calls == []


def test_confirmed_commit_pre_commit_failure_skips_generation_and_commit() -> None:
    pre_commit = FakePreCommitRunner(PreCommitRunResult(status=PreCommitRunStatus.FAILED, stderr="hook failed\n"))
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()

    result = ConfirmedCommitWorkflow(
        generator=generator,
        committer=committer,
        pre_commit_runner=pre_commit,
    ).generate()

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.recommendation is None
    assert result.commit_result is None
    assert result.commit_attempted is False
    assert result.usage_evidence == ()
    assert result.cost_evidence == ()
    assert result.observations[0].metadata["category"] == "pre_commit_failed"
    assert pre_commit.commands == [PreCommitRunCommand()]
    assert generator.skill_ids == []
    assert committer.calls == []


def test_confirmed_commit_modified_files_skips_generation_and_reports_review_required() -> None:
    pre_commit = FakePreCommitRunner(
        PreCommitRunResult(status=PreCommitRunStatus.MODIFIED_FILES, stdout="files were modified by this hook\n"),
    )
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()

    result = ConfirmedCommitWorkflow(
        generator=generator,
        committer=committer,
        pre_commit_runner=pre_commit,
    ).generate()

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.recommendation is None
    assert result.commit_result is None
    assert result.commit_attempted is False
    assert result.observations[0].metadata["category"] == "pre_commit_modified_files"
    assert "review and stage" in result.observations[0].message
    assert pre_commit.commands == [PreCommitRunCommand()]
    assert generator.skill_ids == []
    assert committer.calls == []


def test_confirmed_commit_pre_commit_error_skips_generation_and_commit() -> None:
    pre_commit = FakePreCommitRunner(
        error=PreCommitRunError(
            "pre-commit timed out",
            category=PreCommitFailureCategory.TIMED_OUT,
            metadata={"timeout_seconds": 1.0},
        ),
    )
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()

    result = ConfirmedCommitWorkflow(
        generator=generator,
        committer=committer,
        pre_commit_runner=pre_commit,
    ).generate()

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.recommendation is None
    assert result.commit_result is None
    assert result.commit_attempted is False
    assert result.observations[0].metadata == {
        "category": PreCommitFailureCategory.TIMED_OUT,
        "timeout_seconds": 1.0,
    }
    assert pre_commit.commands == [PreCommitRunCommand()]
    assert generator.skill_ids == []
    assert committer.calls == []


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_category"),
    [
        (
            GitStagedChangesLoadError("git failed", category=GitStagedChangesFailureCategory.GIT_FAILED),
            DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            GitStagedChangesFailureCategory.GIT_FAILED,
        ),
        (
            CommitMessageSkillContextLoadError("skill missing", category="skill_not_found"),
            DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            "skill_not_found",
        ),
        (
            GenerateCommitMessageError("bad input", metadata={"evidence_count": 0}),
            DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            "invalid_commit_message_input",
        ),
        (
            CommitMessageAnalysisError("analysis failed", metadata={"phase": "analysis"}),
            DeveloperWorkflowStatus.MODEL_ERROR,
            "commit_message_model_failure",
        ),
        (
            CommitMessageSynthesisError("synthesis failed", metadata={"phase": "synthesis"}),
            DeveloperWorkflowStatus.MODEL_ERROR,
            "commit_message_model_failure",
        ),
    ],
)
def test_confirmed_commit_generation_errors_skip_commit(
    error: Exception,
    expected_status: DeveloperWorkflowStatus,
    expected_category: object,
) -> None:
    pre_commit = FakePreCommitRunner(PreCommitRunResult(status=PreCommitRunStatus.PASSED))
    generator = FakeGenerator(error)
    committer = FakeCommitter()

    result = ConfirmedCommitWorkflow(
        generator=generator,
        committer=committer,
        pre_commit_runner=pre_commit,
    ).generate(skill_id="team-style")

    assert result.status is expected_status
    assert result.recommendation is None
    assert result.commit_result is None
    assert result.commit_attempted is False
    assert result.observations[0].message == str(error)
    assert result.observations[0].metadata["category"] == expected_category
    assert generator.skill_ids == ["team-style"]
    assert committer.calls == []


def _recommendation() -> CommitMessageRecommendation:
    return CommitMessageRecommendation(
        summary="Adds confirmed commit pre-commit gate.",
        rationale="The staged evidence supports gating before generation.",
        commit_message="feat: gate confirmed commits",
    )


def _generate_result(recommendation: CommitMessageRecommendation) -> GenerateCommitMessageResult:
    evidence = StagedFileCommitEvidence(
        staged_file=GitStagedFile(path="src/fabrica/example.py", status=GitStagedFileStatus.MODIFIED),
        summary="Adds confirmed commit pre-commit gate.",
        category="behavior",
        public_contract_impact="No public contract impact identified.",
        validation_relevance="Application tests cover the gate.",
        migration_concern="No migration concern identified.",
        breaking_risk="No breaking risk identified.",
    )
    return GenerateCommitMessageResult(
        recommendation=recommendation,
        evidence_bundle=CommitMessageEvidenceBundle(evidence=(evidence,)),
    )
