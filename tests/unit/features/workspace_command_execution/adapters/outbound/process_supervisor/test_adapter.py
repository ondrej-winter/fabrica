"""Tests for non-interactive POSIX command supervision."""

import asyncio
import os
import signal
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic, sleep
from typing import cast

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
TEST_PROCESS_ID = 123


@dataclass(frozen=True)
class Cancellation:
    is_cancelled: bool = False


@dataclass
class _Stream:
    content: bytes

    async def read(self) -> bytes:
        return self.content


@dataclass
class _Process:
    stdout: _Stream | None = None
    stderr: _Stream | None = None
    returncode: int | None = 0
    pid: int | None = TEST_PROCESS_ID

    async def wait(self) -> int | None:
        return self.returncode


class _SlowProcess(_Process):
    async def wait(self) -> int | None:
        await asyncio.sleep(1)
        return self.returncode


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


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (PermissionError(), CommandErrorCode.PERMISSION_DENIED),
        (OSError(), CommandErrorCode.SPAWN_FAILED),
    ],
)
def test_supervisor_maps_other_spawn_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error: OSError,
    expected_code: CommandErrorCode,
) -> None:
    async def fail_spawn(*args: object, **kwargs: object) -> _Process:
        del args, kwargs
        raise error

    monkeypatch.setattr(adapter.asyncio, "create_subprocess_exec", fail_spawn)

    result = asyncio.run(_supervisor(tmp_path).run(_command(), _context()))

    assert result.status is CommandExecutionStatus.SPAWN_FAILED
    assert result.error is not None
    assert result.error.code is expected_code


def test_supervisor_rejects_processes_without_required_streams(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = _Process(stdout=None, stderr=_Stream(b"stderr"), pid=TEST_PROCESS_ID)

    async def spawn(*args: object, **kwargs: object) -> _Process:
        del args, kwargs
        return process

    async def terminate(*args: object, **kwargs: object) -> None:
        del args, kwargs

    monkeypatch.setattr(adapter.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(adapter, "_terminate_process_group", terminate)

    result = asyncio.run(_supervisor(tmp_path).run(_command(), _context()))

    assert result.status is CommandExecutionStatus.SPAWN_FAILED
    assert result.error is not None
    assert result.error.code is CommandErrorCode.INTERNAL_EXECUTION_ERROR


@pytest.mark.parametrize(
    ("returncode", "expected_signal"),
    [(None, None), (-signal.SIGTERM, "SIGTERM")],
)
def test_supervisor_maps_missing_return_code_and_signal_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returncode: int | None,
    expected_signal: str | None,
) -> None:
    process = _Process(stdout=_Stream(b"out"), stderr=_Stream(b"err"), returncode=returncode)

    async def spawn(*args: object, **kwargs: object) -> _Process:
        del args, kwargs
        return process

    monkeypatch.setattr(adapter.asyncio, "create_subprocess_exec", spawn)
    if returncode is None:

        async def complete_without_return_code(*args: object, **kwargs: object) -> CommandExecutionStatus | None:
            del args, kwargs
            return None

        monkeypatch.setattr(adapter, "_wait_for_completion", complete_without_return_code)

    result = asyncio.run(_supervisor(tmp_path).run(_command(), _context()))

    if expected_signal is None:
        assert result.status is CommandExecutionStatus.SPAWN_FAILED
        assert result.error is not None
        assert result.error.code is CommandErrorCode.INTERNAL_EXECUTION_ERROR
    else:
        assert result.status is CommandExecutionStatus.EXITED
        assert result.signal == expected_signal


def test_supervisor_reaps_then_reraises_caller_cancellation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = _Process(stdout=_Stream(b""), stderr=_Stream(b""), returncode=None)

    async def spawn(*args: object, **kwargs: object) -> _Process:
        del args, kwargs
        return process

    async def cancelled_wait(*args: object, **kwargs: object) -> CommandExecutionStatus | None:
        del args, kwargs
        raise asyncio.CancelledError

    terminated: list[_Process] = []

    async def terminate(candidate: _Process, grace_seconds: float) -> None:
        del grace_seconds
        terminated.append(candidate)

    monkeypatch.setattr(adapter.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(adapter, "_wait_for_completion", cancelled_wait)
    monkeypatch.setattr(adapter, "_terminate_process_group", terminate)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_supervisor(tmp_path).run(_command(), _context()))

    assert terminated == [process]


@pytest.mark.parametrize(
    ("shell_executable", "termination_grace_seconds", "message"),
    [
        ("", 1.0, "shell_executable"),
        ("/bin/sh\x00", 1.0, "shell_executable"),
        ("/bin/sh", 0.0, "termination_grace_seconds"),
    ],
)
def test_supervisor_settings_reject_invalid_values(
    shell_executable: str, termination_grace_seconds: float, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        PosixCommandSupervisorSettings(shell_executable, termination_grace_seconds)


def test_effective_deadline_honors_an_expired_host_deadline() -> None:
    deadline = adapter._effective_deadline(  # noqa: SLF001 - regression test for host deadline bounding.
        1_000,
        datetime.now(UTC) - timedelta(seconds=1),
    )

    assert deadline <= monotonic()


def test_termination_skips_processes_without_a_pid() -> None:
    process = _Process(pid=None)

    asyncio.run(
        adapter._terminate_process_group(  # noqa: SLF001 - cleanup helper boundary.
            cast("asyncio.subprocess.Process", process), 0.01
        )
    )


def test_termination_retries_graceful_reap_after_a_poll_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _SlowProcess(pid=TEST_PROCESS_ID)
    signals: list[signal.Signals] = []
    probe_results = iter((True, True, False))

    monkeypatch.setattr(adapter, "_process_group_exists", lambda _process_group_id: next(probe_results))
    monkeypatch.setattr(
        adapter, "_send_group_signal", lambda _process_group_id, sent_signal: signals.append(sent_signal)
    )

    asyncio.run(
        adapter._terminate_process_group(  # noqa: SLF001 - cleanup helper boundary.
            cast("asyncio.subprocess.Process", process), 0.001
        )
    )

    assert signals == [signal.SIGTERM]


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
