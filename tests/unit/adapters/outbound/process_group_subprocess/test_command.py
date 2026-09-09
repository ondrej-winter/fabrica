"""Tests for process-group command orchestration."""

from __future__ import annotations

import math
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from fabrica.adapters.outbound.process_group_subprocess import (
    ProcessGroupCommandSettings,
    run_process_group_command,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

TEST_PID = 1234
NON_ZERO_RETURN_CODE = 7


@dataclass
class _FakeProcess:
    """Scripted subprocess-like object for command tests."""

    outcomes: list[tuple[str, str] | BaseException]
    pid: int = TEST_PID
    returncode: int | None = 0
    communicate_calls: list[float | None] = field(default_factory=list)

    def communicate(
        self,
        input: bytes | str | None = None,  # noqa: A002, ARG002 - matches subprocess.Popen.communicate.
        timeout: float | None = None,
    ) -> tuple[str, str]:
        """Record the timeout and return or raise the next scripted outcome."""
        self.communicate_calls.append(timeout)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@dataclass
class _FakeProcessFactory:
    """Record process construction and return one scripted process."""

    process: _FakeProcess
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], **kwargs: object) -> _FakeProcess:
        """Record one construction request."""
        self.calls.append({"argv": argv, **kwargs})
        return self.process


def test_run_process_group_command_starts_command_in_new_session_without_shell(tmp_path: Path) -> None:
    process = _FakeProcess(outcomes=[("ok", "")], returncode=NON_ZERO_RETURN_CODE)
    factory = _FakeProcessFactory(process=process)

    result = run_process_group_command(
        ("python", "script.py"),
        cwd=tmp_path,
        timeout_seconds=3.0,
        settings=ProcessGroupCommandSettings(env={}, text=True, process_factory=factory),
    )

    assert result.returncode == NON_ZERO_RETURN_CODE
    assert result.stdout == "ok"
    assert factory.calls == [
        {
            "argv": ["python", "script.py"],
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": tmp_path,
            "env": {},
            "shell": False,
            "text": True,
            "start_new_session": True,
        }
    ]
    assert process.communicate_calls == [3.0]


def test_run_process_group_command_raises_timeout_with_cleanup_output() -> None:
    process = _FakeProcess(
        outcomes=[
            subprocess.TimeoutExpired(cmd=["tool"], timeout=1.0),
            ("partial stdout", "partial stderr"),
        ]
    )
    sent_signals: list[tuple[int, signal.Signals]] = []

    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(
                termination_grace_seconds=0.5,
                process_factory=_FakeProcessFactory(process=process),
                group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append(
                    (process_group_id, sent_signal)
                ),
            ),
        )

    assert sent_signals == [(TEST_PID, signal.SIGTERM)]
    assert process.communicate_calls == [1.0, 0.5]
    assert exc_info.value.stdout == "partial stdout"
    assert exc_info.value.stderr == "partial stderr"


def test_run_process_group_command_escalates_timeout_cleanup_to_kill() -> None:
    process = _FakeProcess(
        outcomes=[
            subprocess.TimeoutExpired(cmd=["tool"], timeout=1.0),
            subprocess.TimeoutExpired(cmd=["tool"], timeout=0.5),
            ("after kill", ""),
        ]
    )
    sent_signals: list[tuple[int, signal.Signals]] = []

    with pytest.raises(subprocess.TimeoutExpired) as exc_info:
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(
                termination_grace_seconds=0.5,
                process_factory=_FakeProcessFactory(process=process),
                group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append(
                    (process_group_id, sent_signal)
                ),
            ),
        )

    assert sent_signals == [(TEST_PID, signal.SIGTERM), (TEST_PID, signal.SIGKILL)]
    assert process.communicate_calls == [1.0, 0.5, 0.5]
    assert exc_info.value.stdout == "after kill"


def test_run_process_group_command_preserves_wait_failure_when_cleanup_signal_fails() -> None:
    process = _FakeProcess(outcomes=[RuntimeError("wait failed")])

    with pytest.raises(RuntimeError, match="wait failed"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(
                process_factory=_FakeProcessFactory(process=process),
                group_signal_sender=_raise_permission_error,
            ),
        )


def test_run_process_group_command_preserves_wait_failure_when_cleanup_reap_fails() -> None:
    process = _FakeProcess(outcomes=[RuntimeError("wait failed"), RuntimeError("cleanup failed")])

    with pytest.raises(RuntimeError, match="wait failed"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(process_factory=_FakeProcessFactory(process=process)),
        )


@pytest.mark.parametrize("timeout_seconds", [0.0, -1.0, math.inf, math.nan])
def test_run_process_group_command_rejects_invalid_timeout_before_spawn(timeout_seconds: float) -> None:
    factory = _FakeProcessFactory(_FakeProcess(outcomes=[]))

    with pytest.raises(ValueError, match="timeout_seconds"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=timeout_seconds,
            settings=ProcessGroupCommandSettings(process_factory=factory),
        )

    assert factory.calls == []


def test_run_process_group_command_rejects_invalid_termination_grace_before_spawn() -> None:
    factory = _FakeProcessFactory(_FakeProcess(outcomes=[]))

    with pytest.raises(ValueError, match="termination_grace_seconds"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(termination_grace_seconds=0.0, process_factory=factory),
        )

    assert factory.calls == []


def test_run_process_group_command_rejects_completed_process_without_return_code() -> None:
    process = _FakeProcess(outcomes=[("ok", "")], returncode=None)

    with pytest.raises(RuntimeError, match="return code"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(process_factory=_FakeProcessFactory(process)),
        )


def test_run_process_group_command_cleans_up_process_group_when_wait_is_interrupted() -> None:
    process = _FakeProcess(outcomes=[KeyboardInterrupt(), ("", "")])
    sent_signals: list[tuple[int, signal.Signals]] = []

    with pytest.raises(KeyboardInterrupt):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(
                termination_grace_seconds=0.5,
                process_factory=_FakeProcessFactory(process=process),
                group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append(
                    (process_group_id, sent_signal)
                ),
            ),
        )

    assert sent_signals == [(TEST_PID, signal.SIGTERM)]
    assert process.communicate_calls == [1.0, 0.5]


def _raise_permission_error(_process_group_id: int, _sent_signal: signal.Signals) -> None:
    raise PermissionError
