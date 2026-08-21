"""Tests for the process-group subprocess runner."""

from __future__ import annotations

import math
import signal
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import pytest

from fabrica.adapters.outbound.process_group_subprocess import ProcessGroupCommandSettings, run_process_group_command

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

TEST_PID = 1234
NON_ZERO_RETURN_CODE = 7


@dataclass
class FakeProcess:
    outcomes: list[tuple[str, str] | BaseException]
    pid: int = TEST_PID
    returncode: int | None = 0
    communicate_calls: list[float | None] = field(default_factory=list)

    def communicate(
        self,
        input: bytes | str | None = None,  # noqa: A002, ARG002 - matches subprocess.Popen.communicate.
        timeout: float | None = None,
    ) -> tuple[str, str]:
        self.communicate_calls.append(timeout)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@dataclass
class FakeProcessFactory:
    process: FakeProcess
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(self, argv: Sequence[str], **kwargs: object) -> FakeProcess:
        self.calls.append({"argv": argv, **kwargs})
        return self.process


def test_runner_starts_command_in_new_session_without_shell(tmp_path: Path) -> None:
    process = FakeProcess(outcomes=[("ok", "")], returncode=NON_ZERO_RETURN_CODE)
    factory = FakeProcessFactory(process=process)

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


def test_runner_terminates_process_group_on_timeout_and_preserves_output() -> None:
    process = FakeProcess(
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
                process_factory=FakeProcessFactory(process=process),
                group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append(
                    (process_group_id, sent_signal)
                ),
            ),
        )

    assert sent_signals == [(TEST_PID, signal.SIGTERM)]
    assert process.communicate_calls == [1.0, 0.5]
    assert exc_info.value.stdout == "partial stdout"
    assert exc_info.value.stderr == "partial stderr"


def test_runner_escalates_to_force_kill_when_process_group_survives_grace_period() -> None:
    process = FakeProcess(
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
                process_factory=FakeProcessFactory(process=process),
                group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append(
                    (process_group_id, sent_signal)
                ),
            ),
        )

    assert sent_signals == [
        (TEST_PID, signal.SIGTERM),
        (TEST_PID, signal.SIGKILL),
    ]
    assert process.communicate_calls == [1.0, 0.5, 0.5]
    assert exc_info.value.stdout == "after kill"


def test_runner_preserves_final_partial_output_when_process_survives_force_kill() -> None:
    process = FakeProcess(
        outcomes=[
            subprocess.TimeoutExpired(cmd=["tool"], timeout=1.0),
            subprocess.TimeoutExpired(cmd=["tool"], timeout=0.5),
            subprocess.TimeoutExpired(cmd=["tool"], timeout=0.5, output="partial", stderr="diagnostic"),
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
                process_factory=FakeProcessFactory(process=process),
                group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append(
                    (process_group_id, sent_signal)
                ),
            ),
        )

    assert sent_signals == [
        (TEST_PID, signal.SIGTERM),
        (TEST_PID, signal.SIGKILL),
    ]
    assert process.communicate_calls == [1.0, 0.5, 0.5]
    assert exc_info.value.stdout == "partial"
    assert exc_info.value.stderr == "diagnostic"


def test_runner_ignores_already_exited_process_group_on_timeout() -> None:
    process = FakeProcess(
        outcomes=[
            subprocess.TimeoutExpired(cmd=["tool"], timeout=1.0),
            ("", ""),
        ]
    )

    with pytest.raises(subprocess.TimeoutExpired):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(
                process_factory=FakeProcessFactory(process=process),
                group_signal_sender=_raise_process_lookup_error,
            ),
        )

    assert process.communicate_calls == [1.0, 2.0]


def test_runner_cleans_up_process_group_when_wait_is_interrupted() -> None:
    process = FakeProcess(outcomes=[KeyboardInterrupt(), ("", "")])
    sent_signals: list[tuple[int, signal.Signals]] = []

    with pytest.raises(KeyboardInterrupt):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1.0,
            settings=ProcessGroupCommandSettings(
                termination_grace_seconds=0.5,
                process_factory=FakeProcessFactory(process=process),
                group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append(
                    (process_group_id, sent_signal)
                ),
            ),
        )

    assert sent_signals == [(TEST_PID, signal.SIGTERM)]
    assert process.communicate_calls == [1.0, 0.5]


def test_runner_rejects_non_positive_timeouts() -> None:
    process = FakeProcess(outcomes=[])

    with pytest.raises(ValueError, match="timeout_seconds"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=0,
            settings=ProcessGroupCommandSettings(process_factory=FakeProcessFactory(process)),
        )

    with pytest.raises(ValueError, match="termination_grace_seconds"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1,
            settings=ProcessGroupCommandSettings(
                termination_grace_seconds=0,
                process_factory=FakeProcessFactory(process),
            ),
        )


@pytest.mark.parametrize("timeout_seconds", [math.inf, math.nan])
def test_runner_rejects_non_finite_timeouts(timeout_seconds: float) -> None:
    process = FakeProcess(outcomes=[])

    with pytest.raises(ValueError, match="timeout_seconds"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=timeout_seconds,
            settings=ProcessGroupCommandSettings(process_factory=FakeProcessFactory(process)),
        )


@pytest.mark.parametrize(
    ("argv", "expected_error", "message"),
    [
        ((), ValueError, "executable"),
        ("tool", TypeError, "sequence"),
        (("",), ValueError, "executable"),
        (("tool", "bad\x00arg"), ValueError, "NUL"),
        (("tool", 1), TypeError, r"argv\[1\]"),
    ],
)
def test_runner_rejects_malformed_argv_before_spawn(
    argv: object,
    expected_error: type[Exception],
    message: str,
) -> None:
    process = FakeProcess(outcomes=[])
    factory = FakeProcessFactory(process)

    with pytest.raises(expected_error, match=message):
        run_process_group_command(
            cast("Sequence[str]", argv),
            cwd=None,
            timeout_seconds=1,
            settings=ProcessGroupCommandSettings(process_factory=factory),
        )

    assert factory.calls == []


def test_runner_rejects_started_process_without_positive_pid() -> None:
    process = FakeProcess(outcomes=[], pid=0)

    with pytest.raises(RuntimeError, match="pid"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1,
            settings=ProcessGroupCommandSettings(process_factory=FakeProcessFactory(process)),
        )


def test_runner_rejects_completed_process_without_return_code() -> None:
    process = FakeProcess(outcomes=[("ok", "")], returncode=None)

    with pytest.raises(RuntimeError, match="return code"):
        run_process_group_command(
            ("tool",),
            cwd=None,
            timeout_seconds=1,
            settings=ProcessGroupCommandSettings(process_factory=FakeProcessFactory(process)),
        )


def _raise_process_lookup_error(_process_group_id: int, _sent_signal: signal.Signals) -> None:
    raise ProcessLookupError
