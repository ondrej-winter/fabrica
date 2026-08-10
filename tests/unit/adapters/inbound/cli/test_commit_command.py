"""Tests for the interactive confirmed commit CLI command."""

from dataclasses import dataclass, field
from io import StringIO

from fabrica.adapters.inbound.cli import (
    CliCommandDependencies,
    CliCommitCommand,
    CliGlobalOptions,
    CliInvocation,
    run_cli_command,
)
from fabrica.bootstrap import ConfirmedCommitWorkflowResult
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    RuntimeObservation,
)
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    GenerateCommitMessageCommand,
    GitCommitResult,
)

EXPECTED_CONFIGURATION_ERROR_EXIT_CODE = 2
EXPECTED_INTERRUPTED_EXIT_CODE = 5


@dataclass
class FakeConfirmedCommitWorkflow:
    generation_result: ConfirmedCommitWorkflowResult
    commit_result: ConfirmedCommitWorkflowResult | None = None
    generate_calls: list[GenerateCommitMessageCommand] = field(default_factory=list)
    commit_calls: list[CommitMessageRecommendation] = field(default_factory=list)

    def generate(self, command: GenerateCommitMessageCommand) -> ConfirmedCommitWorkflowResult:
        self.generate_calls.append(command)
        return self.generation_result

    def commit(self, recommendation: CommitMessageRecommendation) -> ConfirmedCommitWorkflowResult:
        self.commit_calls.append(recommendation)
        if self.commit_result is None:
            return ConfirmedCommitWorkflowResult(
                status=LocalAgentRunStatus.SUCCESS,
                recommendation=recommendation,
                commit_result=GitCommitResult(short_hash="abc1234"),
                commit_attempted=True,
            )
        return self.commit_result


class InterruptingInput(StringIO):
    def readline(self, size: int = -1, /) -> str:
        _ = size
        raise KeyboardInterrupt


def test_commit_command_prints_recommendation_prompts_and_commits_on_yes() -> None:
    recommendation = _recommendation()
    workflow = FakeConfirmedCommitWorkflow(generation_result=_generation_success(recommendation))
    stdout = StringIO()
    stderr = StringIO()
    command = CliCommitCommand(skill_id="team-style", model="gpt-5.6-sol", reasoning_effort="medium")

    exit_code = run_cli_command(
        command,
        dependencies=CliCommandDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO(" yes \n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == (
        "Summary:\nAdds x.\n\n"
        "Rationale:\nThe staged evidence supports x.\n\n"
        "Commit message:\nfeat: add x\n"
        "Commit with this message? [y/N] "
        "Committed as abc1234.\n"
    )
    assert stderr.getvalue() == ""
    assert workflow.generate_calls == [GenerateCommitMessageCommand(skill_id="team-style")]
    assert workflow.commit_calls == [recommendation]


def test_commit_command_rejects_without_invoking_commit() -> None:
    recommendation = _recommendation()
    workflow = FakeConfirmedCommitWorkflow(generation_result=_generation_success(recommendation))
    stdout = StringIO()

    exit_code = run_cli_command(
        CliCommitCommand(),
        dependencies=CliCommandDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO("maybe\n"),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert stdout.getvalue().endswith("Commit with this message? [y/N] Commit cancelled; no commit created.\n")
    assert workflow.commit_calls == []


def test_commit_command_treats_eof_as_successful_noop() -> None:
    workflow = FakeConfirmedCommitWorkflow(generation_result=_generation_success(_recommendation()))

    exit_code = run_cli_command(
        CliCommitCommand(),
        dependencies=CliCommandDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO(""),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert workflow.commit_calls == []


def test_commit_command_interrupted_input_exits_nonzero_without_commit() -> None:
    workflow = FakeConfirmedCommitWorkflow(generation_result=_generation_success(_recommendation()))
    stderr = StringIO()

    exit_code = run_cli_command(
        CliCommitCommand(),
        dependencies=CliCommandDependencies(confirmed_commit_workflow=workflow),
        stdin=InterruptingInput(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == EXPECTED_INTERRUPTED_EXIT_CODE
    assert "status: safety_denied" in stderr.getvalue()
    assert "commit confirmation interrupted" in stderr.getvalue()
    assert workflow.commit_calls == []


def test_commit_command_generation_failure_skips_prompt_and_commit() -> None:
    workflow = FakeConfirmedCommitWorkflow(
        generation_result=ConfirmedCommitWorkflowResult(
            status=LocalAgentRunStatus.CONFIGURATION_ERROR,
            observations=(
                RuntimeObservation(message="no staged git changes", metadata={"category": "no_staged_changes"}),
            ),
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        CliCommitCommand(),
        dependencies=CliCommandDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO("yes\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_CONFIGURATION_ERROR_EXIT_CODE
    assert stdout.getvalue() == ""
    assert (
        stderr.getvalue()
        == "status: configuration_error\nobservation: no staged git changes category=no_staged_changes\n"
    )
    assert workflow.commit_calls == []


def test_commit_command_pre_commit_stop_skips_prompt_and_commit() -> None:
    workflow = FakeConfirmedCommitWorkflow(
        generation_result=ConfirmedCommitWorkflowResult(
            status=LocalAgentRunStatus.CONFIGURATION_ERROR,
            observations=(
                RuntimeObservation(
                    message="pre-commit failed; no commit was created",
                    metadata={"category": "pre_commit_failed"},
                ),
            ),
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        CliCommitCommand(),
        dependencies=CliCommandDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO("yes\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_CONFIGURATION_ERROR_EXIT_CODE
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "status: configuration_error\n"
        "observation: pre-commit failed; no commit was created category=pre_commit_failed\n"
    )
    assert workflow.commit_calls == []


def test_commit_command_appends_evidence_on_rejection() -> None:
    workflow = FakeConfirmedCommitWorkflow(
        generation_result=_generation_success(_recommendation(), usage_evidence=(_usage_evidence(),)),
    )
    stdout = StringIO()

    exit_code = run_cli_command(
        CliInvocation(
            command=CliCommitCommand(),
            global_options=CliGlobalOptions(print_usage=True),
        ),
        dependencies=CliCommandDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO("no\n"),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert "Usage evidence:\n" in stdout.getvalue()
    assert "provider=codex status=collected" in stdout.getvalue()
    assert workflow.commit_calls == []


def test_commit_command_reports_commit_failure_without_reprinting_recommendation() -> None:
    recommendation = _recommendation()
    workflow = FakeConfirmedCommitWorkflow(
        generation_result=_generation_success(recommendation, usage_evidence=(_usage_evidence(),)),
        commit_result=ConfirmedCommitWorkflowResult(
            status=LocalAgentRunStatus.CONFIGURATION_ERROR,
            recommendation=recommendation,
            observations=(
                RuntimeObservation(
                    message="git commit failed",
                    metadata={"category": "git_failed", "commit_attempted": True},
                ),
            ),
            usage_evidence=(_usage_evidence(),),
            commit_attempted=True,
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_cli_command(
        CliInvocation(command=CliCommitCommand(), global_options=CliGlobalOptions(print_usage=True)),
        dependencies=CliCommandDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO("y\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == EXPECTED_CONFIGURATION_ERROR_EXIT_CODE
    assert stdout.getvalue().count("Commit message:") == 1
    assert "Usage evidence:\n" in stdout.getvalue()
    assert stderr.getvalue() == (
        "status: configuration_error\nobservation: git commit failed category=git_failed commit_attempted=True\n"
    )


def _recommendation() -> CommitMessageRecommendation:
    return CommitMessageRecommendation(
        summary="Adds x.",
        rationale="The staged evidence supports x.",
        commit_message="feat: add x",
    )


def _generation_success(
    recommendation: CommitMessageRecommendation,
    *,
    usage_evidence: tuple[ModelUsageEvidence, ...] = (),
) -> ConfirmedCommitWorkflowResult:
    return ConfirmedCommitWorkflowResult(
        status=LocalAgentRunStatus.SUCCESS,
        recommendation=recommendation,
        output_text=(
            f"Summary:\n{recommendation.summary}\n\n"
            f"Rationale:\n{recommendation.rationale}\n\n"
            f"Commit message:\n{recommendation.commit_message}"
        ),
        usage_evidence=usage_evidence,
    )


def _usage_evidence() -> ModelUsageEvidence:
    return ModelUsageEvidence(
        provider="codex",
        status=ModelUsageCollectionStatus.COLLECTED,
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
        confidence=ModelUsageEvidenceConfidence.EXTRACTED,
        model="gpt-5.3-codex-spark",
        tokens=ModelTokenUsageEvidence(input_tokens=12, output_tokens=8, total_tokens=20),
    )
