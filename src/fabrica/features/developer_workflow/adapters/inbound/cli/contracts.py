"""Contracts and injected dependencies for developer-workflow CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from fabrica.features.agent_runtime.application.dtos import LocalAgentRunResult
    from fabrica.features.developer_workflow.application.ports import (
        CommitMessageWorkflowRunner,
        ConfirmedCommitWorkflowRunner,
    )
    from fabrica.features.developer_workflow.application.use_cases import ConfirmedCommitWorkflowResult


class DeveloperWorkflowCliCommandOptions(Protocol):
    """Shared product CLI options consumed by developer-workflow command adapters."""

    @property
    def print_usage(self) -> bool:
        """Return whether model usage evidence should be printed."""

    @property
    def print_prices(self) -> bool:
        """Return whether model pricing evidence should be printed."""

    @property
    def verbose_diagnostics(self) -> bool:
        """Return whether additional safe diagnostics should be included."""


class RuntimeResultWriter(Protocol):
    """Writer for runtime-shaped developer workflow results."""

    def __call__(self, result: LocalAgentRunResult, *, stdout: TextIO, stderr: TextIO) -> int:
        """Write a runtime result and return a process exit code."""


class ConfirmedCommitResultWriter(Protocol):
    """Writer for confirmed commit workflow results."""

    def __call__(self, result: ConfirmedCommitWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
        """Write a confirmed commit workflow result and return a process exit code."""


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowCliDependencies:
    """Injected dependencies for developer-workflow CLI commands."""

    commit_message_workflow: CommitMessageWorkflowRunner | None = None
    confirmed_commit_workflow: ConfirmedCommitWorkflowRunner | None = None


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowCliStreams:
    """Normalized CLI input/output streams for developer-workflow commands."""

    stdin: TextIO
    stdout: TextIO
    stderr: TextIO


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowCliWriters:
    """Injected output writers for developer-workflow CLI commands."""

    evidence: EvidenceWriter
    runtime_result: RuntimeResultWriter
    confirmed_commit_result: ConfirmedCommitResultWriter


class EvidenceWriter(Protocol):
    """Protocol for writing requested model evidence after command output."""

    def __call__(
        self,
        result: LocalAgentRunResult | ConfirmedCommitWorkflowResult,
        *,
        global_options: DeveloperWorkflowCliCommandOptions,
        stdout: TextIO,
    ) -> None:
        """Write model evidence selected by global CLI options."""
