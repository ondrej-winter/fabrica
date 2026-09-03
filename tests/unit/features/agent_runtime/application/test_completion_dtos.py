"""Tests for submit-and-exit completion DTO and schema contracts."""

from dataclasses import FrozenInstanceError, fields
from typing import cast

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    MAX_COMPLETION_SUMMARY_CHARS,
    SUBMIT_AND_EXIT_TOOL_DEFINITION,
    SUBMIT_AND_EXIT_TOOL_NAME,
    CompletionOutcome,
    CompletionSubmission,
    CompletionVerification,
    ToolArgumentSchemaValue,
    ToolBatchPolicy,
)


def test_submit_and_exit_definition_matches_the_canonical_model_facing_contract() -> None:
    definition = SUBMIT_AND_EXIT_TOOL_DEFINITION
    properties = cast("dict[str, ToolArgumentSchemaValue]", definition.argument_schema["properties"])
    outcome = cast("dict[str, ToolArgumentSchemaValue]", properties["outcome"])
    summary = cast("dict[str, ToolArgumentSchemaValue]", properties["summary"])
    verification = cast("dict[str, ToolArgumentSchemaValue]", properties["verification"])

    assert definition.name == SUBMIT_AND_EXIT_TOOL_NAME
    assert definition.batch_policy is ToolBatchPolicy.REQUIRE_SOLO
    assert definition.argument_schema["type"] == "object"
    assert definition.argument_schema["required"] == ("outcome", "summary", "verification")
    assert definition.argument_schema["additionalProperties"] is False
    assert outcome == {"type": "string", "enum": ("completed", "partial", "blocked")}
    assert summary == {"type": "string", "minLength": 1, "maxLength": MAX_COMPLETION_SUMMARY_CHARS}
    assert verification == {"type": "string", "enum": ("verified", "not_verified", "not_applicable")}


@pytest.mark.parametrize("outcome", tuple(CompletionOutcome))
@pytest.mark.parametrize("verification", tuple(CompletionVerification))
def test_completion_submission_accepts_every_independent_outcome_and_verification_combination(
    outcome: CompletionOutcome,
    verification: CompletionVerification,
) -> None:
    submission = CompletionSubmission(
        outcome=outcome,
        summary="No changes needed.",
        verification=verification,
    )

    assert submission.outcome is outcome
    assert submission.verification is verification


@pytest.mark.parametrize(
    ("outcome", "summary", "verification", "error_type", "error_message"),
    [
        (
            cast("CompletionOutcome", "unknown"),
            "Completed work.",
            CompletionVerification.VERIFIED,
            TypeError,
            "outcome",
        ),
        (CompletionOutcome.COMPLETED, "", CompletionVerification.VERIFIED, ValueError, "summary"),
        (
            CompletionOutcome.COMPLETED,
            "x" * (MAX_COMPLETION_SUMMARY_CHARS + 1),
            CompletionVerification.VERIFIED,
            ValueError,
            "summary",
        ),
        (CompletionOutcome.COMPLETED, cast("str", 42), CompletionVerification.VERIFIED, ValueError, "summary"),
        (
            CompletionOutcome.COMPLETED,
            "Completed work.",
            cast("CompletionVerification", "unknown"),
            TypeError,
            "verification",
        ),
    ],
)
def test_completion_submission_rejects_invalid_model_facing_field_values(
    outcome: CompletionOutcome,
    summary: str,
    verification: CompletionVerification,
    error_type: type[Exception],
    error_message: str,
) -> None:
    with pytest.raises(error_type, match=error_message):
        CompletionSubmission(outcome=outcome, summary=summary, verification=verification)


def test_completion_submission_is_immutable() -> None:
    field_name = next(field.name for field in fields(CompletionSubmission) if field.name == "summary")
    submission = CompletionSubmission(
        outcome=CompletionOutcome.COMPLETED,
        summary="Completed work.",
        verification=CompletionVerification.VERIFIED,
    )

    with pytest.raises(FrozenInstanceError):
        setattr(submission, field_name, "Changed")
