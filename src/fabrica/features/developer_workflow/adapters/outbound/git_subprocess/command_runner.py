"""Subprocess runner boundary for developer-workflow git commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from fabrica.adapters.outbound.process_group_subprocess import run_process_group_command

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
    result = run_process_group_command(
        argv,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )
    return GitCommandResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
