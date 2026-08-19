"""Subprocess runner boundary for developer-workflow git commands."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitCommandResult:
    """Process-shaped result returned by the injectable git command runner."""

    returncode: int
    stdout: str | bytes = ""
    stderr: str | bytes = ""


class GitCommandRunner(Protocol):
    """Adapter-local subprocess boundary for deterministic tests."""

    def __call__(self, argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
        """Run a git command and return captured output."""
        ...


def run_git_command(argv: Sequence[str], *, cwd: Path | None, timeout_seconds: float) -> GitCommandResult:
    """Run a git command and return captured process output."""
    # Intentional adapter boundary: argv is constructed by Git command value objects, with no shell interpolation.
    completed = subprocess.run(  # noqa: S603
        list(argv),
        check=False,
        capture_output=True,
        cwd=cwd,
        shell=False,
        timeout=timeout_seconds,
    )
    return GitCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
