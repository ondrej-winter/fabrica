"""Tests for the interactive confirmed commit CLI command."""

from dataclasses import dataclass, field
from io import StringIO
from typing import TextIO

import pytest

from fabrica.adapters.inbound.cli import CliGlobalOptions, CliInvocation
from fabrica.adapters.inbound.cli.output import write_model_evidence_report
from fabrica.features.agent_runtime.application.dtos import (
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliOptions,
    DeveloperWorkflowCliStreams,
    DeveloperWorkflowCliWriters,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.output import (
    write_confirmed_commit_result,
    write_developer_workflow_result,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import run_developer_workflow_cli_command
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    CommitMessageWorkflowResult,
    ConfirmedCommitWorkflowResult,
    DeveloperWorkflowObservation,
    DeveloperWorkflowStatus,
    GenerateCommitMessageCommand,
    GitCommitResult,
)

EXPECTED_CONFIGURATION_ERROR_EXIT_CODE = 2
EXPECTED_INTERRUPTED_EXIT_CODE = 5


def run_feature_cli_command(
    invocation: CliCommitCommand | CliInvocation,
    *,
    dependencies: DeveloperWorkflowCliDependencies | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    command, global_options = _normalize_invocation(invocation)
    return run_developer_workflow_cli_command(
        command,
        options=DeveloperWorkflowCliOptions(
            print_usage=global_options.print_usage,
            print_prices=global_options.print_prices,
        ),
        dependencies=dependencies or DeveloperWorkflowCliDependencies(),
        streams=DeveloperWorkflowCliStreams(
            stdin=stdin or StringIO(),
            stdout=stdout or StringIO(),
            stderr=stderr or StringIO(),
        ),
        writers=DeveloperWorkflowCliWriters(
            evidence=_write_evidence,
            runtime_result=write_developer_workflow_result,
            confirmed_commit_result=write_confirmed_commit_result,
        ),
    )


def _normalize_invocation(invocation: CliCommitCommand | CliInvocation) -> tuple[CliCommitCommand, CliGlobalOptions]:
    if isinstance(invocation, CliInvocation):
        if not isinstance(invocation.command, CliCommitCommand):
            msg = "commit tests only support CliCommitCommand invocations"
            raise TypeError(msg)
        return invocation.command, invocation.global_options
    return invocation, CliGlobalOptions()


def _write_evidence(
    result: CommitMessageWorkflowResult | ConfirmedCommitWorkflowResult,
    *,
    include_usage: bool,
    include_prices: bool,
    stdout: TextIO,
) -> None:
    write_model_evidence_report(
        usage_evidence=result.usage_evidence,
        cost_evidence=result.cost_evidence,
        stdout=stdout,
        include_usage=include_usage,
        include_prices=include_prices,
    )


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
                status=DeveloperWorkflowStatus.SUCCESS,
                recommendation=recommendation,
                commit_result=GitCommitResult(short_hash="abc1234"),
                commit_attempted=True,
            )
        return self.commit_result


class InterruptingInput(StringIO):
    def readline(self, size: int = -1, /) -> str:
        _ = size
        raise KeyboardInterrupt


@pytest.mark.parametrize("confirmation", ["y\n", " yes \n"])
def test_commit_command_prints_recommendation_prompts_and_commits_on_approval(confirmation: str) -> None:
    recommendation = _recommendation()
    workflow = FakeConfirmedCommitWorkflow(generation_result=_generation_success(recommendation))
    stdout = StringIO()
    stderr = StringIO()
    command = CliCommitCommand(skill_id="team-style")

    exit_code = run_feature_cli_command(
        command,
        dependencies=DeveloperWorkflowCliDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO(confirmation),
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


def test_commit_command_rejects_no_without_invoking_commit() -> None:
    recommendation = _recommendation()
    workflow = FakeConfirmedCommitWorkflow(generation_result=_generation_success(recommendation))
    stdout = StringIO()

    exit_code = run_feature_cli_command(
        CliCommitCommand(),
        dependencies=DeveloperWorkflowCliDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO("n\n"),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert stdout.getvalue().endswith("Commit with this message? [y/N] Commit cancelled; no commit created.\n")
    assert workflow.commit_calls == []


def test_commit_command_treats_eof_as_successful_noop() -> None:
    workflow = FakeConfirmedCommitWorkflow(generation_result=_generation_success(_recommendation()))

    exit_code = run_feature_cli_command(
        CliCommitCommand(),
        dependencies=DeveloperWorkflowCliDependencies(confirmed_commit_workflow=workflow),
        stdin=StringIO(""),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert workflow.commit_calls == []


def test_commit_command_interrupted_input_exits_nonzero_without_commit() -> None:
    workflow = FakeConfirmedCommitWorkflow(generation_result=_generation_success(_recommendation()))
    stderr = StringIO()

    exit_code = run_feature_cli_command(
        CliCommitCommand(),
        dependencies=DeveloperWorkflowCliDependencies(confirmed_commit_workflow=workflow),
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
            status=DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            observations=(
                DeveloperWorkflowObservation(
                    message="no staged git changes",
                    metadata={"category": "no_staged_changes"},
                ),
            ),
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_feature_cli_command(
        CliCommitCommand(),
        dependencies=DeveloperWorkflowCliDependencies(confirmed_commit_workflow=workflow),
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
            status=DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            observations=(
                DeveloperWorkflowObservation(
                    message="pre-commit failed; no commit was created",
                    metadata={"category": "pre_commit_failed"},
                ),
            ),
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_feature_cli_command(
        CliCommitCommand(),
        dependencies=DeveloperWorkflowCliDependencies(confirmed_commit_workflow=workflow),
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

    exit_code = run_feature_cli_command(
        CliInvocation(
            command=CliCommitCommand(),
            global_options=CliGlobalOptions(print_usage=True),
        ),
        dependencies=DeveloperWorkflowCliDependencies(confirmed_commit_workflow=workflow),
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
            status=DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            recommendation=recommendation,
            observations=(
                DeveloperWorkflowObservation(
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

    exit_code = run_feature_cli_command(
        CliInvocation(command=CliCommitCommand(), global_options=CliGlobalOptions(print_usage=True)),
        dependencies=DeveloperWorkflowCliDependencies(confirmed_commit_workflow=workflow),
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
        status=DeveloperWorkflowStatus.SUCCESS,
        recommendation=recommendation,
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
