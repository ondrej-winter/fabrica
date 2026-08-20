"""Run subprocess commands in dedicated process groups with bounded cleanup."""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

DEFAULT_TERMINATION_GRACE_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class ProcessGroupCommandResult:
    """Captured result from a completed process-group command."""

    returncode: int
    stdout: str | bytes = ""
    stderr: str | bytes = ""


type ProcessOutput = str | bytes


class _Process(Protocol):
    pid: int
    returncode: int | None

    def communicate(
        self,
        input: bytes | str | None = None,  # noqa: A002 - matches subprocess.Popen.communicate.
        timeout: float | None = None,
    ) -> tuple[ProcessOutput, ProcessOutput]:
        """Wait for process completion and return captured stdout/stderr."""
        ...


class _ProcessFactory(Protocol):
    def __call__(  # noqa: PLR0913 - mirrors the subprocess.Popen keyword surface used by this adapter.
        self,
        argv: Sequence[str],
        *,
        stdout: int,
        stderr: int,
        cwd: Path | None,
        env: Mapping[str, str] | None,
        shell: bool,
        text: bool,
        start_new_session: bool,
    ) -> _Process:
        """Create a subprocess-like object."""
        ...


def _open_process(  # noqa: PLR0913 - mirrors the subprocess.Popen keyword surface used by this adapter.
    argv: Sequence[str],
    *,
    stdout: int,
    stderr: int,
    cwd: Path | None,
    env: Mapping[str, str] | None,
    shell: bool,
    text: bool,
    start_new_session: bool,
) -> _Process:
    # Intentional adapter boundary: callers provide explicit argv sequences and shell remains false.
    return subprocess.Popen(  # noqa: S603
        argv,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        env=env,
        shell=shell,
        text=text,
        start_new_session=start_new_session,
    )


@dataclass(frozen=True, slots=True)
class ProcessGroupCommandSettings:
    """Infrastructure settings for process-group command execution."""

    env: Mapping[str, str] | None = None
    text: bool = False
    termination_grace_seconds: float = DEFAULT_TERMINATION_GRACE_SECONDS
    process_factory: _ProcessFactory = _open_process
    process_group_id_loader: Callable[[int], int] = os.getpgid
    group_signal_sender: Callable[[int, signal.Signals], None] = os.killpg


def run_process_group_command(
    argv: Sequence[str],
    *,
    cwd: Path | None,
    timeout_seconds: float,
    settings: ProcessGroupCommandSettings | None = None,
) -> ProcessGroupCommandResult:
    """Run an explicit argv command and terminate its process group on timeout."""
    command_settings = settings or ProcessGroupCommandSettings()
    if timeout_seconds <= 0:
        msg = "timeout_seconds must be positive"
        raise ValueError(msg)
    if command_settings.termination_grace_seconds <= 0:
        msg = "termination_grace_seconds must be positive"
        raise ValueError(msg)

    argv_list = list(argv)
    process = command_settings.process_factory(
        argv_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=command_settings.env,
        shell=False,
        text=command_settings.text,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as err:
        stdout, stderr = _terminate_process_group(
            process,
            termination_grace_seconds=command_settings.termination_grace_seconds,
            process_group_id_loader=command_settings.process_group_id_loader,
            group_signal_sender=command_settings.group_signal_sender,
        )
        raise subprocess.TimeoutExpired(
            cmd=argv_list,
            timeout=timeout_seconds,
            output=stdout,
            stderr=stderr,
        ) from err
    return ProcessGroupCommandResult(
        returncode=process.returncode or 0,
        stdout=stdout,
        stderr=stderr,
    )


def _terminate_process_group(
    process: _Process,
    *,
    termination_grace_seconds: float,
    process_group_id_loader: Callable[[int], int],
    group_signal_sender: Callable[[int, signal.Signals], None],
) -> tuple[ProcessOutput, ProcessOutput]:
    process_group_id = process_group_id_loader(process.pid)
    _send_group_signal(group_signal_sender, process_group_id, signal.SIGTERM)
    try:
        return process.communicate(timeout=termination_grace_seconds)
    except subprocess.TimeoutExpired:
        _send_group_signal(group_signal_sender, process_group_id, signal.SIGKILL)
        return process.communicate()


def _send_group_signal(
    group_signal_sender: Callable[[int, signal.Signals], None],
    process_group_id: int,
    sent_signal: signal.Signals,
) -> None:
    try:
        group_signal_sender(process_group_id, sent_signal)
    except ProcessLookupError:
        return
