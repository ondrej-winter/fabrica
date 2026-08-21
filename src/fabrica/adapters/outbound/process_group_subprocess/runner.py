"""Run subprocess commands in dedicated process groups with bounded cleanup."""

from __future__ import annotations

import math
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
        stdin: int,
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
    stdin: int,
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
        stdin=stdin,
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
    _ensure_positive_finite_duration(timeout_seconds, field_name="timeout_seconds")
    _ensure_positive_finite_duration(
        command_settings.termination_grace_seconds,
        field_name="termination_grace_seconds",
    )

    argv_list = _validated_argv(argv)
    process = command_settings.process_factory(
        argv_list,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=command_settings.env,
        shell=False,
        text=command_settings.text,
        start_new_session=True,
    )
    process_group_id = _process_group_id_from_started_process(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as err:
        stdout, stderr = _terminate_process_group(
            process=process,
            process_group_id=process_group_id,
            termination_grace_seconds=command_settings.termination_grace_seconds,
            group_signal_sender=command_settings.group_signal_sender,
        )
        raise subprocess.TimeoutExpired(
            cmd=argv_list,
            timeout=timeout_seconds,
            output=stdout,
            stderr=stderr,
        ) from err
    except BaseException:
        _cleanup_process_group_after_wait_failure(
            process=process,
            process_group_id=process_group_id,
            termination_grace_seconds=command_settings.termination_grace_seconds,
            group_signal_sender=command_settings.group_signal_sender,
        )
        raise
    if process.returncode is None:
        msg = "process completed without a return code"
        raise RuntimeError(msg)
    return ProcessGroupCommandResult(
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _validated_argv(argv: Sequence[str]) -> list[str]:
    if isinstance(argv, str):
        msg = "argv must be a sequence of arguments, not a string"
        raise TypeError(msg)
    argv_list = list(argv)
    if not argv_list:
        msg = "argv must include an executable"
        raise ValueError(msg)
    for index, argument in enumerate(argv_list):
        if not isinstance(argument, str):
            msg = f"argv[{index}] must be a string"
            raise TypeError(msg)
        if "\x00" in argument:
            msg = f"argv[{index}] must not contain NUL bytes"
            raise ValueError(msg)
    if not argv_list[0]:
        msg = "argv executable must not be empty"
        raise ValueError(msg)
    return argv_list


def _ensure_positive_finite_duration(value: float, *, field_name: str) -> None:
    if value <= 0 or not math.isfinite(value):
        msg = f"{field_name} must be positive and finite"
        raise ValueError(msg)


def _process_group_id_from_started_process(process: _Process) -> int:
    if process.pid <= 0:
        msg = "process pid must be positive"
        raise RuntimeError(msg)
    return process.pid


def _terminate_process_group(
    *,
    process: _Process,
    process_group_id: int,
    termination_grace_seconds: float,
    group_signal_sender: Callable[[int, signal.Signals], None],
) -> tuple[ProcessOutput | None, ProcessOutput | None]:
    _send_group_signal(group_signal_sender, process_group_id, signal.SIGTERM)
    try:
        return process.communicate(timeout=termination_grace_seconds)
    except subprocess.TimeoutExpired:
        _send_group_signal(group_signal_sender, process_group_id, signal.SIGKILL)
        return _bounded_final_communicate(
            process,
            timeout_seconds=termination_grace_seconds,
        )


def _cleanup_process_group_after_wait_failure(
    *,
    process: _Process,
    process_group_id: int,
    termination_grace_seconds: float,
    group_signal_sender: Callable[[int, signal.Signals], None],
) -> None:
    try:
        _terminate_process_group(
            process=process,
            process_group_id=process_group_id,
            termination_grace_seconds=termination_grace_seconds,
            group_signal_sender=group_signal_sender,
        )
    except subprocess.TimeoutExpired:
        return


def _bounded_final_communicate(
    process: _Process,
    *,
    timeout_seconds: float,
) -> tuple[ProcessOutput | None, ProcessOutput | None]:
    try:
        return process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as err:
        return err.output, err.stderr


def _send_group_signal(
    group_signal_sender: Callable[[int, signal.Signals], None],
    process_group_id: int,
    sent_signal: signal.Signals,
) -> None:
    try:
        group_signal_sender(process_group_id, sent_signal)
    except ProcessLookupError:
        return
