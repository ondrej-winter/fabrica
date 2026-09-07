"""Tests for live user-interaction application DTO contracts."""

from collections.abc import Callable
from dataclasses import fields

import pytest

from fabrica.features.user_interaction.application.dtos import (
    MAX_OPTION_CHARS,
    MAX_QUESTION_CHARS,
    MAX_QUESTION_ID_CHARS,
    QUESTION_ID_PREFIX,
    AnswerSubmission,
    InteractionErrorCode,
    InteractionOwner,
    InteractionPublication,
    InteractionQuestion,
    InteractionResult,
    InteractionResultStatus,
    InteractionState,
    QuestionId,
    generate_question_id,
)


def test_interaction_question_accepts_focused_question_and_exact_unique_options() -> None:
    question = InteractionQuestion("Which database should this use?", ("PostgreSQL", "SQLite"))

    assert question.question == "Which database should this use?"
    assert question.options == ("PostgreSQL", "SQLite")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: InteractionQuestion(" ", ("PostgreSQL", "SQLite")),
        lambda: InteractionQuestion("question", ("only one",)),
        lambda: InteractionQuestion("question", ("a", "b", "c", "d", "e", "f")),
        lambda: InteractionQuestion("question", (" ", "SQLite")),
        lambda: InteractionQuestion("question", ("PostgreSQL", "PostgreSQL")),
        lambda: InteractionQuestion("q" * (MAX_QUESTION_CHARS + 1), ("PostgreSQL", "SQLite")),
        lambda: InteractionQuestion("question", ("a" * (MAX_OPTION_CHARS + 1), "SQLite")),
    ],
)
def test_interaction_question_rejects_invalid_version_one_inputs(factory: Callable[[], object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory()


def test_question_id_generation_and_validation_use_opaque_q_prefix() -> None:
    generated = generate_question_id()

    assert generated.value.startswith(QUESTION_ID_PREFIX)
    assert len(generated.value) <= MAX_QUESTION_ID_CHARS
    with pytest.raises(ValueError, match="start"):
        QuestionId("question-1")
    with pytest.raises(ValueError, match="safe length"):
        QuestionId(f"q_{'a' * MAX_QUESTION_ID_CHARS}")
    with pytest.raises(ValueError, match="opaque URL-safe"):
        QuestionId("q_")
    with pytest.raises(ValueError, match="opaque URL-safe"):
        QuestionId("q_é")


@pytest.mark.parametrize("value", ["", "é", "owner space"])
def test_interaction_owner_rejects_non_opaque_identifiers(value: str) -> None:
    with pytest.raises(ValueError, match="opaque identifier"):
        InteractionOwner(value)


def test_answer_submission_rejects_non_string_answer() -> None:
    with pytest.raises(TypeError, match="answer must be a string"):
        AnswerSubmission(QuestionId("q_123"), 42)  # ty: ignore[invalid-argument-type]


def test_answered_interaction_result_preserves_free_text_and_known_option_index() -> None:
    result = InteractionResult(
        question_id=QuestionId("q_123"),
        status=InteractionResultStatus.ANSWERED,
        answer="Use PostgreSQL, but SQLite is fine for tests.",
        selected_option=0,
    )

    assert result.answer == "Use PostgreSQL, but SQLite is fine for tests."
    assert result.selected_option == 0


@pytest.mark.parametrize(
    "factory",
    [
        lambda: InteractionResult(QuestionId("q_123"), InteractionResultStatus.ANSWERED, None),
        lambda: InteractionResult(QuestionId("q_123"), InteractionResultStatus.ANSWERED, " "),
        lambda: InteractionResult(QuestionId("q_123"), InteractionResultStatus.ANSWERED, "answer", selected_option=-1),
        lambda: InteractionResult(QuestionId("q_123"), InteractionResultStatus.CANCELLED, "answer"),
        lambda: InteractionResult(QuestionId("q_123"), InteractionResultStatus.CANCELLED, None, selected_option=0),
    ],
)
def test_interaction_result_rejects_invalid_terminal_state_combinations(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match=r"answer|selected_option"):
        factory()


def test_owner_is_distinct_from_question_id_and_absent_from_host_submission_and_result() -> None:
    owner = InteractionOwner("run_owner_123")
    question_id = QuestionId("q_123")
    publication = InteractionPublication(question_id, InteractionQuestion("Continue?", ("Yes", "No")))
    AnswerSubmission(question_id, "Yes", selected_option=0)
    InteractionResult(question_id, InteractionResultStatus.ANSWERED, "Yes", selected_option=0)

    assert owner != question_id
    assert publication.question_id == question_id
    assert "owner" not in {field.name for field in fields(AnswerSubmission)}
    assert "owner" not in {field.name for field in fields(InteractionResult)}


def test_stable_interaction_error_codes_and_states_are_available() -> None:
    assert {code.value for code in InteractionErrorCode} == {
        "INVALID_INPUT",
        "QUESTION_ALREADY_PENDING",
        "INTERACTION_PUBLISH_FAILED",
        "SESSION_NOT_INTERACTIVE",
        "INTERACTION_NOT_FOUND",
        "INTERNAL_INTERACTION_ERROR",
    }
    assert {state.value for state in InteractionState} == {"pending", "answered", "cancelled"}
