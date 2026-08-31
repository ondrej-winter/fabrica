"""Bounded scheduling for planned workspace command batches."""

import asyncio
from collections import deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from fabrica.features.workspace_command_execution.application.dtos import (
    DEFAULT_MAX_COMMAND_PREVIEW_CHARS,
    CommandError,
    CommandErrorCode,
    CommandExecutionStatus,
    CommandResult,
    ExecutionPolicy,
    PlannedCommand,
    RunCommandsCommand,
    RunCommandsResult,
    SkippedCommandReason,
)
from fabrica.features.workspace_command_execution.application.output_limiting import limit_run_commands_result
from fabrica.features.workspace_command_execution.application.ports import (
    CommandSupervisor,
    RunCommandsContext,
    RunCommandsPort,
)
from fabrica.features.workspace_command_execution.application.use_cases.plan_commands import PlanCommands

_SCHEDULER_POLL_SECONDS = 0.01


@dataclass(frozen=True, slots=True)
class RunCommands(RunCommandsPort):
    """Plan and execute an ordered batch with bounded host-owned concurrency."""

    planner: PlanCommands
    supervisor: CommandSupervisor

    async def run(self, command: RunCommandsCommand, context: RunCommandsContext) -> RunCommandsResult:
        """Execute every eligible command and return one ordered, output-bounded result."""
        entries = await self.planner.plan(command)
        results: list[CommandResult | None] = [entry if isinstance(entry, CommandResult) else None for entry in entries]
        queued = deque(entry for entry in entries if isinstance(entry, PlannedCommand))
        deadline_at, batch_deadline_at = _deadlines(context)
        active: dict[asyncio.Task[CommandResult], PlannedCommand] = {}
        concurrency = 1 if command.execution is ExecutionPolicy.SEQUENTIAL else context.limits.max_concurrent_commands

        while active or queued:
            stop_reason = _stop_reason(context, deadline_at)
            if stop_reason is not None:
                _skip_queued(results, queued, stop_reason)
            while queued and len(active) < concurrency and stop_reason is None:
                planned = queued.popleft()
                task_context = replace(context, deadline_at=deadline_at)
                active[asyncio.create_task(self.supervisor.run(planned, task_context))] = planned
                if command.execution is ExecutionPolicy.SEQUENTIAL:
                    break
            if not active:
                continue
            done, _ = await asyncio.wait(active, timeout=_SCHEDULER_POLL_SECONDS, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                planned = active.pop(task)
                results[planned.index] = _task_result(task, planned, batch_deadline_at)

        if any(result is None for result in results):
            msg = "command scheduler did not produce an outcome for every command"
            raise RuntimeError(msg)
        completed = RunCommandsResult(command.execution, tuple(result for result in results if result is not None))
        return limit_run_commands_result(
            completed,
            max_serialized_chars=context.limits.max_serialized_result_chars,
            max_command_output_chars=context.limits.max_command_output_chars,
        )


def _deadlines(context: RunCommandsContext) -> tuple[datetime | None, datetime | None]:
    if context.limits.batch_timeout_ms is None:
        return context.deadline_at, None
    batch_deadline = datetime.now(UTC) + timedelta(milliseconds=context.limits.batch_timeout_ms)
    effective_deadline = batch_deadline if context.deadline_at is None else min(batch_deadline, context.deadline_at)
    return effective_deadline, batch_deadline


def _stop_reason(context: RunCommandsContext, deadline_at: datetime | None) -> SkippedCommandReason | None:
    if context.cancellation.is_cancelled:
        return SkippedCommandReason.BATCH_CANCELLED
    if deadline_at is not None and datetime.now(UTC) >= deadline_at:
        return SkippedCommandReason.BATCH_TIMED_OUT
    return None


def _skip_queued(
    results: list[CommandResult | None],
    queued: deque[PlannedCommand],
    reason: SkippedCommandReason,
) -> None:
    while queued:
        command = queued.popleft()
        results[command.index] = CommandResult(
            index=command.index,
            command_preview=_command_preview(command),
            status=CommandExecutionStatus.SKIPPED,
            duration_ms=0,
            reason=reason,
        )


def _task_result(
    task: asyncio.Task[CommandResult], command: PlannedCommand, batch_deadline_at: datetime | None
) -> CommandResult:
    if task.cancelled():
        return _cancelled_result(command)
    try:
        result = task.result()
    except (OSError, RuntimeError, ValueError):
        return _internal_failure_result(command)
    if (
        result.status is CommandExecutionStatus.TIMED_OUT
        and batch_deadline_at is not None
        and datetime.now(UTC) >= batch_deadline_at
    ):
        return replace(
            result,
            error=CommandError(CommandErrorCode.BATCH_TIMEOUT, "batch execution deadline was reached"),
        )
    return result


def _cancelled_result(command: PlannedCommand) -> CommandResult:
    return CommandResult(
        index=command.index,
        command_preview=_command_preview(command),
        status=CommandExecutionStatus.CANCELLED,
        duration_ms=0,
        error=CommandError(CommandErrorCode.COMMAND_CANCELLED, "command execution was cancelled"),
    )


def _internal_failure_result(command: PlannedCommand) -> CommandResult:
    return CommandResult(
        index=command.index,
        command_preview=_command_preview(command),
        status=CommandExecutionStatus.SPAWN_FAILED,
        duration_ms=0,
        error=CommandError(CommandErrorCode.INTERNAL_EXECUTION_ERROR, "command supervision failed"),
    )


def _command_preview(command: PlannedCommand) -> str:
    request = command.request
    preview = request.shell if request.shell is not None else " ".join(request.argv or ())
    return preview[:DEFAULT_MAX_COMMAND_PREVIEW_CHARS]
