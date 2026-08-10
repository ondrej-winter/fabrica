"""Tests for product CLI contribution aggregation."""

from __future__ import annotations

from fabrica.adapters.inbound.cli.registry import default_cli_contributions
from fabrica.features.agent_runtime.adapters.inbound.cli.command_models import (
    CliRunCommand,
    CliScriptExecuteCommand,
    CliScriptPolicyCommand,
)
from fabrica.features.agent_runtime.application.dtos import SkillScriptType
from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
    CliCommitCommand,
    CliCommitMessageCommand,
)


def test_default_cli_contributions_declare_feature_owned_command_sets() -> None:
    """Keep product CLI aggregation declarative and feature-owned."""
    contributions = default_cli_contributions()

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


def test_default_cli_contributions_route_only_owned_commands() -> None:
    """Guard against product runner feature-specific isinstance chains."""
    agent_runtime, developer_workflow = default_cli_contributions()

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
        approval_script_type=SkillScriptType.PYTHON,
        approval_suffix=".py",
        approval_byte_size=128,
        approval_content_digest="sha256:abc123",
    )
