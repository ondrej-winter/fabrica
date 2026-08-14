"""Output formatting for developer-workflow CLI commands."""

from __future__ import annotations

from typing import TextIO

from fabrica.adapters.inbound.cli.text import format_metadata, write_line, write_text
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    CommitMessageWorkflowResult,
    ConfirmedCommitWorkflowResult,
    DeveloperWorkflowStatus,
)

EXIT_CODE_BY_DEVELOPER_WORKFLOW_STATUS: dict[DeveloperWorkflowStatus, int] = {
    DeveloperWorkflowStatus.SUCCESS: 0,
    DeveloperWorkflowStatus.CONFIGURATION_ERROR: 2,
    DeveloperWorkflowStatus.MODEL_ERROR: 3,
    DeveloperWorkflowStatus.UNSUPPORTED_CAPABILITY: 4,
    DeveloperWorkflowStatus.SAFETY_DENIED: 5,
}


def write_developer_workflow_result(result: CommitMessageWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a developer workflow result and return the matching process exit code."""
    output_text = result.output_text or _format_optional_recommendation(result.recommendation)
    if output_text:
        write_text(stdout, output_text)

    if not result.succeeded:
        write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            write_line(stderr, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_DEVELOPER_WORKFLOW_STATUS[result.status]


def write_confirmed_commit_result(result: ConfirmedCommitWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a confirmed commit workflow result and return the matching process exit code."""
    output_text = result.output_text or _format_optional_recommendation(result.recommendation)
    if output_text:
        write_text(stdout, output_text)

    if not result.succeeded:
        write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            write_line(stderr, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_DEVELOPER_WORKFLOW_STATUS[result.status]


def format_commit_message_recommendation(recommendation: CommitMessageRecommendation) -> str:
    """Format a recommendation with the stable terminal output labels."""
    return (
        f"Summary:\n{recommendation.summary}\n\n"
        f"Rationale:\n{recommendation.rationale}\n\n"
        f"Commit message:\n{recommendation.commit_message}"
    )


def _format_optional_recommendation(recommendation: CommitMessageRecommendation | None) -> str | None:
    if recommendation is None:
        return None
    return format_commit_message_recommendation(recommendation)


__all__ = [
    "format_commit_message_recommendation",
    "write_confirmed_commit_result",
    "write_developer_workflow_result",
]
