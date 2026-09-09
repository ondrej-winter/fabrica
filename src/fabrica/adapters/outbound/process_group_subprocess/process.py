"""Subprocess construction for process-group command execution."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from fabrica.adapters.outbound.process_group_subprocess.contracts import Process


def open_process(  # noqa: PLR0913 - mirrors the subprocess.Popen keyword surface used by this adapter.
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
    """Open an explicit argv command in a dedicated process group."""
    return cast(
        "Process",
        subprocess.Popen(  # noqa: S603
            argv,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
            env=env,
            shell=shell,
            text=text,
            start_new_session=start_new_session,
        ),
    )
