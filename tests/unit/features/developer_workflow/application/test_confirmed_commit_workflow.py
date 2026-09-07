"""Tests for confirmed commit pre-commit gate orchestration."""

import asyncio
from dataclasses import dataclass, field

import pytest

from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    CreateGitCommitCommand,
    DeveloperWorkflowStatus,
    GenerateCommitMessageResult,
    GitCommitResult,
    GitRepositorySnapshot,
    GitRepositorySnapshotFailureCategory,
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
    GitRepositorySnapshotLoadError,
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

    async def generate(self, *, skill_id: str) -> GenerateCommitMessageResult:
        """Record the selected skill and return a deterministic recommendation."""
        self.skill_ids.append(skill_id)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@dataclass
class FakeCommitter:
    """Fake git committer recording approved commit commands."""

    calls: list[CreateGitCommitCommand] = field(default_factory=list)

    def create(self, command: CreateGitCommitCommand) -> GitCommitResult:
        """Record one commit attempt and return a deterministic commit result."""
        self.calls.append(command)
        return GitCommitResult(short_hash="abc1234")


@dataclass
class FakeSnapshotReader:
    index_tree_ids: list[str | Exception] = field(default_factory=lambda: ["a" * 40] * 10)
    calls: int = 0

    def load_index_tree_id(self) -> str:
        value = self.index_tree_ids[self.calls]
        self.calls += 1
        if isinstance(value, Exception):
            raise value
        return value

    def load_snapshot(self) -> GitRepositorySnapshot:
        index_tree_id = "a" * 40
        if self.calls < len(self.index_tree_ids):
            candidate = self.index_tree_ids[self.calls]
            if isinstance(candidate, str):
                index_tree_id = candidate
        return GitRepositorySnapshot(
            index_tree_id=index_tree_id,
            tracked_worktree_id="0" * 64,
        )


def test_confirmed_commit_runs_pre_commit_before_recommendation_generation() -> None:
    pre_commit = FakePreCommitRunner(PreCommitRunResult(status=PreCommitRunStatus.PASSED))
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()
    snapshots = FakeSnapshotReader()

    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=committer,
            pre_commit_runner=pre_commit,
            snapshot_reader=snapshots,
        ).generate(skill_id="team-style")
    )

    assert result.succeeded
    assert result.recommendation == _recommendation()
    assert pre_commit.commands == [PreCommitRunCommand()]
    assert pre_commit.commands[0].all_files is False
    assert generator.skill_ids == ["team-style"]
    assert committer.calls == []


def test_confirmed_commit_denies_recommendation_when_index_changes_during_generation() -> None:
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()
    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=committer,
            pre_commit_runner=FakePreCommitRunner(),
            snapshot_reader=FakeSnapshotReader(["a" * 40, "b" * 40]),
        ).generate()
    )

    assert result.status is DeveloperWorkflowStatus.SAFETY_DENIED
    assert result.recommendation is None
    assert result.observations[0].metadata == {"category": "commit_recommendation_stale"}
    assert committer.calls == []


def test_confirmed_commit_denies_commit_when_index_changes_after_approval() -> None:
    recommendation = _recommendation()
    committer = FakeCommitter()
    workflow = ConfirmedCommitWorkflow(
        generator=FakeGenerator(_generate_result(recommendation)),
        committer=committer,
        pre_commit_runner=FakePreCommitRunner(),
        snapshot_reader=FakeSnapshotReader(["a" * 40, "a" * 40, "b" * 40]),
    )

    generation_result = asyncio.run(workflow.generate())
    result = workflow.commit(recommendation, analyzed_index_tree_id=generation_result.analyzed_index_tree_id or "")

    assert result.status is DeveloperWorkflowStatus.SAFETY_DENIED
    assert result.recommendation is recommendation
    assert result.commit_attempted is False
    assert committer.calls == []


def test_confirmed_commit_allows_worktree_only_change_when_index_is_unchanged() -> None:
    recommendation = _recommendation()
    committer = FakeCommitter()
    workflow = ConfirmedCommitWorkflow(
        generator=FakeGenerator(_generate_result(recommendation)),
        committer=committer,
        pre_commit_runner=FakePreCommitRunner(),
        snapshot_reader=FakeSnapshotReader(),
    )

    generation_result = asyncio.run(workflow.generate())
    result = workflow.commit(recommendation, analyzed_index_tree_id=generation_result.analyzed_index_tree_id or "")

    assert result.succeeded
    assert committer.calls[0].message == recommendation.commit_message


def test_confirmed_commit_snapshot_error_fails_closed_before_generation() -> None:
    error = GitRepositorySnapshotLoadError(
        "repository snapshot timed out",
        category=GitRepositorySnapshotFailureCategory.TIMED_OUT,
    )
    generator = FakeGenerator(_generate_result(_recommendation()))
    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=FakeCommitter(),
            pre_commit_runner=FakePreCommitRunner(),
            snapshot_reader=FakeSnapshotReader([error]),
        ).generate()
    )

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.observations[0].metadata["category"] is GitRepositorySnapshotFailureCategory.TIMED_OUT
    assert generator.skill_ids == []


def test_confirmed_commit_snapshot_error_after_generation_retains_no_recommendation() -> None:
    error = GitRepositorySnapshotLoadError(
        "repository snapshot timed out",
        category=GitRepositorySnapshotFailureCategory.TIMED_OUT,
    )
    generator = FakeGenerator(_generate_result(_recommendation()))
    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=FakeCommitter(),
            pre_commit_runner=FakePreCommitRunner(),
            snapshot_reader=FakeSnapshotReader(["a" * 40, error]),
        ).generate()
    )

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.recommendation is None
    assert result.observations[0].metadata["category"] is GitRepositorySnapshotFailureCategory.TIMED_OUT
    assert generator.skill_ids == ["conventional-commits"]


def test_confirmed_commit_snapshot_error_before_commit_retains_recommendation() -> None:
    error = GitRepositorySnapshotLoadError(
        "repository snapshot timed out",
        category=GitRepositorySnapshotFailureCategory.TIMED_OUT,
    )
    recommendation = _recommendation()
    committer = FakeCommitter()
    result = ConfirmedCommitWorkflow(
        generator=FakeGenerator(_generate_result(recommendation)),
        committer=committer,
        pre_commit_runner=FakePreCommitRunner(),
        snapshot_reader=FakeSnapshotReader([error]),
    ).commit(recommendation, analyzed_index_tree_id="a" * 40)

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.recommendation == recommendation
    assert result.observations[0].metadata["category"] is GitRepositorySnapshotFailureCategory.TIMED_OUT
    assert committer.calls == []


def test_confirmed_commit_continues_when_pre_commit_is_not_configured() -> None:
    pre_commit = FakePreCommitRunner(PreCommitRunResult(status=PreCommitRunStatus.SKIPPED))
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()

    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=committer,
            pre_commit_runner=pre_commit,
            snapshot_reader=FakeSnapshotReader(),
        ).generate(skill_id="team-style")
    )

    assert result.succeeded
    assert result.recommendation == _recommendation()
    assert pre_commit.commands == [PreCommitRunCommand()]
    assert generator.skill_ids == ["team-style"]
    assert committer.calls == []


def test_confirmed_commit_pre_commit_failure_skips_generation_and_commit() -> None:
    pre_commit = FakePreCommitRunner(PreCommitRunResult(status=PreCommitRunStatus.FAILED, stderr="hook failed\n"))
    generator = FakeGenerator(_generate_result(_recommendation()))
    committer = FakeCommitter()

    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=committer,
            pre_commit_runner=pre_commit,
            snapshot_reader=FakeSnapshotReader(),
        ).generate()
    )

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

    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=committer,
            pre_commit_runner=pre_commit,
            snapshot_reader=FakeSnapshotReader(),
        ).generate()
    )

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

    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=committer,
            pre_commit_runner=pre_commit,
            snapshot_reader=FakeSnapshotReader(),
        ).generate()
    )

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

    result = asyncio.run(
        ConfirmedCommitWorkflow(
            generator=generator,
            committer=committer,
            pre_commit_runner=pre_commit,
            snapshot_reader=FakeSnapshotReader(),
        ).generate(skill_id="team-style")
    )

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
