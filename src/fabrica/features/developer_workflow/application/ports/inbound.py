"""Inbound application ports for developer workflow use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from fabrica.features.agent_runtime.application.dtos import LocalAgentRunResult
    from fabrica.features.developer_workflow.application.dtos import (
        CommitMessageRecommendation,
        GenerateCommitMessageCommand,
    )
    from fabrica.features.developer_workflow.application.use_cases import ConfirmedCommitWorkflowResult


class CommitMessageWorkflowRunner(Protocol):
    """Inbound port for selected-skill commit-message generation."""

    def run(self, command: GenerateCommitMessageCommand) -> LocalAgentRunResult:
        """Run selected-skill commit-message generation."""


class ConfirmedCommitWorkflowRunner(Protocol):
    """Inbound port for externally approved git commit workflows."""

    def generate(self, command: GenerateCommitMessageCommand) -> ConfirmedCommitWorkflowResult:
        """Generate a commit-message recommendation without creating a commit."""

    def commit(self, recommendation: CommitMessageRecommendation) -> ConfirmedCommitWorkflowResult:
        """Create a git commit from an approved recommendation."""
