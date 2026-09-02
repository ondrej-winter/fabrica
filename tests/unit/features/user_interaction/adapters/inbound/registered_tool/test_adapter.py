"""Tests for the model-facing ask-question registered-tool adapter."""

import asyncio
import json
from collections.abc import Coroutine, Mapping
from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolBatchPolicy,
    ToolExecutionContext,
    ToolOutcomeStatus,
    ToolTextContent,
    canonical_tool_arguments_digest,
)
from fabrica.features.user_interaction.adapters.inbound.registered_tool import (
    ASK_QUESTION_TOOL_DEFINITION,
    INTERACTION_OWNER_CONTEXT_KEY,
    AskQuestionRegisteredToolAdapter,
)
from fabrica.features.user_interaction.application.dtos import (
    AnswerSubmission,
    InteractionErrorCode,
    InteractionOwner,
    InteractionQuestion,
    InteractionResult,
    InteractionResultStatus,
    QuestionId,
)
from fabrica.features.user_interaction.application.use_cases import InteractionManagerError


def test_ask_question_definition_uses_the_canonical_schema_and_solo_batch_policy() -> None:
    definition = ASK_QUESTION_TOOL_DEFINITION

    assert definition.name == "ask_question"
    assert definition.batch_policy is ToolBatchPolicy.REQUIRE_SOLO
    assert definition.argument_schema["required"] == ("question", "options")
    assert definition.argument_schema["additionalProperties"] is False


def test_ask_question_returns_the_authoritative_free_text_result_once() -> None:
    result = InteractionResult(QuestionId("q_123"), InteractionResultStatus.ANSWERED, "Use SQLite for tests.")
    manager = _FakeInteractionManager(result=result)
    arguments = {"question": "Which database?", "options": ("PostgreSQL", "SQLite")}

    outcome = _run(AskQuestionRegisteredToolAdapter(manager).handle(arguments, _context(arguments)))

    assert manager.calls == [
        (InteractionOwner("owner_123"), InteractionQuestion("Which database?", ("PostgreSQL", "SQLite")))
    ]
    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert _payload(outcome) == {
        "answer": "Use SQLite for tests.",
        "question_id": "q_123",
        "selected_option": None,
        "status": "answered",
    }


def test_ask_question_preserves_the_selected_option_and_cancellation_results() -> None:
    arguments = {"question": "Which database?", "options": ("PostgreSQL", "SQLite")}
    selected = InteractionResult(QuestionId("q_123"), InteractionResultStatus.ANSWERED, "SQLite", 1)
    cancelled = InteractionResult(QuestionId("q_456"), InteractionResultStatus.CANCELLED, None)

    selected_outcome = _run(
        AskQuestionRegisteredToolAdapter(_FakeInteractionManager(selected)).handle(arguments, _context(arguments))
    )
    cancelled_outcome = _run(
        AskQuestionRegisteredToolAdapter(_FakeInteractionManager(cancelled)).handle(arguments, _context(arguments))
    )

    assert _payload(selected_outcome)["selected_option"] == 1
    assert _payload(cancelled_outcome) == {
        "answer": None,
        "question_id": "q_456",
        "selected_option": None,
        "status": "cancelled",
    }


def test_ask_question_fails_closed_without_an_opaque_interaction_owner() -> None:
    manager = _FakeInteractionManager(
        InteractionResult(QuestionId("q_123"), InteractionResultStatus.ANSWERED, "ignored")
    )
    arguments = {"question": "Which database?", "options": ("PostgreSQL", "SQLite")}

    outcome = _run(AskQuestionRegisteredToolAdapter(manager).handle(arguments, _context(arguments, interactive=False)))

    assert manager.calls == []
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "SESSION_NOT_INTERACTIVE"


def test_ask_question_rejects_invalid_arguments_without_asking() -> None:
    manager = _FakeInteractionManager(
        InteractionResult(QuestionId("q_123"), InteractionResultStatus.ANSWERED, "ignored")
    )
    arguments = {"question": "Which database?", "options": ("SQLite",)}

    outcome = _run(AskQuestionRegisteredToolAdapter(manager).handle(arguments, _context(arguments)))

    assert manager.calls == []
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_INPUT"


@pytest.mark.parametrize(
    "arguments",
    [
        {"question": "Which database?"},
        {"question": 42, "options": ("PostgreSQL", "SQLite")},
        {"question": "Which database?", "options": "PostgreSQL"},
        {"question": "Which database?", "options": ("PostgreSQL", 42)},
    ],
)
def test_ask_question_rejects_malformed_arguments_without_asking(
    arguments: Mapping[str, ToolArgumentValue],
) -> None:
    manager = _FakeInteractionManager(
        InteractionResult(QuestionId("q_123"), InteractionResultStatus.ANSWERED, "ignored")
    )

    outcome = _run(AskQuestionRegisteredToolAdapter(manager).handle(arguments, _context(arguments)))

    assert manager.calls == []
    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "INVALID_INPUT"


def test_ask_question_maps_interaction_manager_errors_to_stable_rejections() -> None:
    arguments = {"question": "Which database?", "options": ("PostgreSQL", "SQLite")}
    manager = _FailingInteractionManager()

    outcome = _run(AskQuestionRegisteredToolAdapter(manager).handle(arguments, _context(arguments)))

    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code == "QUESTION_ALREADY_PENDING"


@dataclass(slots=True)
class _FakeInteractionManager:
    result: InteractionResult
    calls: list[tuple[InteractionOwner, InteractionQuestion]] = field(default_factory=list)

    async def ask(self, owner: InteractionOwner, question: InteractionQuestion) -> InteractionResult:
        self.calls.append((owner, question))
        return self.result

    async def submit_answer(self, owner: InteractionOwner, submission: AnswerSubmission) -> InteractionResult:
        del owner, submission
        return self.result

    async def cancel(self, owner: InteractionOwner, question_id: str) -> InteractionResult:
        del owner, question_id
        return self.result

    async def cancel_owner(self, owner: InteractionOwner) -> None:
        del owner

    async def release_owner(self, owner: InteractionOwner) -> None:
        del owner


@dataclass(frozen=True, slots=True)
class _FailingInteractionManager:
    async def ask(self, owner: InteractionOwner, question: InteractionQuestion) -> InteractionResult:
        del owner, question
        raise InteractionManagerError(InteractionErrorCode.QUESTION_ALREADY_PENDING, "question already pending")

    async def submit_answer(self, owner: InteractionOwner, submission: AnswerSubmission) -> InteractionResult:
        del owner, submission
        raise AssertionError

    async def cancel(self, owner: InteractionOwner, question_id: str) -> InteractionResult:
        del owner, question_id
        raise AssertionError

    async def cancel_owner(self, owner: InteractionOwner) -> None:
        del owner

    async def release_owner(self, owner: InteractionOwner) -> None:
        del owner


@dataclass(frozen=True, slots=True)
class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        await asyncio.Event().wait()


def _context(arguments: Mapping[str, ToolArgumentValue], *, interactive: bool = True) -> ToolExecutionContext:
    opaque_values = {INTERACTION_OWNER_CONTEXT_KEY: InteractionOwner("owner_123")} if interactive else {}
    return ToolExecutionContext(
        call_id="call-1",
        argument_digest=canonical_tool_arguments_digest(arguments),
        cancellation=_NeverCancelled(),
        opaque_values=opaque_values,
    )


def _payload(outcome: RegisteredToolOutcome) -> dict[str, object]:
    content = outcome.content
    assert len(content) == 1
    assert isinstance(content[0], ToolTextContent)
    return json.loads(content[0].text)


def _run(coroutine: Coroutine[object, object, RegisteredToolOutcome]) -> RegisteredToolOutcome:
    return asyncio.run(coroutine)
