"""Contracts and injected dependencies for developer-workflow CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from fabrica.features.developer_workflow.application.dtos import (
        CommitMessageWorkflowResult,
        ConfirmedCommitWorkflowResult,
    )


class RuntimeResultWriter(Protocol):
    """Writer for runtime-shaped developer workflow results."""

    def __call__(self, result: CommitMessageWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
        """Write a runtime result and return a process exit code."""


class ConfirmedCommitResultWriter(Protocol):
    """Writer for confirmed commit workflow results."""

    def __call__(self, result: ConfirmedCommitWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
        """Write a confirmed commit workflow result and return a process exit code."""


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowCliOptions:
    """Product CLI option values consumed by developer-workflow commands."""

    print_usage: bool = False
    print_prices: bool = False


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowCliStreams:
    """Normalized CLI input/output streams for developer-workflow commands."""

    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


class EvidenceWriter(Protocol):
    """Protocol for writing requested model evidence after command output."""

    def __call__(
        self,
        result: CommitMessageWorkflowResult | ConfirmedCommitWorkflowResult,
        *,
        include_usage: bool,
        include_prices: bool,
        stdout: TextIO,
    ) -> None:
        """Write model evidence selected by global CLI options."""
