"""Tests for the selected-skill commit-message CLI command."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from typing import TextIO

from fabrica.adapters.inbound.cli import GlobalOptions
from fabrica.adapters.inbound.cli.model_evidence import write_model_evidence_report
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import (
    DeveloperWorkflowCliOptions,
    DeveloperWorkflowCliStreams,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.runner import run_commit_message_cli_command
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


@dataclass
class CommitMessageCommandHarness:
    workflow: FakeCommitMessageWorkflow
    global_options: GlobalOptions | None = None
    stdin: TextIO | None = None
    stdout: TextIO | None = None
    stderr: TextIO | None = None


def run_feature_cli_command(
    command: CliCommitMessageCommand,
    *,
    harness: CommitMessageCommandHarness,
) -> int:
    options = harness.global_options or GlobalOptions()
    return run_commit_message_cli_command(
        command,
        options=DeveloperWorkflowCliOptions(
            print_usage=options.print_usage,
            print_prices=options.print_prices,
        ),
        streams=DeveloperWorkflowCliStreams(
            stdin=harness.stdin or StringIO(),
            stdout=harness.stdout or StringIO(),
            stderr=harness.stderr or StringIO(),
        ),
        workflow=harness.workflow,
        evidence_writer=_write_evidence,
    )


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
class FakeCommitMessageWorkflow:
    result: CommitMessageWorkflowResult
    calls: list[GenerateCommitMessageCommand] = field(default_factory=list)

    async def run(self, command: GenerateCommitMessageCommand) -> CommitMessageWorkflowResult:
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
        harness=CommitMessageCommandHarness(workflow=workflow, stdout=stdout, stderr=stderr),
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
        harness=CommitMessageCommandHarness(workflow=workflow, stdout=stdout, stderr=StringIO()),
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
        CliCommitMessageCommand(),
        harness=CommitMessageCommandHarness(
            workflow=workflow,
            global_options=GlobalOptions(print_usage=True, print_prices=True),
            stdout=stdout,
            stderr=StringIO(),
        ),
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
        harness=CommitMessageCommandHarness(workflow=workflow, stdout=StringIO(), stderr=stderr),
    )

    assert exit_code == EXPECTED_CONFIGURATION_ERROR_EXIT_CODE
    assert (
        stderr.getvalue()
        == "status: configuration_error\nobservation: no staged git changes were found category=no_staged_changes\n"
    )
