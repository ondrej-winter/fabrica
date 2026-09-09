"""Orchestrate bounded process-group command execution."""

from __future__ import annotations

import subprocess
from contextlib import suppress
from typing import TYPE_CHECKING

from fabrica.adapters.outbound.process_group_subprocess.cleanup import (
    process_group_id_from_started_process,
    terminate_process_group,
)
from fabrica.adapters.outbound.process_group_subprocess.contracts import (
    ProcessGroupCommandResult,
    ProcessGroupCommandSettings,
)
from fabrica.adapters.outbound.process_group_subprocess.validation import (
    ensure_positive_finite_duration,
    validated_argv,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def run_process_group_command(
    argv: Sequence[str],
    *,
    cwd: Path | None,
    timeout_seconds: float,
    settings: ProcessGroupCommandSettings | None = None,
) -> ProcessGroupCommandResult:
    """Run an explicit argv command and terminate its process group on timeout."""
    command_settings = settings or ProcessGroupCommandSettings()
    ensure_positive_finite_duration(timeout_seconds, field_name="timeout_seconds")
    ensure_positive_finite_duration(
        command_settings.termination_grace_seconds,
        field_name="termination_grace_seconds",
    )

    argv_list = validated_argv(argv)
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
    process_group_id = process_group_id_from_started_process(process)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as err:
        stdout, stderr = terminate_process_group(
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
        with suppress(BaseException):  # Cleanup must not replace the initial wait failure.
            terminate_process_group(
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
