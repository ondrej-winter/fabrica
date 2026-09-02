"""Tests for in-memory live interaction lifecycle management."""

import asyncio
from dataclasses import dataclass, field

import pytest

from fabrica.features.user_interaction.application.dtos import (
    AnswerSubmission,
    InteractionErrorCode,
    InteractionOwner,
    InteractionPublication,
    InteractionQuestion,
    InteractionResultStatus,
    QuestionId,
)
from fabrica.features.user_interaction.application.use_cases import InMemoryInteractionManager, InteractionManagerError


def test_manager_publishes_question_and_resolves_it_with_exact_answer() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        manager = InMemoryInteractionManager(transport)
        owner = InteractionOwner("owner_one")
        task = asyncio.create_task(manager.ask(owner, _question()))

        await transport.published.wait()
        publication = transport.publications[0]
        submitted = await manager.submit_answer(
            owner,
            AnswerSubmission(publication.question_id, "Use PostgreSQL\nfor production.", selected_option=None),
        )

        assert submitted == await task
        assert submitted.status is InteractionResultStatus.ANSWERED
        assert submitted.answer == "Use PostgreSQL\nfor production."
        assert submitted.selected_option is None

    asyncio.run(scenario())


def test_manager_allows_only_one_pending_question_per_owner() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        manager = InMemoryInteractionManager(transport)
        owner = InteractionOwner("owner_one")
        task = asyncio.create_task(manager.ask(owner, _question()))
        await transport.published.wait()

        with pytest.raises(InteractionManagerError) as error:
            await manager.ask(owner, _question())

        assert error.value.code is InteractionErrorCode.QUESTION_ALREADY_PENDING
        await manager.cancel_owner(owner)
        await task

    asyncio.run(scenario())


def test_manager_replays_first_terminal_result_for_duplicate_answer_or_cancellation() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        manager = InMemoryInteractionManager(transport)
        owner = InteractionOwner("owner_one")
        task = asyncio.create_task(manager.ask(owner, _question()))
        await transport.published.wait()
        question_id = transport.publications[0].question_id

        first = await manager.submit_answer(owner, AnswerSubmission(question_id, "SQLite", selected_option=1))
        duplicate = await manager.submit_answer(owner, AnswerSubmission(question_id, "PostgreSQL", selected_option=0))
        cancelled = await manager.cancel(owner, question_id.value)

        assert await task == first
        assert duplicate == first
        assert cancelled == first

    asyncio.run(scenario())


def test_manager_rejects_unknown_or_wrong_owner_without_disclosure() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        manager = InMemoryInteractionManager(transport)
        owner = InteractionOwner("owner_one")
        other_owner = InteractionOwner("owner_two")
        task = asyncio.create_task(manager.ask(owner, _question()))
        await transport.published.wait()
        question_id = transport.publications[0].question_id

        with pytest.raises(InteractionManagerError) as wrong_owner:
            await manager.submit_answer(other_owner, AnswerSubmission(question_id, "SQLite", selected_option=1))
        with pytest.raises(InteractionManagerError) as unknown:
            await manager.cancel(other_owner, "q_unknown")

        assert wrong_owner.value.code is InteractionErrorCode.INTERACTION_NOT_FOUND
        assert unknown.value.code is InteractionErrorCode.INTERACTION_NOT_FOUND
        await manager.cancel_owner(owner)
        await task

    asyncio.run(scenario())


def test_manager_keeps_question_pending_when_empty_answer_cannot_be_constructed() -> None:
    with pytest.raises(ValueError, match="non-whitespace"):
        AnswerSubmission(_question_id(), " ")


def test_manager_rejects_out_of_range_selected_option_without_resolving_question() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        manager = InMemoryInteractionManager(transport)
        owner = InteractionOwner("owner_one")
        task = asyncio.create_task(manager.ask(owner, _question()))
        await transport.published.wait()
        question_id = transport.publications[0].question_id

        with pytest.raises(InteractionManagerError) as error:
            await manager.submit_answer(owner, AnswerSubmission(question_id, "custom", selected_option=2))

        assert error.value.code is InteractionErrorCode.INVALID_INPUT
        assert not task.done()
        await manager.cancel_owner(owner)
        assert (await task).status is InteractionResultStatus.CANCELLED

    asyncio.run(scenario())


def test_manager_rejects_selected_option_that_does_not_match_answer_without_resolving_question() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        manager = InMemoryInteractionManager(transport)
        owner = InteractionOwner("owner_one")
        task = asyncio.create_task(manager.ask(owner, _question()))
        await transport.published.wait()
        question_id = transport.publications[0].question_id

        with pytest.raises(InteractionManagerError) as error:
            await manager.submit_answer(owner, AnswerSubmission(question_id, "SQLite", selected_option=0))

        assert error.value.code is InteractionErrorCode.INVALID_INPUT
        assert not task.done()
        await manager.cancel_owner(owner)
        await task

    asyncio.run(scenario())


def test_manager_removes_pending_record_after_definitive_publication_failure() -> None:
    async def scenario() -> None:
        manager = InMemoryInteractionManager(_FailingTransport())
        owner = InteractionOwner("owner_one")

        with pytest.raises(InteractionManagerError) as error:
            await manager.ask(owner, _question())

        assert error.value.code is InteractionErrorCode.INTERACTION_PUBLISH_FAILED
        replacement_transport = _FakeTransport()
        manager.transport = replacement_transport
        task = asyncio.create_task(manager.ask(owner, _question()))
        await replacement_transport.published.wait()
        await manager.cancel_owner(owner)
        await task

    asyncio.run(scenario())


def test_release_owner_cancels_waiter_and_removes_retained_result() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        manager = InMemoryInteractionManager(transport)
        owner = InteractionOwner("owner_one")
        task = asyncio.create_task(manager.ask(owner, _question()))
        await transport.published.wait()
        question_id = transport.publications[0].question_id

        await manager.release_owner(owner)

        assert (await task).status is InteractionResultStatus.CANCELLED
        with pytest.raises(InteractionManagerError) as error:
            await manager.cancel(owner, question_id.value)
        assert error.value.code is InteractionErrorCode.INTERACTION_NOT_FOUND

    asyncio.run(scenario())


def test_manager_task_cancellation_resolves_pending_question_and_allows_a_new_question() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        manager = InMemoryInteractionManager(transport)
        owner = InteractionOwner("owner_one")
        task = asyncio.create_task(manager.ask(owner, _question()))
        await transport.published.wait()
        cancelled_question_id = transport.publications[0].question_id

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        cancelled = await manager.cancel(owner, cancelled_question_id.value)
        assert cancelled.status is InteractionResultStatus.CANCELLED

        transport.published.clear()
        replacement_task = asyncio.create_task(manager.ask(owner, _question()))
        await transport.published.wait()
        assert transport.publications[-1].question_id != cancelled_question_id
        await manager.cancel_owner(owner)

        assert (await replacement_task).status is InteractionResultStatus.CANCELLED

    asyncio.run(scenario())


@dataclass(slots=True)
class _FakeTransport:
    publications: list[InteractionPublication] = field(default_factory=list)
    published: asyncio.Event = field(default_factory=asyncio.Event)

    async def publish(self, publication: InteractionPublication) -> None:
        self.publications.append(publication)
        self.published.set()


@dataclass(frozen=True, slots=True)
class _FailingTransport:
    async def publish(self, publication: InteractionPublication) -> None:
        del publication
        message = "host disconnected"
        raise RuntimeError(message)


def _question() -> InteractionQuestion:
    return InteractionQuestion("Which database should this use?", ("PostgreSQL", "SQLite"))


def _question_id() -> QuestionId:
    return QuestionId("q_123")
