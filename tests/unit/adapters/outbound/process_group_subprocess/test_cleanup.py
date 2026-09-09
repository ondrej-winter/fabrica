"""Tests for bounded process-group cleanup."""

import signal
import subprocess
from dataclasses import dataclass, field

import pytest

from fabrica.adapters.outbound.process_group_subprocess.cleanup import (
    bounded_final_communicate,
    process_group_id_from_started_process,
    send_group_signal,
    terminate_process_group,
)

TEST_PID = 1234


@dataclass
class _FakeProcess:
    """Scripted subprocess-like object for cleanup tests."""

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


def test_process_group_id_uses_started_process_pid() -> None:
    assert process_group_id_from_started_process(_FakeProcess(outcomes=[])) == TEST_PID


def test_process_group_id_rejects_non_positive_pid() -> None:
    with pytest.raises(RuntimeError, match="pid"):
        process_group_id_from_started_process(_FakeProcess(outcomes=[], pid=0))


def test_terminate_process_group_sends_term_and_returns_reaped_output() -> None:
    process = _FakeProcess(outcomes=[("stdout", "stderr")])
    sent_signals: list[tuple[int, signal.Signals]] = []

    result = terminate_process_group(
        process=process,
        process_group_id=TEST_PID,
        termination_grace_seconds=0.5,
        group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append((process_group_id, sent_signal)),
    )

    assert result == ("stdout", "stderr")
    assert sent_signals == [(TEST_PID, signal.SIGTERM)]
    assert process.communicate_calls == [0.5]


def test_terminate_process_group_escalates_to_kill_and_preserves_final_timeout_output() -> None:
    process = _FakeProcess(
        outcomes=[
            subprocess.TimeoutExpired(cmd=["tool"], timeout=0.5),
            subprocess.TimeoutExpired(cmd=["tool"], timeout=0.5, output="partial", stderr="diagnostic"),
        ]
    )
    sent_signals: list[tuple[int, signal.Signals]] = []

    result = terminate_process_group(
        process=process,
        process_group_id=TEST_PID,
        termination_grace_seconds=0.5,
        group_signal_sender=lambda process_group_id, sent_signal: sent_signals.append((process_group_id, sent_signal)),
    )

    assert result == ("partial", "diagnostic")
    assert sent_signals == [(TEST_PID, signal.SIGTERM), (TEST_PID, signal.SIGKILL)]
    assert process.communicate_calls == [0.5, 0.5]


def test_bounded_final_communicate_returns_timeout_output() -> None:
    process = _FakeProcess(
        outcomes=[subprocess.TimeoutExpired(cmd=["tool"], timeout=0.25, output="partial", stderr="error")]
    )

    assert bounded_final_communicate(process, timeout_seconds=0.25) == ("partial", "error")


def test_send_group_signal_ignores_already_exited_process_group() -> None:
    def raise_process_lookup_error(_process_group_id: int, _sent_signal: signal.Signals) -> None:
        raise ProcessLookupError

    send_group_signal(raise_process_lookup_error, TEST_PID, signal.SIGTERM)
