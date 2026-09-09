"""Bounded process-group termination helpers."""

from __future__ import annotations

import signal
import subprocess
from typing import TYPE_CHECKING

from fabrica.adapters.outbound.process_group_subprocess.contracts import Process, ProcessOutput

if TYPE_CHECKING:
    from collections.abc import Callable


def process_group_id_from_started_process(process: Process) -> int:
    """Return the dedicated process-group ID for a started process."""
    if process.pid <= 0:
        msg = "process pid must be positive"
        raise RuntimeError(msg)
    return process.pid


def terminate_process_group(
    *,
    process: Process,
    process_group_id: int,
    termination_grace_seconds: float,
    group_signal_sender: Callable[[int, signal.Signals], None],
) -> tuple[ProcessOutput | None, ProcessOutput | None]:
    """Terminate a process group and collect any available output."""
    send_group_signal(group_signal_sender, process_group_id, signal.SIGTERM)
    try:
        return process.communicate(timeout=termination_grace_seconds)
    except subprocess.TimeoutExpired:
        send_group_signal(group_signal_sender, process_group_id, signal.SIGKILL)
        return bounded_final_communicate(process, timeout_seconds=termination_grace_seconds)


def bounded_final_communicate(
    process: Process,
    *,
    timeout_seconds: float,
) -> tuple[ProcessOutput | None, ProcessOutput | None]:
    """Wait once more after SIGKILL without allowing cleanup to block forever."""
    try:
        return process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as err:
        return err.output, err.stderr


def send_group_signal(
    group_signal_sender: Callable[[int, signal.Signals], None],
    process_group_id: int,
    sent_signal: signal.Signals,
) -> None:
    """Send a signal unless the process group has already exited."""
    try:
        group_signal_sender(process_group_id, sent_signal)
    except ProcessLookupError:
        return
