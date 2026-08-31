"""Tests for non-interactive POSIX command supervision."""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from fabrica.features.workspace_command_execution.adapters.outbound.process_supervisor import (
    PosixCommandSupervisor,
    PosixCommandSupervisorSettings,
)
from fabrica.features.workspace_command_execution.application.dtos import (
    CommandErrorCode,
    CommandExecutionLimits,
    CommandExecutionMode,
    CommandExecutionStatus,
    CommandRequest,
    PlannedCommand,
)
from fabrica.features.workspace_command_execution.application.ports import RunCommandsContext

NON_ZERO_EXIT_CODE = 7


@dataclass(frozen=True)
class Cancellation:
    is_cancelled: bool = False


def _command(*, mode: CommandExecutionMode = CommandExecutionMode.ARGV, timeout_ms: int = 1_000) -> PlannedCommand:
    request = (
        CommandRequest(
            mode,
            argv=(sys.executable, "-c", "print('out'); import sys; print('err', file=sys.stderr)"),
            timeout_ms=timeout_ms,
        )
        if mode is CommandExecutionMode.ARGV
        else CommandRequest(mode, shell="printf shell-output", timeout_ms=timeout_ms)  # noqa: S604 - DTO only; host shell is tested.
    )
    return PlannedCommand(index=0, request=request, resolved_cwd=".", environment={})


def _context(*, cancelled: bool = False) -> RunCommandsContext:
    return RunCommandsContext(cancellation=Cancellation(cancelled), limits=CommandExecutionLimits())


def _supervisor(workspace_root: Path) -> PosixCommandSupervisor:
    return PosixCommandSupervisor(workspace_root, PosixCommandSupervisorSettings(shell_executable="/bin/sh"))


def test_supervisor_uses_direct_argv_with_closed_stdin_and_separate_streams(tmp_path: Path) -> None:
    result = asyncio.run(_supervisor(tmp_path).run(_command(), _context()))

    assert result.status is CommandExecutionStatus.EXITED
    assert result.exit_code == 0
    assert result.output.stdout == "out\n"
    assert result.output.stderr == "err\n"


def test_supervisor_uses_only_host_configured_shell_for_shell_mode(tmp_path: Path) -> None:
    result = asyncio.run(_supervisor(tmp_path).run(_command(mode=CommandExecutionMode.SHELL), _context()))

    assert result.status is CommandExecutionStatus.EXITED
    assert result.exit_code == 0
    assert result.output.stdout == "shell-output"


def test_supervisor_keeps_non_zero_exit_as_normal_result(tmp_path: Path) -> None:
    command = PlannedCommand(
        index=0,
        request=CommandRequest(
            CommandExecutionMode.ARGV,
            argv=(sys.executable, "-c", f"import sys; sys.exit({NON_ZERO_EXIT_CODE})"),
        ),
        resolved_cwd=".",
        environment={},
    )

    result = asyncio.run(_supervisor(tmp_path).run(command, _context()))

    assert result.status is CommandExecutionStatus.EXITED
    assert result.exit_code == NON_ZERO_EXIT_CODE
    assert result.error is None


def test_supervisor_maps_missing_executable_to_spawn_failure(tmp_path: Path) -> None:
    command = PlannedCommand(
        index=0,
        request=CommandRequest(CommandExecutionMode.ARGV, argv=("not-a-real-fabrica-command",)),
        resolved_cwd=".",
        environment={},
    )

    result = asyncio.run(_supervisor(tmp_path).run(command, _context()))

    assert result.status is CommandExecutionStatus.SPAWN_FAILED
    assert result.error is not None
    assert result.error.code is CommandErrorCode.EXECUTABLE_NOT_FOUND


@pytest.mark.parametrize(
    ("is_cancelled", "expected_status", "expected_error"),
    [
        (True, CommandExecutionStatus.CANCELLED, CommandErrorCode.COMMAND_CANCELLED),
        (False, CommandExecutionStatus.TIMED_OUT, CommandErrorCode.COMMAND_TIMEOUT),
    ],
)
def test_supervisor_terminates_long_running_command_and_preserves_partial_output(
    tmp_path: Path,
    is_cancelled,
    expected_status: CommandExecutionStatus,
    expected_error: CommandErrorCode,
) -> None:
    command = PlannedCommand(
        index=0,
        request=CommandRequest(
            CommandExecutionMode.ARGV,
            argv=(sys.executable, "-c", "import sys,time; print('before'); sys.stdout.flush(); time.sleep(5)"),
            timeout_ms=50,
        ),
        resolved_cwd=".",
        environment={},
    )

    result = asyncio.run(_supervisor(tmp_path).run(command, _context(cancelled=is_cancelled)))

    assert result.status is expected_status
    assert result.error is not None
    assert result.error.code is expected_error
    if is_cancelled:
        assert result.output.stdout == ""
    else:
        assert result.output.stdout == "before\n"
