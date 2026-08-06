"""Tests for the selected-skill commit-message CLI command."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from fabrica.adapters.inbound.cli import (
    CliCommandDependencies,
    CliCommitMessageCommand,
    CliGlobalOptions,
    CliInvocation,
    run_cli_command,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunResult,
    LocalAgentRunStatus,
    ModelCostEvidence,
    ModelPricingStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    ModelUsageObservation,
    RuntimeObservation,
)

EXPECTED_CONFIGURATION_ERROR_EXIT_CODE = 2


@dataclass
class FakeCommitMessageWorkflow:
    result: LocalAgentRunResult
    calls: list[CliCommitMessageCommand] = field(default_factory=list)

    def run(self, command: CliCommitMessageCommand) -> LocalAgentRunResult:
        self.calls.append(command)
        return self.result


def test_commit_message_command_uses_injected_workflow_and_writes_success_output() -> None:
    workflow = FakeCommitMessageWorkflow(
        result=LocalAgentRunResult(status=LocalAgentRunStatus.SUCCESS, output_text="Commit message:\nfeat: add x"),
    )
    stdout = StringIO()
    stderr = StringIO()
    command = CliCommitMessageCommand(
        skill_id="team-style",
        model="gpt-5.6-sol",
        reasoning_effort="medium",
        skill_roots=(Path("skills"),),
    )

    exit_code = run_cli_command(
        command,
        dependencies=CliCommandDependencies(commit_message_workflow=workflow),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "Commit message:\nfeat: add x\n"
    assert stderr.getvalue() == ""
    assert workflow.calls == [command]


def test_commit_message_invocation_appends_requested_usage_and_price_evidence() -> None:
    workflow = FakeCommitMessageWorkflow(
        result=LocalAgentRunResult(
            status=LocalAgentRunStatus.SUCCESS,
            output_text="Commit message:\nfeat: add x",
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

    exit_code = run_cli_command(
        CliInvocation(
            command=CliCommitMessageCommand(),
            global_options=CliGlobalOptions(print_usage=True, print_prices=True),
        ),
        dependencies=CliCommandDependencies(commit_message_workflow=workflow),
        stdout=stdout,
        stderr=StringIO(),
    )

    assert exit_code == 0
    assert stdout.getvalue() == (
        "Commit message:\nfeat: add x\n"
        "Usage evidence:\n"
        "- provider=codex status=collected source=response_payload confidence=extracted "
        "model=gpt-5.3-codex-spark input_tokens=12 output_tokens=8 total_tokens=20\n"
        "Pricing evidence:\n"
        "- status=unknown source=source_code_observation confidence=unknown observation='pricing is unknown'\n"
    )


def test_commit_message_command_reports_pre_model_configuration_failures() -> None:
    workflow = FakeCommitMessageWorkflow(
        result=LocalAgentRunResult(
            status=LocalAgentRunStatus.CONFIGURATION_ERROR,
            observations=(
                RuntimeObservation(
                    message="no staged git changes were found", metadata={"category": "no_staged_changes"}
                ),
            ),
        ),
    )
    stderr = StringIO()

    exit_code = run_cli_command(
        CliCommitMessageCommand(),
        dependencies=CliCommandDependencies(commit_message_workflow=workflow),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == EXPECTED_CONFIGURATION_ERROR_EXIT_CODE
    assert (
        stderr.getvalue()
        == "status: configuration_error\nobservation: no staged git changes were found category=no_staged_changes\n"
    )
