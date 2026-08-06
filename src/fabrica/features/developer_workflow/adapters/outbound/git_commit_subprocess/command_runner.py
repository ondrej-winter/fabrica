"""Subprocess runner boundary for approved git commit execution."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitCommitCommandResult:
    """Process-shaped result returned by the injectable git commit runner."""

    returncode: int
    stdout: str | bytes = ""
    stderr: str | bytes = ""


class GitCommitCommandRunner(Protocol):
    """Adapter-local subprocess boundary for deterministic commit tests."""

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommitCommandResult:
        """Run a git command and return captured output."""
        ...


def run_git_commit_command(
    argv: Sequence[str],
    *,
    cwd: Path | None,
    timeout_seconds: float,
) -> GitCommitCommandResult:
    """Run a git command for commit creation and return captured process output."""
    completed = subprocess.run(  # noqa: S603
        list(argv),
        check=False,
        capture_output=True,
        cwd=cwd,
        shell=False,
        timeout=timeout_seconds,
    )
    return GitCommitCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
