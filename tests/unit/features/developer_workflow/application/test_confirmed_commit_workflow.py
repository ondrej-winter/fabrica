"""Tests for confirmed commit pre-commit gate orchestration."""

from dataclasses import dataclass, field

from fabrica.bootstrap import ConfirmedCommitWorkflow
from fabrica.features.agent_runtime.application.dtos import LocalAgentRunStatus
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    GenerateCommitMessageResult,
    GitCommitResult,
    GitStagedFile,
    GitStagedFileStatus,
    PreCommitFailureCategory,
    PreCommitRunCommand,
    PreCommitRunResult,
    PreCommitRunStatus,
    StagedFileCommitEvidence,
)
from fabrica.features.developer_workflow.application.ports import PreCommitRunError


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

    result: GenerateCommitMessageResult
    skill_ids: list[str] = field(default_factory=list)

    async def generate_async(self, *, skill_id: str) -> GenerateCommitMessageResult:
        """Record the selected skill and return a deterministic recommendation."""
        self.skill_ids.append(skill_id)
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


def test_confirmed_commit_pre_commit_failure_skips_generation_and_commit() -> None:
    pre_commit = FakePreCommitRunner(PreCommitRunResult(status=PreCommitRunStatus.FAILED, stderr="hook failed\n"))
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()

    result = ConfirmedCommitWorkflow(
        generator=generator,
        committer=committer,
        pre_commit_runner=pre_commit,
    ).generate()

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
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

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
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

    assert result.status is LocalAgentRunStatus.CONFIGURATION_ERROR
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
