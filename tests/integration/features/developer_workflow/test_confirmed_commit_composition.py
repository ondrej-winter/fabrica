"""Offline integration tests for confirmed commit workflow composition."""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from fabrica.bootstrap import (
    CommitMessageWorkflowOptions,
    create_confirmed_commit_workflow,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    LocalAgentRunResult,
    LocalAgentRunStatus,
    ModelCostEvidence,
    ModelPricingStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
)
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageEvidenceBundle,
    CommitMessageRecommendation,
    DeveloperWorkflowObservation,
    DeveloperWorkflowStatus,
    GenerateCommitMessageResult,
    GitCommitResult,
    GitStagedChangesFailureCategory,
    GitStagedFile,
    GitStagedFileStatus,
    PreCommitRunCommand,
    PreCommitRunResult,
    PreCommitRunStatus,
    StagedFileCommitEvidence,
)
from fabrica.features.developer_workflow.application.ports import GitCommitError
from fabrica.features.developer_workflow.application.use_cases import ConfirmedCommitWorkflow


@dataclass
class FakeRuntime:
    results: list[LocalAgentRunResult]
    calls: list[LocalAgentRunCommand] = field(default_factory=list)

    def run(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.results.pop(0)

    async def run_async(self, command: LocalAgentRunCommand) -> LocalAgentRunResult:
        return self.run(command)


@dataclass
class FakeGenerator:
    result: GenerateCommitMessageResult

    async def generate_async(self, *, skill_id: str) -> GenerateCommitMessageResult:
        _ = skill_id
        return self.result


@dataclass
class FailingCommitter:
    error: GitCommitError

    def create(self, command: object) -> GitCommitResult:
        _ = command
        raise self.error


@dataclass
class FakeEvidenceRecorder:
    usage_evidence: tuple[ModelUsageEvidence, ...] = ()
    cost_evidence: tuple[ModelCostEvidence, ...] = ()
    reset_count: int = 0

    def reset(self) -> None:
        self.reset_count += 1


@dataclass
class PassingPreCommitRunner:
    commands: list[PreCommitRunCommand] = field(default_factory=list)

    def run_pre_commit(self, command: PreCommitRunCommand) -> PreCommitRunResult:
        self.commands.append(command)
        return PreCommitRunResult(status=PreCommitRunStatus.PASSED)


def test_confirmed_commit_workflow_creates_commit_from_parsed_recommendation_message(tmp_path: Path) -> None:
    commit_message = "feat: add confirmed commit flow\n\nPreserve exact body.\n\nRefs: #123"
    runtime = FakeRuntime(
        results=[
            LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text=_analysis_json()),
            LocalAgentRunResult(
                status=LocalAgentRunStatus.SUCCESS,
                output_text=_synthesis_text(commit_message=commit_message),
            ),
        ],
    )
    git_repository = _create_repository_with_staged_diff(tmp_path)
    _configure_git_identity(git_repository)
    _write_passing_pre_commit_config(git_repository)
    skill_root = _write_commit_message_skill(tmp_path)
    workflow = create_confirmed_commit_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(git_working_directory=git_repository, skill_roots=(skill_root,)),
    )

    result = workflow.run(skill_id="conventional-commits")

    assert result.succeeded
    assert result.commit_attempted is True
    assert result.recommendation == CommitMessageRecommendation(
        summary="Adds an example file.",
        rationale="The structured evidence shows one staged maintenance change.",
        commit_message=commit_message,
    )
    assert result.commit_result is not None
    assert result.commit_result.short_hash
    assert result.output_text is None
    assert _git_commit_count(git_repository) == 1
    assert _git_log_message(git_repository) == commit_message


def test_confirmed_commit_workflow_preserves_model_evidence(tmp_path: Path) -> None:
    analysis_usage = _usage_evidence(input_tokens=10, output_tokens=5)
    synthesis_usage = _usage_evidence(input_tokens=20, output_tokens=8)
    synthesis_cost = ModelCostEvidence(
        pricing_status=ModelPricingStatus.UNKNOWN,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.UNKNOWN,
    )
    runtime = FakeRuntime(
        results=[
            LocalAgentRunResult(
                status=LocalAgentRunStatus.SUCCESS,
                output_text=_analysis_json(),
                usage_evidence=(analysis_usage,),
            ),
            LocalAgentRunResult(
                status=LocalAgentRunStatus.SUCCESS,
                output_text=_synthesis_text(commit_message="chore: add example file"),
                usage_evidence=(synthesis_usage,),
                cost_evidence=(synthesis_cost,),
            ),
        ],
    )
    git_repository = _create_repository_with_staged_diff(tmp_path)
    _configure_git_identity(git_repository)
    _write_passing_pre_commit_config(git_repository)
    skill_root = _write_commit_message_skill(tmp_path)
    workflow = create_confirmed_commit_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(git_working_directory=git_repository, skill_roots=(skill_root,)),
    )

    result = workflow.run(skill_id="conventional-commits")

    assert result.succeeded
    assert result.usage_evidence == (analysis_usage, synthesis_usage)
    assert result.cost_evidence == (synthesis_cost,)


def test_confirmed_commit_workflow_stops_before_commit_when_staged_discovery_fails(tmp_path: Path) -> None:
    runtime = FakeRuntime(results=[])
    git_repository = tmp_path / "repo"
    git_repository.mkdir()
    _run_git(("git", "init"), cwd=git_repository)
    _write_passing_pre_commit_config(git_repository)
    workflow = create_confirmed_commit_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(git_working_directory=git_repository),
    )

    result = workflow.run()

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.commit_attempted is False
    assert result.commit_result is None
    assert result.observations[0].metadata["category"] == GitStagedChangesFailureCategory.NO_STAGED_CHANGES
    assert runtime.calls == []
    assert _git_commit_count(git_repository) == 0


def test_confirmed_commit_workflow_stops_before_runtime_when_pre_commit_fails(tmp_path: Path) -> None:
    runtime = FakeRuntime(results=[])
    git_repository = _create_repository_with_staged_diff(tmp_path)
    _configure_git_identity(git_repository)
    _write_failing_pre_commit_config(git_repository)
    skill_root = _write_commit_message_skill(tmp_path)
    workflow = create_confirmed_commit_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(git_working_directory=git_repository, skill_roots=(skill_root,)),
    )

    result = workflow.run(skill_id="conventional-commits")

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.recommendation is None
    assert result.commit_attempted is False
    assert result.commit_result is None
    assert result.observations[0].metadata["category"] == "pre_commit_failed"
    assert runtime.calls == []
    assert _git_commit_count(git_repository) == 0
    assert _git_staged_file_names(git_repository) == ("example.txt",)


def test_confirmed_commit_workflow_stops_before_runtime_when_pre_commit_modifies_files(tmp_path: Path) -> None:
    runtime = FakeRuntime(results=[])
    git_repository = _create_repository_with_staged_diff(tmp_path)
    _configure_git_identity(git_repository)
    _write_modifying_pre_commit_config(git_repository)
    skill_root = _write_commit_message_skill(tmp_path)
    workflow = create_confirmed_commit_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(git_working_directory=git_repository, skill_roots=(skill_root,)),
    )

    result = workflow.run(skill_id="conventional-commits")

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.recommendation is None
    assert result.commit_attempted is False
    assert result.commit_result is None
    assert result.observations[0].metadata["category"] == "pre_commit_modified_files"
    assert "review and stage changed files" in result.observations[0].message
    assert runtime.calls == []
    assert _git_commit_count(git_repository) == 0
    assert _git_staged_file_names(git_repository) == ("example.txt",)
    assert _git_unstaged_file_names(git_repository) == ("example.txt",)


def test_confirmed_commit_workflow_reports_git_failure_without_creating_commit(tmp_path: Path) -> None:
    runtime = FakeRuntime(
        results=[
            LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text=_analysis_json()),
            LocalAgentRunResult(
                status=LocalAgentRunStatus.SUCCESS,
                output_text=_synthesis_text(commit_message="feat: add confirmed commit flow"),
            ),
        ],
    )
    git_repository = _create_repository_with_staged_diff(tmp_path)
    _configure_git_identity(git_repository)
    _write_passing_pre_commit_config(git_repository)
    _install_failing_pre_commit_hook(git_repository)
    skill_root = _write_commit_message_skill(tmp_path)
    workflow = create_confirmed_commit_workflow(
        runtime=runtime,
        options=CommitMessageWorkflowOptions(git_working_directory=git_repository, skill_roots=(skill_root,)),
    )

    result = workflow.run(skill_id="conventional-commits")

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.commit_attempted is True
    assert result.commit_result is None
    assert result.recommendation is not None
    assert result.recommendation.commit_message == "feat: add confirmed commit flow"
    assert result.observations[0].metadata["category"] == "git_failed"
    assert result.observations[0].metadata["commit_attempted"] is True
    assert _git_commit_count(git_repository) == 0
    assert _git_staged_file_names(git_repository) == ("example.txt",)


def test_confirmed_commit_workflow_maps_commit_error_after_preserving_recommendation() -> None:
    recommendation = CommitMessageRecommendation(
        summary="Summary text.",
        rationale="Rationale text.",
        commit_message="feat: add confirmed commit flow",
    )
    usage = _usage_evidence(input_tokens=3, output_tokens=2)
    recorder = FakeEvidenceRecorder(usage_evidence=(usage,))
    workflow = ConfirmedCommitWorkflow(
        generator=FakeGenerator(result=_generate_result(recommendation)),
        committer=FailingCommitter(
            GitCommitError("git commit failed", metadata={"category": "git_failed", "returncode": 1})
        ),
        pre_commit_runner=PassingPreCommitRunner(),
        evidence_recorder=recorder,
    )

    result = workflow.run()

    assert result.status is DeveloperWorkflowStatus.CONFIGURATION_ERROR
    assert result.recommendation is recommendation
    assert result.output_text is None
    assert result.commit_attempted is True
    assert result.commit_result is None
    assert result.usage_evidence == (usage,)
    assert result.observations == (
        DeveloperWorkflowObservation(
            message="git commit failed",
            metadata={"category": "git_failed", "commit_attempted": True, "returncode": 1},
        ),
    )
    assert recorder.reset_count == 1


def _analysis_json() -> str:
    return json.dumps(
        {
            "summary": "Adds an example file.",
            "category": "maintenance",
            "public_contract_impact": "No public contract impact identified.",
            "validation_relevance": "No validation relevance identified.",
            "migration_concern": "No migration concern identified.",
            "breaking_risk": "No breaking risk identified.",
        }
    )


def _synthesis_text(
    *,
    commit_message: str,
    summary: str = "Adds an example file.",
    rationale: str = "The structured evidence shows one staged maintenance change.",
) -> str:
    return f"Summary:\n{summary}\n\nRationale:\n{rationale}\n\nCommit message:\n{commit_message}"


def _usage_evidence(*, input_tokens: int, output_tokens: int) -> ModelUsageEvidence:
    return ModelUsageEvidence(
        provider="codex",
        status=ModelUsageCollectionStatus.COLLECTED,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.EXTRACTED,
        model="gpt-5.3-codex-spark",
        tokens=ModelTokenUsageEvidence(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
    )


def _generate_result(recommendation: CommitMessageRecommendation) -> GenerateCommitMessageResult:
    evidence = StagedFileCommitEvidence(
        staged_file=GitStagedFile(path="example.txt", status=GitStagedFileStatus.ADDED),
        summary="Adds an example file.",
        category="maintenance",
        public_contract_impact="No public contract impact identified.",
        validation_relevance="No validation relevance identified.",
        migration_concern="No migration concern identified.",
        breaking_risk="No breaking risk identified.",
    )
    return GenerateCommitMessageResult(
        recommendation=recommendation,
        evidence_bundle=CommitMessageEvidenceBundle(evidence=(evidence,)),
    )


def _write_commit_message_skill(tmp_path: Path) -> Path:
    skill_root = tmp_path / "skills"
    skill_directory = skill_root / "conventional-commits"
    skill_directory.mkdir(parents=True)
    (skill_directory / "SKILL.md").write_text(
        "# Conventional Commits\nUse concise commit messages.\n", encoding="utf-8"
    )
    return skill_root


def _create_repository_with_staged_diff(tmp_path: Path) -> Path:
    git_repository = tmp_path / "repo"
    git_repository.mkdir()
    _run_git(("git", "init"), cwd=git_repository)
    (git_repository / "example.txt").write_text("example\n", encoding="utf-8")
    _run_git(("git", "add", "example.txt"), cwd=git_repository)
    return git_repository


def _configure_git_identity(git_repository: Path) -> None:
    _run_git(("git", "config", "user.name", "Fabrica Test"), cwd=git_repository)
    _run_git(("git", "config", "user.email", "fabrica-test@example.invalid"), cwd=git_repository)


def _write_passing_pre_commit_config(git_repository: Path) -> None:
    _write_local_pre_commit_config(git_repository, script="import sys\nsys.exit(0)\n")


def _write_failing_pre_commit_config(git_repository: Path) -> None:
    _write_local_pre_commit_config(
        git_repository,
        script=("import sys\nsys.stderr.write('failing local pre-commit hook\\n')\nsys.exit(1)\n"),
    )


def _write_modifying_pre_commit_config(git_repository: Path) -> None:
    _write_local_pre_commit_config(
        git_repository,
        script=(
            "from pathlib import Path\n"
            "import sys\n"
            "Path('example.txt').write_text('example\\nmodified by hook\\n', encoding='utf-8')\n"
            "sys.exit(1)\n"
        ),
    )


def _write_local_pre_commit_config(git_repository: Path, *, script: str) -> None:
    hooks_directory = git_repository / "hooks"
    hooks_directory.mkdir()
    hook_path = hooks_directory / "fabrica_test_hook.py"
    hook_path.write_text(script, encoding="utf-8")
    (git_repository / ".pre-commit-config.yaml").write_text(
        """
repos:
  - repo: local
    hooks:
      - id: fabrica-test-hook
        name: Fabrica test hook
        entry: python hooks/fabrica_test_hook.py
        language: system
        pass_filenames: false
        always_run: true
""".lstrip(),
        encoding="utf-8",
    )


def _install_failing_pre_commit_hook(git_repository: Path) -> None:
    hook_path = git_repository / ".git" / "hooks" / "pre-commit"
    hook_path.write_text("#!/bin/sh\necho failing test hook >&2\nexit 1\n", encoding="utf-8")
    hook_path.chmod(0o755)


def _git_commit_count(git_repository: Path) -> int:
    result = subprocess.run(
        ("git", "rev-list", "--count", "HEAD"),  # noqa: S607
        cwd=git_repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0
    return int(result.stdout.strip())


def _git_staged_file_names(git_repository: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ("git", "diff", "--cached", "--name-only"),  # noqa: S607
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line for line in result.stdout.splitlines() if line)


def _git_unstaged_file_names(git_repository: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ("git", "diff", "--name-only"),  # noqa: S607
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line for line in result.stdout.splitlines() if line)


def _git_log_message(git_repository: Path) -> str:
    return subprocess.run(
        ("git", "log", "-1", "--pretty=%B"),  # noqa: S607
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run_git(argv: tuple[str, ...], *, cwd: Path) -> None:
    subprocess.run(argv, cwd=cwd, check=True, capture_output=True)  # noqa: S603
