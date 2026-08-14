"""Tests for the selected-skill commit-message CLI command."""

from dataclasses import dataclass, field
from io import StringIO
from typing import TextIO

import pytest

from fabrica.adapters.inbound.cli import CliGlobalOptions, CliInvocation
from fabrica.adapters.inbound.cli.output import write_model_evidence_report
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliDependencies,
    DeveloperWorkflowCliOptions,
    DeveloperWorkflowCliStreams,
    DeveloperWorkflowCliWriters,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.output import write_developer_workflow_result
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import run_developer_workflow_cli_command
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    CommitMessageWorkflowResult,
    ConfirmedCommitWorkflowResult,
    DeveloperWorkflowObservation,
    DeveloperWorkflowStatus,
    GenerateCommitMessageCommand,
)
from fabrica.shared_kernel.model_usage import (
    ModelCostEvidence,
    ModelPricingStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    ModelUsageObservation,
)

EXPECTED_CONFIGURATION_ERROR_EXIT_CODE = 2


def run_feature_cli_command(
    invocation: CliCommitMessageCommand | CliInvocation,
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
            confirmed_commit_result=_unexpected_confirmed_commit_result_writer,
        ),
    )


def _normalize_invocation(
    invocation: CliCommitMessageCommand | CliInvocation,
) -> tuple[CliCommitMessageCommand, CliGlobalOptions]:
    if isinstance(invocation, CliInvocation):
        if not isinstance(invocation.command, CliCommitMessageCommand):
            msg = "commit-message tests only support CliCommitMessageCommand invocations"
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


def _unexpected_confirmed_commit_result_writer(*args: object, **kwargs: object) -> int:
    _ = args, kwargs
    msg = "commit-message tests must not execute confirmed-commit writer"
    raise AssertionError(msg)


@dataclass
class FakeCommitMessageWorkflow:
    result: CommitMessageWorkflowResult
    calls: list[GenerateCommitMessageCommand] = field(default_factory=list)

    def run(self, command: GenerateCommitMessageCommand) -> CommitMessageWorkflowResult:
        self.calls.append(command)
        return self.result


def test_commit_message_command_uses_injected_workflow_and_writes_success_output() -> None:
    recommendation = CommitMessageRecommendation(
        summary="Adds x.",
        rationale="The staged evidence supports x.",
        commit_message="feat: add x",
    )
    workflow = FakeCommitMessageWorkflow(
        result=CommitMessageWorkflowResult(
            status=DeveloperWorkflowStatus.SUCCESS,
            recommendation=recommendation,
        ),
    )
    stdout = StringIO()
    stderr = StringIO()
    command = CliCommitMessageCommand(skill_id="team-style")

    exit_code = run_feature_cli_command(
        command,
        dependencies=DeveloperWorkflowCliDependencies(commit_message_workflow=workflow),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert (
        stdout.getvalue()
        == "Summary:\nAdds x.\n\nRationale:\nThe staged evidence supports x.\n\nCommit message:\nfeat: add x\n"
    )
    assert stderr.getvalue() == ""
    assert workflow.calls == [GenerateCommitMessageCommand(skill_id="team-style")]


def test_commit_message_command_writes_success_output_without_cli_line_truncation() -> None:
    long_summary = "x" * 4_010
    recommendation = CommitMessageRecommendation(
        summary=long_summary,
        rationale="The staged evidence supports x.",
        commit_message="feat: add x",
    )
    workflow = FakeCommitMessageWorkflow(
        result=CommitMessageWorkflowResult(
            status=DeveloperWorkflowStatus.SUCCESS,
            recommendation=recommendation,
        ),
    )
    stdout = StringIO()

    exit_code = run_feature_cli_command(
        CliCommitMessageCommand(),
        dependencies=DeveloperWorkflowCliDependencies(commit_message_workflow=workflow),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert long_summary in stdout.getvalue()
    assert "...<truncated>" not in stdout.getvalue()


def test_commit_message_invocation_appends_requested_usage_and_price_evidence() -> None:
    recommendation = CommitMessageRecommendation(
        summary="Adds x.",
        rationale="The staged evidence supports x.",
        commit_message="feat: add x",
    )
    workflow = FakeCommitMessageWorkflow(
        result=CommitMessageWorkflowResult(
            status=DeveloperWorkflowStatus.SUCCESS,
            recommendation=recommendation,
            usage_evidence=(
                ModelUsageEvidence(
                    provider="codex",
                    status=ModelUsageCollectionStatus.COLLECTED,
                    source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
                    confidence=ModelUsageEvidenceConfidence.EXTRACTED,
                    model="gpt-5.3-codex-spark",
                    tokens=ModelTokenUsageEvidence(input_tokens=12, output_tokens=8, total_tokens=20),
                ),
            ),
            cost_evidence=(
                ModelCostEvidence(
                    pricing_status=ModelPricingStatus.UNKNOWN,
                    source=ModelUsageEvidenceSource.SOURCE_CODE_OBSERVATION,
                    confidence=ModelUsageEvidenceConfidence.UNKNOWN,
                    observations=(ModelUsageObservation(message="pricing is unknown"),),
                ),
            ),
        ),
    )
    stdout = StringIO()

    exit_code = run_feature_cli_command(
        CliInvocation(
            command=CliCommitMessageCommand(),
            global_options=CliGlobalOptions(print_usage=True, print_prices=True),
        ),
        dependencies=DeveloperWorkflowCliDependencies(commit_message_workflow=workflow),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert stdout.getvalue() == (
        "Summary:\nAdds x.\n\n"
        "Rationale:\nThe staged evidence supports x.\n\n"
        "Commit message:\nfeat: add x\n"
        "Usage evidence:\n"
        "- provider=codex status=collected source=response_payload confidence=extracted "
        "model=gpt-5.3-codex-spark input_tokens=12 output_tokens=8 total_tokens=20\n"
        "Pricing evidence:\n"
        "- status=unknown source=source_code_observation confidence=unknown observation='pricing is unknown'\n"
    )


def test_commit_message_command_reports_pre_model_configuration_failures() -> None:
    workflow = FakeCommitMessageWorkflow(
        result=CommitMessageWorkflowResult(
            status=DeveloperWorkflowStatus.CONFIGURATION_ERROR,
            observations=(
                DeveloperWorkflowObservation(
                    message="no staged git changes were found", metadata={"category": "no_staged_changes"}
                ),
            ),
        ),
    )
    stderr = StringIO()

    exit_code = run_feature_cli_command(
        CliCommitMessageCommand(),
        dependencies=DeveloperWorkflowCliDependencies(commit_message_workflow=workflow),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == EXPECTED_CONFIGURATION_ERROR_EXIT_CODE
    assert (
        stderr.getvalue()
        == "status: configuration_error\nobservation: no staged git changes were found category=no_staged_changes\n"
    )


def test_commit_message_command_reports_missing_injected_workflow() -> None:
    with pytest.raises(RuntimeError, match="commit_message_workflow"):
        run_feature_cli_command(CliCommitMessageCommand())
