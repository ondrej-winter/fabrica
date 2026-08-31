"""Tests for non-interactive POSIX command supervision."""

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep

import pytest

from fabrica.features.workspace_command_execution.adapters.outbound.process_supervisor import (
    PosixCommandSupervisor,
    PosixCommandSupervisorSettings,
    adapter,
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
PROCESS_CLEANUP_TIMEOUT_SECONDS = 2.0


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


def _supervisor(workspace_root: Path, *, termination_grace_seconds: float = 1.0) -> PosixCommandSupervisor:
    return PosixCommandSupervisor(
        workspace_root,
        PosixCommandSupervisorSettings(
            shell_executable="/bin/sh",
            termination_grace_seconds=termination_grace_seconds,
        ),
    )


def _wait_for_process_exit(process_id: int) -> None:
    deadline = monotonic() + PROCESS_CLEANUP_TIMEOUT_SECONDS
    while monotonic() < deadline:
        try:
            os.kill(process_id, 0)
        except ProcessLookupError:
            return
        sleep(0.01)
    pytest.fail(f"process {process_id} remained after supervisor cleanup")


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


def test_process_group_probe_treats_permission_denial_as_not_supervisor_owned(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_process_group_probe(_process_group_id: int, _sent_signal: int) -> None:
        raise PermissionError

    monkeypatch.setattr(adapter.os, "killpg", deny_process_group_probe)

    assert not adapter._process_group_exists(1)  # noqa: SLF001 - regression test for cleanup probe.


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
            timeout_ms=4_000,
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


@pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="requires POSIX process groups")
def test_supervisor_escalates_to_kill_and_cleans_a_term_ignoring_descendant(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    child_script = (
        "import os,signal,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"open({str(child_pid_path)!r}, 'w', encoding='utf-8').write(str(os.getpid())); "
        "time.sleep(30)"
    )
    parent_script = (
        "import subprocess,sys,time; "
        f"subprocess.Popen((sys.executable, '-c', {child_script!r})); "
        "time.sleep(0.2); "
        "time.sleep(30)"
    )
    command = PlannedCommand(
        index=0,
        request=CommandRequest(
            CommandExecutionMode.ARGV,
            argv=(sys.executable, "-c", parent_script),
            timeout_ms=500,
        ),
        resolved_cwd=".",
        environment={},
    )

    result = asyncio.run(_supervisor(tmp_path, termination_grace_seconds=0.05).run(command, _context()))

    assert result.status is CommandExecutionStatus.TIMED_OUT
    assert result.error is not None
    assert result.error.code is CommandErrorCode.COMMAND_TIMEOUT
    child_process_id = int(child_pid_path.read_text(encoding="utf-8"))
    _wait_for_process_exit(child_process_id)
