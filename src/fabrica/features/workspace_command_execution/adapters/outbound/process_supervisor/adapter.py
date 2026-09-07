"""Non-interactive POSIX process-group supervision for planned commands."""
# ruff: noqa: C901, PLR0911, PLR0913

from __future__ import annotations

import asyncio
import os
import signal
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING

from fabrica.features.workspace_command_execution.application.dtos import (
    DEFAULT_MAX_COMMAND_PREVIEW_CHARS,
    CommandError,
    CommandErrorCode,
    CommandExecutionMode,
    CommandExecutionOutput,
    CommandExecutionStatus,
    CommandResult,
    PlannedCommand,
)

if TYPE_CHECKING:
    from pathlib import Path

    from fabrica.features.workspace_command_execution.application.ports import RunCommandsContext

_POLL_INTERVAL_SECONDS = 0.01
_DEFAULT_TERMINATION_GRACE_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class PosixCommandSupervisorSettings:
    """Host-owned POSIX process-supervision configuration."""

    shell_executable: str
    termination_grace_seconds: float = _DEFAULT_TERMINATION_GRACE_SECONDS

    def __post_init__(self) -> None:
        if not self.shell_executable or "\x00" in self.shell_executable:
            msg = "shell_executable must be a non-empty string without NUL bytes"
            raise ValueError(msg)
        if self.termination_grace_seconds <= 0:
            msg = "termination_grace_seconds must be positive"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PosixCommandSupervisor:
    """Run planned commands in isolated POSIX process groups without interactive input."""

    workspace_root: Path
    settings: PosixCommandSupervisorSettings

    async def run(self, command: PlannedCommand, context: RunCommandsContext) -> CommandResult:
        """Execute one planned command and translate terminal process outcomes."""
        started_at = monotonic()
        preview = _command_preview(command)
        try:
            process = await asyncio.create_subprocess_exec(
                *_spawn_argv(command, self.settings.shell_executable),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_root / command.resolved_cwd,
                env=dict(command.environment),
                start_new_session=True,
            )
        except FileNotFoundError:
            return _failure_result(
                command.index,
                preview,
                started_at,
                CommandErrorCode.EXECUTABLE_NOT_FOUND,
                "command executable was not found",
            )
        except PermissionError:
            return _failure_result(
                command.index,
                preview,
                started_at,
                CommandErrorCode.PERMISSION_DENIED,
                "command executable permission was denied",
            )
        except OSError:
            return _failure_result(
                command.index, preview, started_at, CommandErrorCode.SPAWN_FAILED, "command could not be started"
            )

        if process.stdout is None or process.stderr is None or process.pid is None:
            await _terminate_process_group(process, self.settings.termination_grace_seconds)
            return _failure_result(
                command.index,
                preview,
                started_at,
                CommandErrorCode.INTERNAL_EXECUTION_ERROR,
                "command process did not expose required output streams",
            )

        stdout_task = asyncio.create_task(process.stdout.read())
        stderr_task = asyncio.create_task(process.stderr.read())
        outcome: CommandExecutionStatus | None = None
        try:
            outcome = await _wait_for_completion(process, context, command.request.timeout_ms)
        except asyncio.CancelledError:
            await _terminate_process_group(process, self.settings.termination_grace_seconds)
            raise
        finally:
            if outcome is CommandExecutionStatus.TIMED_OUT or outcome is CommandExecutionStatus.CANCELLED:
                await _terminate_process_group(process, self.settings.termination_grace_seconds)

        stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
        output = _output(stdout, stderr)
        duration_ms = _duration_ms(started_at)
        if outcome is CommandExecutionStatus.TIMED_OUT:
            return CommandResult(
                index=command.index,
                command_preview=preview,
                status=outcome,
                duration_ms=duration_ms,
                output=output,
                error=CommandError(CommandErrorCode.COMMAND_TIMEOUT, "command deadline expired"),
            )
        if outcome is CommandExecutionStatus.CANCELLED:
            return CommandResult(
                index=command.index,
                command_preview=preview,
                status=outcome,
                duration_ms=duration_ms,
                output=output,
                error=CommandError(CommandErrorCode.COMMAND_CANCELLED, "command execution was cancelled"),
            )

        returncode = process.returncode
        if returncode is None:
            return _failure_result(
                command.index,
                preview,
                started_at,
                CommandErrorCode.INTERNAL_EXECUTION_ERROR,
                "command completed without a return code",
                output=output,
            )
        if returncode < 0:
            return CommandResult(
                index=command.index,
                command_preview=preview,
                status=CommandExecutionStatus.EXITED,
                duration_ms=duration_ms,
                output=output,
                signal=signal.Signals(-returncode).name,
            )
        return CommandResult(
            index=command.index,
            command_preview=preview,
            status=CommandExecutionStatus.EXITED,
            duration_ms=duration_ms,
            output=output,
            exit_code=returncode,
        )


async def _wait_for_completion(
    process: asyncio.subprocess.Process, context: RunCommandsContext, timeout_ms: int
) -> CommandExecutionStatus | None:
    deadline = _effective_deadline(timeout_ms, context.deadline_at)
    while process.returncode is None:
        if context.cancellation.is_cancelled:
            return CommandExecutionStatus.CANCELLED
        if monotonic() >= deadline:
            return CommandExecutionStatus.TIMED_OUT
        try:
            await asyncio.wait_for(
                asyncio.shield(process.wait()), timeout=min(_POLL_INTERVAL_SECONDS, deadline - monotonic())
            )
        except TimeoutError:
            continue
    return None


def _effective_deadline(timeout_ms: int, host_deadline: datetime | None) -> float:
    deadline = monotonic() + timeout_ms / 1_000
    if host_deadline is None:
        return deadline
    return min(deadline, monotonic() + max(0.0, (host_deadline - datetime.now(UTC)).total_seconds()))


async def _terminate_process_group(process: asyncio.subprocess.Process, grace_seconds: float) -> None:
    if process.pid is None:
        return
    process_group_id = process.pid
    _send_group_signal(process_group_id, signal.SIGTERM)
    grace_deadline = monotonic() + grace_seconds
    while _process_group_exists(process_group_id) and monotonic() < grace_deadline:
        try:
            await asyncio.wait_for(
                asyncio.shield(process.wait()),
                timeout=min(_POLL_INTERVAL_SECONDS, max(0.0, grace_deadline - monotonic())),
            )
        except TimeoutError:
            continue
    if _process_group_exists(process_group_id):
        _send_group_signal(process_group_id, signal.SIGKILL)
    await asyncio.gather(process.wait(), return_exceptions=True)


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except PermissionError, ProcessLookupError:
        return False
    return True


def _send_group_signal(process_group_id: int, sent_signal: signal.Signals) -> None:
    with suppress(PermissionError, ProcessLookupError):
        os.killpg(process_group_id, sent_signal)


def _spawn_argv(command: PlannedCommand, shell_executable: str) -> tuple[str, ...]:
    if command.request.mode is CommandExecutionMode.ARGV:
        if command.request.argv is not None:
            return command.request.argv
    elif command.request.shell is not None:
        return (shell_executable, "-c", command.request.shell)
    # PlannedCommand originates from validated CommandRequest DTOs.
    msg = "planned command is missing its validated invocation"  # pragma: no cover
    raise RuntimeError(msg)  # pragma: no cover


def _command_preview(command: PlannedCommand) -> str:
    request = command.request
    return (request.shell if request.shell is not None else " ".join(request.argv or ()))[
        :DEFAULT_MAX_COMMAND_PREVIEW_CHARS
    ]


def _output(stdout: bytes, stderr: bytes) -> CommandExecutionOutput:
    decoded_stdout = stdout.decode("utf-8", errors="replace")
    decoded_stderr = stderr.decode("utf-8", errors="replace")
    retained = len(decoded_stdout) + len(decoded_stderr)
    return CommandExecutionOutput(
        stdout=decoded_stdout,
        stderr=decoded_stderr,
        total_output_chars=retained,
        retained_output_chars=retained,
    )


def _duration_ms(started_at: float) -> int:
    return max(0, round((monotonic() - started_at) * 1_000))


def _failure_result(
    index: int,
    preview: str,
    started_at: float,
    code: CommandErrorCode,
    message: str,
    *,
    output: CommandExecutionOutput | None = None,
) -> CommandResult:
    return CommandResult(
        index=index,
        command_preview=preview,
        status=CommandExecutionStatus.SPAWN_FAILED,
        duration_ms=_duration_ms(started_at),
        output=output or CommandExecutionOutput(),
        error=CommandError(code, message),
    )
