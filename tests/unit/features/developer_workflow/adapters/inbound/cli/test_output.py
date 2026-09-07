"""Tests for developer-workflow CLI output formatting."""

from io import StringIO

from fabrica.features.developer_workflow.adapters.inbound.cli.output import write_confirmed_commit_result
from fabrica.features.developer_workflow.application.dtos import (
    CommitMessageRecommendation,
    ConfirmedCommitWorkflowResult,
    DeveloperWorkflowStatus,
)


def test_write_confirmed_commit_result_formats_recommendation_when_output_is_absent() -> None:
    result = ConfirmedCommitWorkflowResult(
        status=DeveloperWorkflowStatus.SUCCESS,
        recommendation=CommitMessageRecommendation(
            summary="Add focused coverage",
            rationale="Exercises CLI rendering fallback",
            commit_message="test: cover confirmed commit output",
        ),
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = write_confirmed_commit_result(result, stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stdout.getvalue() == (
        "Summary:\nAdd focused coverage\n\n"
        "Rationale:\nExercises CLI rendering fallback\n\n"
        "Commit message:\ntest: cover confirmed commit output\n"
    )
    assert stderr.getvalue() == ""
