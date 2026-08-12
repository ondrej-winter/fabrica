"""Tests for product CLI contribution aggregation."""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from fabrica.adapters.inbound.cli import CliCommandExecutionOptions, build_parser, run_cli_command
from fabrica.adapters.inbound.cli import parse_args as parse_cli_args
from fabrica.adapters.inbound.cli.contributions import CliContribution
from fabrica.bootstrap.cli import create_cli_contributions
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptApprovalOptions,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
)
from fabrica.features.agent_runtime.application.dtos import SkillScriptType
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.contributions import CliSubparsers

ARGPARSE_USAGE_ERROR = 2
SYNTHETIC_EXIT_CODE = 42


def test_parser_registers_only_supplied_contributions() -> None:
    """Keep command registration explicit instead of hidden behind a default registry."""
    parser = build_parser((_synthetic_contribution(),))

    assert parser.parse_args(["synthetic"]).command_factory(Namespace()).name == "synthetic"

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["run", "--prompt", "pong"])

    assert exc_info.value.code == ARGPARSE_USAGE_ERROR


def test_runner_dispatches_only_supplied_contributions() -> None:
    """Keep command dispatch explicit instead of hidden behind a default registry."""
    command = _SyntheticCommand(name="synthetic")

    exit_code = run_cli_command(command, options=CliCommandExecutionOptions(contributions=(_synthetic_contribution(),)))

    assert exit_code == SYNTHETIC_EXIT_CODE

    with pytest.raises(RuntimeError, match="no CLI contribution registered"):
        run_cli_command(command, options=CliCommandExecutionOptions(contributions=()))


def test_parser_rejects_contribution_without_command_factory() -> None:
    parser = build_parser((_malformed_contribution_without_command_factory(),))
    namespace = parser.parse_args(["malformed"])

    assert not hasattr(namespace, "command_factory")


def test_parse_args_reports_missing_command_factory() -> None:
    with pytest.raises(TypeError, match="did not configure a command factory"):
        parse_cli_args(["malformed"], contributions=(_malformed_contribution_without_command_factory(),))


def test_contribution_validation_rejects_duplicate_command_ownership() -> None:
    duplicate = CliContribution(
        name="duplicate_synthetic",
        command_types=(_SyntheticCommand,),
        register_commands=_ignore_registration,
        run_command=_synthetic_run_command,
    )

    with pytest.raises(ValueError, match="duplicate CLI command type ownership"):
        build_parser((_synthetic_contribution(), duplicate))

    with pytest.raises(ValueError, match="duplicate CLI command type ownership"):
        run_cli_command(
            _SyntheticCommand(name="synthetic"),
            options=CliCommandExecutionOptions(contributions=(_synthetic_contribution(), duplicate)),
        )


def test_contribution_validation_rejects_duplicate_names() -> None:
    duplicate_name = CliContribution(
        name="synthetic",
        command_types=(_OtherSyntheticCommand,),
        register_commands=_ignore_registration,
        run_command=_synthetic_run_command,
    )

    with pytest.raises(ValueError, match="duplicate CLI contribution name"):
        build_parser((_synthetic_contribution(), duplicate_name))


def test_bootstrap_cli_contributions_declare_feature_owned_command_sets() -> None:
    """Keep product CLI aggregation declarative, bootstrap-owned, and feature-owned."""
    contributions = create_cli_contributions()

    assert tuple(contribution.name for contribution in contributions) == (
        "agent_runtime",
        "developer_workflow",
    )
    assert contributions[0].command_types == (
        CliRunCommand,
        CliScriptPolicyCommand,
        CliScriptExecuteCommand,
    )
    assert contributions[1].command_types == (
        CliCommitMessageCommand,
        CliCommitCommand,
    )


def test_bootstrap_cli_contributions_route_only_owned_commands() -> None:
    """Guard against product runner feature-specific isinstance chains."""
    agent_runtime, developer_workflow = create_cli_contributions()

    assert agent_runtime.can_handle(CliRunCommand(prompt="pong"))
    assert agent_runtime.can_handle(CliScriptPolicyCommand(skill_id="python-testing", script_id="scripts/check.py"))
    assert agent_runtime.can_handle(_script_execute_command())
    assert not agent_runtime.can_handle(CliCommitMessageCommand())
    assert not agent_runtime.can_handle(CliCommitCommand())

    assert developer_workflow.can_handle(CliCommitMessageCommand())
    assert developer_workflow.can_handle(CliCommitCommand())
    assert not developer_workflow.can_handle(CliRunCommand(prompt="pong"))


def _script_execute_command() -> CliScriptExecuteCommand:
    return CliScriptExecuteCommand(
        skill_id="python-testing",
        script_id="scripts/check.py",
        approval_options=CliScriptApprovalOptions(
            script_type=SkillScriptType.PYTHON,
            suffix=".py",
            byte_size=128,
            content_digest="sha256:abc123",
        ),
    )


@dataclass(frozen=True, slots=True)
class _SyntheticCommand:
    name: str


@dataclass(frozen=True, slots=True)
class _OtherSyntheticCommand:
    name: str


def _synthetic_contribution() -> CliContribution:
    def register(subparsers: CliSubparsers) -> None:
        parser = subparsers.add_parser("synthetic")
        parser.set_defaults(command_factory=_synthetic_command_factory)

    def run(command: object, context: object) -> int:
        _ = command, context
        return SYNTHETIC_EXIT_CODE

    return CliContribution(
        name="synthetic",
        command_types=(_SyntheticCommand,),
        register_commands=register,
        run_command=run,
    )


def _ignore_registration(subparsers: CliSubparsers) -> None:
    _ = subparsers


def _synthetic_run_command(command: object, context: object) -> int:
    _ = command, context
    return SYNTHETIC_EXIT_CODE


def _malformed_contribution_without_command_factory() -> CliContribution:
    def register(subparsers: CliSubparsers) -> None:
        subparsers.add_parser("malformed")

    def run(command: object, context: object) -> int:
        _ = command, context
        return SYNTHETIC_EXIT_CODE

    return CliContribution(
        name="malformed",
        command_types=(_SyntheticCommand,),
        register_commands=register,
        run_command=run,
    )


def _synthetic_command_factory(namespace: Namespace) -> _SyntheticCommand:
    _ = namespace
    return _SyntheticCommand(name="synthetic")
