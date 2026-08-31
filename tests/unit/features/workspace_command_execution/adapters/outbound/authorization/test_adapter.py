"""Tests for explicit host command-admission policy adapters."""

import asyncio

from fabrica.features.workspace_command_execution.adapters.outbound.authorization import (
    HostCommandApprovalResolver,
    HostCommandPermissionEvaluator,
    HostCommandSandboxPreflight,
)
from fabrica.features.workspace_command_execution.application.dtos import (
    CommandExecutionMode,
    CommandRequest,
    PlannedCommand,
)
from fabrica.features.workspace_command_execution.application.ports import CommandPermissionDecision


def test_delegates_each_admission_decision_to_its_explicit_host_callback() -> None:
    command = PlannedCommand(0, CommandRequest(CommandExecutionMode.ARGV, argv=("pwd",)), ".", {"PATH": "/bin"})

    permission = HostCommandPermissionEvaluator(lambda _: _permission_allowed())
    approval = HostCommandApprovalResolver(lambda _: _approved())
    sandbox = HostCommandSandboxPreflight(lambda _: _sandbox_allowed())

    assert asyncio.run(permission.evaluate(command)) is CommandPermissionDecision.ALLOW
    assert asyncio.run(approval.resolve(command)) is True
    assert asyncio.run(sandbox.allow(command)) is True


async def _permission_allowed() -> CommandPermissionDecision:
    return CommandPermissionDecision.ALLOW


async def _approved() -> bool:
    return True


async def _sandbox_allowed() -> bool:
    return True
