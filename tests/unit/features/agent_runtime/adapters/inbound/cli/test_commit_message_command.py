"""Tests for the selected-skill commit-message CLI command."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from fabrica.features.agent_runtime.adapters.inbound.cli import (
    CliCommandDependencies,
    CliCommitMessageCommand,
    run_cli_command,
)
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunResult,
    LocalAgentRunStatus,
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
        verbose_diagnostics=True,
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
