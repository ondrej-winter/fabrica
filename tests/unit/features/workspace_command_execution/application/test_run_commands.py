"""Tests for bounded workspace-command batch scheduling."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from fabrica.features.workspace_command_execution.application.dtos import (
    CommandError,
    CommandErrorCode,
    CommandExecutionLimits,
    CommandExecutionMode,
    CommandExecutionStatus,
    CommandRequest,
    CommandResult,
    ExecutionPolicy,
    PlannedCommand,
    RunCommandsCommand,
    SkippedCommandReason,
)
from fabrica.features.workspace_command_execution.application.ports import CommandSupervisor, RunCommandsContext
from fabrica.features.workspace_command_execution.application.use_cases import PlanCommands, RunCommands

MAX_CONCURRENT_COMMANDS = 2


@dataclass(frozen=True)
class NeverCancelled:
    is_cancelled: bool = False


@dataclass
class MutableCancellation:
    is_cancelled: bool = False


@dataclass
class FakePlanner:
    entries: tuple[PlannedCommand | CommandResult, ...]

    async def plan(self, command: RunCommandsCommand) -> tuple[PlannedCommand | CommandResult, ...]:
        assert len(command.commands) == len(self.entries)
        return self.entries


@dataclass
class ControlledSupervisor:
    delays: dict[int, float] = field(default_factory=dict)
    active: int = 0
    maximum_active: int = 0
    started: list[int] = field(default_factory=list)

    async def run(self, command: PlannedCommand, context: RunCommandsContext) -> CommandResult:
        self.started.append(command.index)
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            await asyncio.sleep(self.delays.get(command.index, 0))
            if context.cancellation.is_cancelled:
                return CommandResult(
                    command.index,
                    _preview(command),
                    CommandExecutionStatus.CANCELLED,
                    1,
                    error=CommandError(CommandErrorCode.COMMAND_CANCELLED),
                )
            if context.deadline_at is not None and datetime.now(UTC) >= context.deadline_at:
                return CommandResult(
                    command.index,
                    _preview(command),
                    CommandExecutionStatus.TIMED_OUT,
                    1,
                    error=CommandError(CommandErrorCode.COMMAND_TIMEOUT),
                )
            return CommandResult(command.index, _preview(command), CommandExecutionStatus.EXITED, 1, exit_code=0)
        finally:
            self.active -= 1


@dataclass
class FailingSupervisor:
    error: BaseException

    async def run(self, command: PlannedCommand, context: RunCommandsContext) -> CommandResult:
        del command, context
        raise self.error


def test_parallel_scheduler_preserves_request_order_despite_out_of_order_completion_and_concurrency_bound() -> None:
    command = _command(ExecutionPolicy.PARALLEL, 3)
    supervisor = ControlledSupervisor({0: 0.04, 1: 0.01, 2: 0.01})

    result = asyncio.run(
        _use_case(_planned(3), supervisor).run(command, _context(max_concurrency=MAX_CONCURRENT_COMMANDS))
    )

    assert [item.index for item in result.results] == [0, 1, 2]
    assert supervisor.maximum_active == MAX_CONCURRENT_COMMANDS
    assert supervisor.started[0:MAX_CONCURRENT_COMMANDS] == [0, 1]


def test_sequential_scheduler_continues_after_pre_execution_failure() -> None:
    rejected = CommandResult(
        0,
        "rejected",
        CommandExecutionStatus.SPAWN_FAILED,
        0,
        error=CommandError(CommandErrorCode.INVALID_INPUT),
    )
    supervisor = ControlledSupervisor()

    result = asyncio.run(
        _use_case((rejected, *_planned(2, offset=1)), supervisor).run(
            _command(ExecutionPolicy.SEQUENTIAL, 3), _context()
        )
    )

    assert [item.status for item in result.results] == [
        CommandExecutionStatus.SPAWN_FAILED,
        CommandExecutionStatus.EXITED,
        CommandExecutionStatus.EXITED,
    ]
    assert supervisor.started == [1, 2]
    assert supervisor.maximum_active == 1


def test_batch_cancellation_skips_unstarted_sequential_commands() -> None:
    cancellation = MutableCancellation()
    supervisor = ControlledSupervisor({0: 0.03})

    async def run() -> tuple[CommandResult, ...]:
        task = asyncio.create_task(
            _use_case(_planned(3), supervisor).run(
                _command(ExecutionPolicy.SEQUENTIAL, 3), _context(cancellation=cancellation)
            )
        )
        await asyncio.sleep(0.005)
        cancellation.is_cancelled = True
        return (await task).results

    results = asyncio.run(run())

    assert results[0].status is CommandExecutionStatus.CANCELLED
    assert [item.reason for item in results[1:]] == [
        SkippedCommandReason.BATCH_CANCELLED,
        SkippedCommandReason.BATCH_CANCELLED,
    ]


def test_batch_timeout_maps_running_command_and_skips_unstarted_sequential_commands() -> None:
    supervisor = ControlledSupervisor({0: 0.03})
    context = _context(batch_timeout_ms=5)

    result = asyncio.run(_use_case(_planned(2), supervisor).run(_command(ExecutionPolicy.SEQUENTIAL, 2), context))

    assert result.results[0].status is CommandExecutionStatus.TIMED_OUT
    assert result.results[0].error is not None
    assert result.results[0].error.code is CommandErrorCode.BATCH_TIMEOUT
    assert result.results[1].status is CommandExecutionStatus.SKIPPED
    assert result.results[1].reason is SkippedCommandReason.BATCH_TIMED_OUT


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (asyncio.CancelledError(), CommandExecutionStatus.CANCELLED, CommandErrorCode.COMMAND_CANCELLED),
        (OSError("synthetic failure"), CommandExecutionStatus.SPAWN_FAILED, CommandErrorCode.INTERNAL_EXECUTION_ERROR),
    ],
)
def test_scheduler_maps_cancelled_and_failed_supervisor_tasks(
    error: BaseException,
    status: CommandExecutionStatus,
    code: CommandErrorCode,
) -> None:
    result = asyncio.run(
        _use_case(_planned(1), FailingSupervisor(error)).run(_command(ExecutionPolicy.SEQUENTIAL, 1), _context())
    )

    command_result = result.results[0]
    assert command_result.status is status
    assert command_result.error is not None
    assert command_result.error.code is code


def _use_case(entries: tuple[PlannedCommand | CommandResult, ...], supervisor: CommandSupervisor) -> RunCommands:
    return RunCommands(planner=cast("PlanCommands", FakePlanner(entries)), supervisor=supervisor)


def _command(execution: ExecutionPolicy, count: int) -> RunCommandsCommand:
    return RunCommandsCommand(
        execution,
        tuple(CommandRequest(CommandExecutionMode.ARGV, argv=(f"command-{index}",)) for index in range(count)),
    )


def _planned(count: int, *, offset: int = 0) -> tuple[PlannedCommand, ...]:
    return tuple(
        PlannedCommand(
            index=index,
            request=CommandRequest(CommandExecutionMode.ARGV, argv=(f"command-{index}",)),
            resolved_cwd=".",
            environment={},
        )
        for index in range(offset, offset + count)
    )


def _context(
    *,
    max_concurrency: int = 3,
    cancellation: NeverCancelled | MutableCancellation | None = None,
    batch_timeout_ms: int | None = None,
) -> RunCommandsContext:
    return RunCommandsContext(
        cancellation=cancellation or NeverCancelled(),
        limits=CommandExecutionLimits(
            max_commands_per_call=3,
            max_concurrent_commands=max_concurrency,
            batch_timeout_ms=batch_timeout_ms,
        ),
        deadline_at=datetime.now(UTC) + timedelta(seconds=1),
    )


def _preview(command: PlannedCommand) -> str:
    assert command.request.argv is not None
    return " ".join(command.request.argv)
