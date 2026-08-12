"""Tests for the selected-skill commit-message CLI command."""

from dataclasses import dataclass, field
from io import StringIO
from typing import TextIO

from fabrica.adapters.inbound.cli import (
    CliCommand,
    CliCommandExecutionOptions,
    CliGlobalOptions,
    CliInvocation,
)
from fabrica.adapters.inbound.cli import (
    run_cli_command as _run_cli_command,
)
from fabrica.bootstrap.cli import create_cli_contributions
from fabrica.features.agent_runtime.application.dtos import (
    ModelCostEvidence,
    ModelPricingStatus,
    ModelTokenUsageEvidence,
    ModelUsageCollectionStatus,
    ModelUsageEvidence,
    ModelUsageEvidenceConfidence,
    ModelUsageEvidenceSource,
    ModelUsageObservation,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitMessageCommand,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.contracts import DeveloperWorkflowCliDependencies
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageWorkflowResult,
    DeveloperWorkflowObservation,
    DeveloperWorkflowStatus,
    GenerateCommitMessageCommand,
)

EXPECTED_CONFIGURATION_ERROR_EXIT_CODE = 2


def run_cli_command(
    invocation: CliCommand | CliInvocation,
    *,
    dependencies: DeveloperWorkflowCliDependencies | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    options = CliCommandExecutionOptions(
        contributions=create_cli_contributions(developer_workflow_dependencies=dependencies),
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )
    return _run_cli_command(invocation, options=options)


@dataclass
class FakeCommitMessageWorkflow:
    result: CommitMessageWorkflowResult
    calls: list[GenerateCommitMessageCommand] = field(default_factory=list)

    def run(self, command: GenerateCommitMessageCommand) -> CommitMessageWorkflowResult:
        self.calls.append(command)
        return self.result


def test_commit_message_command_uses_injected_workflow_and_writes_success_output() -> None:
    workflow = FakeCommitMessageWorkflow(
        result=CommitMessageWorkflowResult(
            status=DeveloperWorkflowStatus.SUCCESS,
            output_text="Commit message:\nfeat: add x",
        ),
    )
    stdout = StringIO()
    stderr = StringIO()
    command = CliCommitMessageCommand(skill_id="team-style")

    exit_code = run_cli_command(
        command,
        dependencies=DeveloperWorkflowCliDependencies(commit_message_workflow=workflow),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "Commit message:\nfeat: add x\n"
    assert stderr.getvalue() == ""
    assert workflow.calls == [GenerateCommitMessageCommand(skill_id="team-style")]


def test_commit_message_invocation_appends_requested_usage_and_price_evidence() -> None:
    workflow = FakeCommitMessageWorkflow(
        result=CommitMessageWorkflowResult(
            status=DeveloperWorkflowStatus.SUCCESS,
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
        dependencies=DeveloperWorkflowCliDependencies(commit_message_workflow=workflow),
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

    exit_code = run_cli_command(
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
