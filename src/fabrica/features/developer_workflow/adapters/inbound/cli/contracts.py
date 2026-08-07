"""Contracts and injected dependencies for developer-workflow CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TextIO

if TYPE_CHECKING:
    from fabrica.adapters.inbound.cli.options import CliGlobalOptions
    from fabrica.bootstrap import ConfirmedCommitWorkflowResult
    from fabrica.features.agent_runtime.application.dtos import LocalAgentRunResult
    from fabrica.features.developer_workflow.adapters.inbound.cli.command_models import (
        CliCommitCommand,
        CliCommitMessageCommand,
    )
    from fabrica.features.developer_workflow.application.dtos import CommitMessageRecommendation


class CommitMessageWorkflowRunner(Protocol):
    """Protocol for commit-message workflow execution consumed by the CLI adapter."""

    def run(self, command: CliCommitMessageCommand) -> LocalAgentRunResult:
        """Run selected-skill commit-message generation."""


class ConfirmedCommitWorkflowRunner(Protocol):
    """Protocol for interactive confirmed commit workflow execution."""

    def generate(self, command: CliCommitCommand) -> ConfirmedCommitWorkflowResult:
        """Generate a commit-message recommendation without creating a commit."""

    def commit(self, recommendation: CommitMessageRecommendation) -> ConfirmedCommitWorkflowResult:
        """Create a git commit from an approved recommendation."""


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


class EvidenceWriter(Protocol):
    """Protocol for writing requested model evidence after command output."""

    def __call__(
        self,
        result: LocalAgentRunResult | ConfirmedCommitWorkflowResult,
        *,
        global_options: CliGlobalOptions,
        stdout: TextIO,
    ) -> None:
        """Write model evidence selected by global CLI options."""
