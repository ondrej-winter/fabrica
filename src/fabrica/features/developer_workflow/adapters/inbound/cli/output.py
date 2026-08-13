"""Output formatting for developer-workflow CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    CommitMessageWorkflowResult,
    ConfirmedCommitWorkflowResult,
    DeveloperWorkflowStatus,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

EXIT_CODE_BY_DEVELOPER_WORKFLOW_STATUS: dict[DeveloperWorkflowStatus, int] = {
    DeveloperWorkflowStatus.SUCCESS: 0,
    DeveloperWorkflowStatus.CONFIGURATION_ERROR: 2,
    DeveloperWorkflowStatus.MODEL_ERROR: 3,
    DeveloperWorkflowStatus.UNSUPPORTED_CAPABILITY: 4,
    DeveloperWorkflowStatus.SAFETY_DENIED: 5,
}


MAX_OUTPUT_LINE_CHARS = 4_000


def write_developer_workflow_result(result: CommitMessageWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a developer workflow result and return the matching process exit code."""
    output_text = result.output_text or _format_optional_recommendation(result.recommendation)
    if output_text:
        _write_line(stdout, output_text)

    if not result.succeeded:
        _write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = _format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            _write_line(stderr, f"observation: {observation.message}{suffix}")

    return EXIT_CODE_BY_DEVELOPER_WORKFLOW_STATUS[result.status]


def write_confirmed_commit_result(result: ConfirmedCommitWorkflowResult, *, stdout: TextIO, stderr: TextIO) -> int:
    """Write a confirmed commit workflow result and return the matching process exit code."""
    output_text = result.output_text or _format_optional_recommendation(result.recommendation)
    if output_text:
        _write_line(stdout, output_text)

    if not result.succeeded:
        _write_line(stderr, f"status: {result.status.value}")
        for observation in result.observations:
            metadata = _format_metadata(observation.metadata)
            suffix = f" {metadata}" if metadata else ""
            _write_line(stderr, f"observation: {observation.message}{suffix}")

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


def _write_line(stream: TextIO, text: str) -> None:
    bounded = _bound_text(text)
    stream.write(bounded)
    if not bounded.endswith("\n"):
        stream.write("\n")


def _format_metadata(metadata: Mapping[str, object]) -> str:
    if not metadata:
        return ""
    return " ".join(f"{key}={_bound_text(str(value))}" for key, value in sorted(metadata.items()))


def _bound_text(text: str) -> str:
    if len(text) <= MAX_OUTPUT_LINE_CHARS:
        return text
    return f"{text[:MAX_OUTPUT_LINE_CHARS]}...<truncated>"


__all__ = [
    "format_commit_message_recommendation",
    "write_confirmed_commit_result",
    "write_developer_workflow_result",
]
