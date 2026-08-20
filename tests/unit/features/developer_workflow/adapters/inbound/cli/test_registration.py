"""Tests for developer-workflow CLI command registration and decoding."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError, dataclass, field
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from fabrica.adapters.inbound.cli import CommandContext, CommandRegistrar, CommandRegistry, GlobalOptions, run_cli
from fabrica.bootstrap.cli import CliDependencyOverrides
from fabrica.bootstrap.cli import run_cli as run_bootstrap_cli
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
    CliDeveloperWorkflowCompositionOptions,
)
from fabrica.features.developer_workflow.adapters.inbound.cli.registration import (
    register_developer_workflow_cli_commands,
)
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    CommitMessageWorkflowResult,
    ConfirmedCommitWorkflowResult,
    DeveloperWorkflowStatus,
    GenerateCommitMessageCommand,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

ARGPARSE_USAGE_ERROR = 2


@dataclass(frozen=True, slots=True)
class ParsedInvocation:
    command: object
    global_options: GlobalOptions
    composition_options: CliDeveloperWorkflowCompositionOptions


@dataclass(slots=True)
class RecordingHandlers:
    invocation: ParsedInvocation | None = None

    def record_command(
        self,
        command: CliCommitMessageCommand | CliCommitCommand,
        composition_options: CliDeveloperWorkflowCompositionOptions,
        context: CommandContext,
    ) -> int:
        self.invocation = ParsedInvocation(
            command=command,
            global_options=context.global_options,
            composition_options=composition_options,
        )
        return 0


@dataclass(slots=True)
class RecordingCommitMessageWorkflow:
    calls: list[GenerateCommitMessageCommand] = field(default_factory=list)

    async def run(self, command: GenerateCommitMessageCommand) -> CommitMessageWorkflowResult:
        self.calls.append(command)
        return CommitMessageWorkflowResult(status=DeveloperWorkflowStatus.SUCCESS)


@dataclass(slots=True)
class RecordingConfirmedCommitWorkflow:
    generate_calls: list[GenerateCommitMessageCommand] = field(default_factory=list)
    commit_calls: list[CommitMessageRecommendation] = field(default_factory=list)

    async def generate(self, command: GenerateCommitMessageCommand) -> ConfirmedCommitWorkflowResult:
        self.generate_calls.append(command)
        return ConfirmedCommitWorkflowResult(status=DeveloperWorkflowStatus.SUCCESS)

    def commit(self, recommendation: CommitMessageRecommendation) -> ConfirmedCommitWorkflowResult:
        self.commit_calls.append(recommendation)
        return ConfirmedCommitWorkflowResult(status=DeveloperWorkflowStatus.SUCCESS)


def parse_args(args: Sequence[str]) -> ParsedInvocation:
    handlers = RecordingHandlers()
    exit_code = run_cli(
        args,
        command_registrars=(_recording_command_registrar(handlers),),
        stdin=StringIO(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if exit_code != 0:
        raise SystemExit(exit_code)
    assert handlers.invocation is not None
    return handlers.invocation


def _recording_command_registrar(handlers: RecordingHandlers) -> CommandRegistrar:
    def register(commands: CommandRegistry) -> None:
        register_developer_workflow_cli_commands(
            commands,
            commit_message_command=handlers.record_command,
            commit_command=handlers.record_command,
        )

    return register


def test_parse_commit_message_command_defaults_to_conventional_commits_skill() -> None:
    invocation = parse_args(("commit-message",))

    assert invocation == ParsedInvocation(
        command=CliCommitMessageCommand(skill_id="conventional-commits"),
        global_options=GlobalOptions(),
        composition_options=CliDeveloperWorkflowCompositionOptions(),
    )


def test_parse_commit_message_command_supports_skill_root_and_diagnostics_overrides() -> None:
    invocation = parse_args(
        (
            "--verbose-diagnostics",
            "commit-message",
            "--skill",
            "team-style",
            "--model",
            "gpt-5.6-sol",
            "--reasoning-effort",
            "medium",
            "--skill-root",
            "./skills",
        ),
    )
    assert invocation == ParsedInvocation(
        command=CliCommitMessageCommand(skill_id="team-style"),
        global_options=GlobalOptions(verbose_diagnostics=True),
        composition_options=CliDeveloperWorkflowCompositionOptions(
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            skill_roots=(Path("./skills"),),
        ),
    )


def test_parse_commit_message_command_supports_usage_and_price_reporting() -> None:
    invocation = parse_args(("--print-usage", "--print-prices", "commit-message"))

    assert invocation == ParsedInvocation(
        command=CliCommitMessageCommand(skill_id="conventional-commits"),
        global_options=GlobalOptions(print_usage=True, print_prices=True),
        composition_options=CliDeveloperWorkflowCompositionOptions(),
    )


def test_parse_commit_message_command_rejects_unknown_reasoning_effort() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(("commit-message", "--reasoning-effort", "very-high"))

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (("commit-message", "--skill", ""), "skill_id must not be empty"),
        (("commit", "--skill", "   "), "skill_id must not be empty"),
        (("commit-message", "--skill", "../unsafe"), "skill_id must not contain traversal segments"),
        (("commit", "--skill", "../unsafe"), "skill_id must not contain traversal segments"),
        (("commit-message", "--skill", "/unsafe"), "skill_id must be a relative identifier"),
        (("commit", "--skill", "team//unsafe"), "skill_id must be a relative identifier"),
    ],
)
def test_parse_developer_workflow_commands_reject_invalid_boundary_values(
    args: tuple[str, ...],
    expected_message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(args)

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR
    assert expected_message in capsys.readouterr().err


def test_commit_message_rejects_unsafe_skill_before_invoking_workflow() -> None:
    workflow = RecordingCommitMessageWorkflow()
    stderr = StringIO()

    exit_code = run_bootstrap_cli(
        ("commit-message", "--skill", "../unsafe"),
        overrides=CliDependencyOverrides(commit_message_workflow=workflow),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert "skill_id must not contain traversal segments" in stderr.getvalue()
    assert workflow.calls == []


def test_commit_rejects_unsafe_skill_before_invoking_workflow() -> None:
    workflow = RecordingConfirmedCommitWorkflow()
    stderr = StringIO()

    exit_code = run_bootstrap_cli(
        ("commit", "--skill", "../unsafe"),
        overrides=CliDependencyOverrides(confirmed_commit_workflow=workflow),
        stdin=StringIO("yes\n"),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == ARGPARSE_USAGE_ERROR
    assert "skill_id must not contain traversal segments" in stderr.getvalue()
    assert workflow.generate_calls == []


def test_parse_commit_command_defaults_to_conventional_commits_skill() -> None:
    invocation = parse_args(("commit",))

    assert invocation == ParsedInvocation(
        command=CliCommitCommand(skill_id="conventional-commits"),
        global_options=GlobalOptions(),
        composition_options=CliDeveloperWorkflowCompositionOptions(),
    )


def test_commit_command_help_documents_mutating_pre_commit_gate() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = run_bootstrap_cli(("commit", "--help"), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "Run the staged pre-commit quality gate before message generation" in stdout.getvalue()
    assert "create a git commit only after approval" in stdout.getvalue()


def test_parse_commit_command_supports_commit_message_generation_options() -> None:
    invocation = parse_args(
        (
            "--verbose-diagnostics",
            "commit",
            "--skill",
            "team-style",
            "--model",
            "gpt-5.6-sol",
            "--reasoning-effort",
            "medium",
            "--skill-root",
            "./skills",
        ),
    )

    assert invocation == ParsedInvocation(
        command=CliCommitCommand(skill_id="team-style"),
        global_options=GlobalOptions(verbose_diagnostics=True),
        composition_options=CliDeveloperWorkflowCompositionOptions(
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            skill_roots=(Path("./skills"),),
        ),
    )


def test_parse_commit_command_rejects_unknown_reasoning_effort() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_args(("commit", "--reasoning-effort", "very-high"))

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_parsed_developer_workflow_commands_are_immutable_boundary_values() -> None:
    commit_message_invocation = parse_args(("commit-message",))
    commit_invocation = parse_args(("commit",))

    assert isinstance(commit_message_invocation.command, CliCommitMessageCommand)
    with pytest.raises(FrozenInstanceError):
        commit_message_invocation.command.skill_id = "changed"  # ty: ignore[invalid-assignment]
    assert isinstance(commit_invocation.command, CliCommitCommand)
    with pytest.raises(FrozenInstanceError):
        commit_invocation.command.skill_id = "changed"  # ty: ignore[invalid-assignment]
    assert isinstance(commit_invocation.composition_options.skill_roots, tuple)
