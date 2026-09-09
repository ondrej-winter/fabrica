"""Contracts and settings for process-group subprocess execution."""

from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from fabrica.adapters.outbound.process_group_subprocess.process import open_process

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

DEFAULT_TERMINATION_GRACE_SECONDS = 2.0

type ProcessOutput = str | bytes


@dataclass(frozen=True, slots=True)
class ProcessGroupCommandResult:
    """Captured result from a completed process-group command."""

    returncode: int
    stdout: ProcessOutput = ""
    stderr: ProcessOutput = ""


class Process(Protocol):
    """Minimal subprocess protocol used by the command runner."""

    pid: int
    returncode: int | None

    def communicate(
        self,
        input: bytes | str | None = None,  # noqa: A002 - matches subprocess.Popen.communicate.
        timeout: float | None = None,
    ) -> tuple[ProcessOutput, ProcessOutput]:
        """Wait for process completion and return captured stdout/stderr."""
        ...


class ProcessFactory(Protocol):
    """Create a subprocess-like object."""

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
    ) -> Process:
        """Create a subprocess-like object."""
        ...


@dataclass(frozen=True, slots=True)
class ProcessGroupCommandSettings:
    """Infrastructure settings for process-group command execution."""

    env: Mapping[str, str] | None = None
    text: bool = False
    termination_grace_seconds: float = DEFAULT_TERMINATION_GRACE_SECONDS
    process_factory: ProcessFactory = open_process
    group_signal_sender: Callable[[int, signal.Signals], None] = os.killpg
