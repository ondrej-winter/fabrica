"""Tests for host-policy command planning."""

import asyncio
from dataclasses import dataclass, field

import pytest

from fabrica.features.workspace_command_execution.application.dtos import (
    CommandErrorCode,
    CommandExecutionMode,
    CommandRequest,
    CommandResult,
    ExecutionPolicy,
    PlannedCommand,
    RunCommandsCommand,
)
from fabrica.features.workspace_command_execution.application.errors import CommandPlanningError
from fabrica.features.workspace_command_execution.application.ports import CommandPermissionDecision
from fabrica.features.workspace_command_execution.application.use_cases import PlanCommands

COMMAND_COUNT = 2


@dataclass
class FakeResolver:
    resolved_cwd: str = "."
    error: Exception | None = None

    def resolve_cwd(self, requested_cwd: str) -> str:
        assert requested_cwd
        if self.error is not None:
            raise self.error
        return self.resolved_cwd


@dataclass
class FakeEnvironmentBuilder:
    environment: dict[str, str] = field(default_factory=lambda: {"PATH": "/bin"})
    seen_overrides: list[dict[str, str]] = field(default_factory=list)

    def build_environment(self, requested_overrides: dict[str, str]) -> dict[str, str]:
        self.seen_overrides.append(requested_overrides)
        return self.environment | requested_overrides


@dataclass
class FakePermissionEvaluator:
    decision: CommandPermissionDecision = CommandPermissionDecision.ALLOW
    commands: list[PlannedCommand] = field(default_factory=list)

    async def evaluate(self, command: PlannedCommand) -> CommandPermissionDecision:
        self.commands.append(command)
        return self.decision


@dataclass
class FakeApprovalResolver:
    approved: bool = True
    commands: list[PlannedCommand] = field(default_factory=list)

    async def resolve(self, command: PlannedCommand) -> bool:
        self.commands.append(command)
        return self.approved


@dataclass
class FakeSandboxPreflight:
    allowed: bool = True
    commands: list[PlannedCommand] = field(default_factory=list)

    async def allow(self, command: PlannedCommand) -> bool:
        self.commands.append(command)
        return self.allowed


def _planner(
    *,
    resolver: FakeResolver | None = None,
    environment: FakeEnvironmentBuilder | None = None,
    permission: FakePermissionEvaluator | None = None,
    approval: FakeApprovalResolver | None = None,
    sandbox: FakeSandboxPreflight | None = None,
) -> PlanCommands:
    return PlanCommands(
        resolver or FakeResolver(),
        environment or FakeEnvironmentBuilder(),
        permission or FakePermissionEvaluator(),
        approval or FakeApprovalResolver(),
        sandbox or FakeSandboxPreflight(),
    )


def test_plan_resolves_environment_and_applies_identical_policy_to_argv_and_shell() -> None:
    permission = FakePermissionEvaluator()
    sandbox = FakeSandboxPreflight()
    environment = FakeEnvironmentBuilder()
    command = RunCommandsCommand(
        ExecutionPolicy.PARALLEL,
        (
            CommandRequest(CommandExecutionMode.ARGV, argv=("git", "status"), env={"CI": "1"}),
            CommandRequest(CommandExecutionMode.SHELL, shell="echo ok"),  # noqa: S604 - DTO keyword, no execution.
        ),
    )

    entries = asyncio.run(_planner(environment=environment, permission=permission, sandbox=sandbox).plan(command))

    assert all(isinstance(entry, PlannedCommand) for entry in entries)
    assert [item.index for item in permission.commands] == [0, 1]
    assert [item.index for item in sandbox.commands] == [0, 1]
    assert environment.seen_overrides == [{"CI": "1"}, {}]


@pytest.mark.parametrize(
    ("error_code", "expected_code"),
    [
        (CommandErrorCode.INVALID_CWD, CommandErrorCode.INVALID_CWD),
        (CommandErrorCode.CWD_OUTSIDE_WORKSPACE, CommandErrorCode.CWD_OUTSIDE_WORKSPACE),
    ],
)
def test_plan_returns_distinct_command_scoped_cwd_failures(
    error_code: CommandErrorCode, expected_code: CommandErrorCode
) -> None:
    command = RunCommandsCommand(ExecutionPolicy.PARALLEL, (CommandRequest(CommandExecutionMode.ARGV, argv=("pwd",)),))

    entry = asyncio.run(
        _planner(resolver=FakeResolver(error=CommandPlanningError(error_code, "safe cwd failure"))).plan(command)
    )[0]

    assert isinstance(entry, CommandResult)
    assert entry.error is not None
    assert entry.error.code is expected_code


def test_plan_maps_unexpected_boundary_errors_to_internal_failure() -> None:
    command = RunCommandsCommand(ExecutionPolicy.PARALLEL, (CommandRequest(CommandExecutionMode.ARGV, argv=("pwd",)),))

    entry = asyncio.run(_planner(resolver=FakeResolver(error=OSError("synthetic failure"))).plan(command))[0]

    assert isinstance(entry, CommandResult)
    assert entry.error is not None
    assert entry.error.code is CommandErrorCode.INTERNAL_EXECUTION_ERROR


def test_plan_maps_permission_denial_and_approval_rejection_without_sandbox_execution() -> None:
    command = RunCommandsCommand(ExecutionPolicy.PARALLEL, (CommandRequest(CommandExecutionMode.ARGV, argv=("pwd",)),))
    denied_sandbox = FakeSandboxPreflight()
    denied_planner = _planner(
        permission=FakePermissionEvaluator(CommandPermissionDecision.DENY),
        sandbox=denied_sandbox,
    )
    permission_result = asyncio.run(denied_planner.plan(command))[0]
    approval = FakeApprovalResolver(approved=False)
    approval_sandbox = FakeSandboxPreflight()
    approval_result = asyncio.run(
        _planner(
            permission=FakePermissionEvaluator(CommandPermissionDecision.REQUIRE_APPROVAL),
            approval=approval,
            sandbox=approval_sandbox,
        ).plan(command)
    )[0]

    assert isinstance(permission_result, CommandResult)
    assert permission_result.error is not None
    assert permission_result.error.code is CommandErrorCode.PERMISSION_DENIED
    assert denied_sandbox.commands == []
    assert isinstance(approval_result, CommandResult)
    assert approval_result.error is not None
    assert approval_result.error.code is CommandErrorCode.PERMISSION_DENIED
    assert len(approval.commands) == 1
    assert approval_sandbox.commands == []


def test_plan_maps_sandbox_rejection_and_continues_after_another_command_fails() -> None:
    command = RunCommandsCommand(
        ExecutionPolicy.SEQUENTIAL,
        (
            CommandRequest(CommandExecutionMode.ARGV, argv=("first",)),
            CommandRequest(CommandExecutionMode.SHELL, shell="echo second"),  # noqa: S604 - DTO keyword, no execution.
        ),
    )
    resolver = FakeResolver(error=CommandPlanningError(CommandErrorCode.CWD_OUTSIDE_WORKSPACE, "outside"))
    entries = asyncio.run(_planner(resolver=resolver).plan(command))
    sandbox_entries = asyncio.run(_planner(sandbox=FakeSandboxPreflight(allowed=False)).plan(command))

    results = tuple(entry for entry in entries if isinstance(entry, CommandResult))
    sandbox_results = tuple(entry for entry in sandbox_entries if isinstance(entry, CommandResult))
    assert len(results) == len(entries) == COMMAND_COUNT
    assert [entry.index for entry in results] == [0, 1]
    assert all(
        entry.error is not None and entry.error.code is CommandErrorCode.CWD_OUTSIDE_WORKSPACE for entry in results
    )
    assert len(sandbox_results) == len(sandbox_entries) == COMMAND_COUNT
    assert all(
        entry.error is not None and entry.error.code is CommandErrorCode.SANDBOX_DENIED for entry in sandbox_results
    )
