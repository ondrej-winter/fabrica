"""In-memory lifecycle management for one live user interaction at a time."""

import asyncio
from dataclasses import dataclass, field

from fabrica.features.user_interaction.application.dtos import (
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
from fabrica.features.user_interaction.application.ports import InteractionTransport


class InteractionManagerError(Exception):
    """Stable application error returned when an interaction cannot proceed."""

    def __init__(self, code: InteractionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class _InteractionRecord:
    owner: InteractionOwner
    question: InteractionQuestion
    completion: asyncio.Future[InteractionResult]
    state: InteractionState = InteractionState.PENDING
    result: InteractionResult | None = None


@dataclass(slots=True)
class InMemoryInteractionManager:
    """Coordinate idempotent live questions with one pending item per owner."""

    transport: InteractionTransport
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _records: dict[QuestionId, _InteractionRecord] = field(default_factory=dict, init=False, repr=False)
    _pending_question_ids: dict[InteractionOwner, QuestionId] = field(default_factory=dict, init=False, repr=False)

    async def ask(self, owner: InteractionOwner, question: InteractionQuestion) -> InteractionResult:
        """Publish one question and wait without imposing a human-response timeout."""
        question_id = generate_question_id()
        loop = asyncio.get_running_loop()
        record = _InteractionRecord(owner=owner, question=question, completion=loop.create_future())
        async with self._lock:
            if owner in self._pending_question_ids:
                raise InteractionManagerError(
                    InteractionErrorCode.QUESTION_ALREADY_PENDING,
                    "an interaction is already pending for this owner",
                )
            self._records[question_id] = record
            self._pending_question_ids[owner] = question_id

        try:
            await self.transport.publish(InteractionPublication(question_id=question_id, question=question))
        except asyncio.CancelledError:
            await self._cancel_pending(question_id, owner)
            raise
        except Exception as err:
            await self._remove_pending_record(question_id, owner)
            raise InteractionManagerError(
                InteractionErrorCode.INTERACTION_PUBLISH_FAILED,
                "the interactive host could not publish the question",
            ) from err

        try:
            return await asyncio.shield(record.completion)
        except asyncio.CancelledError:
            await self._cancel_pending(question_id, owner)
            raise

    async def submit_answer(self, owner: InteractionOwner, submission: AnswerSubmission) -> InteractionResult:
        """Atomically commit the first authorized answer or replay its result."""
        async with self._lock:
            record = self._authorized_record(owner, submission.question_id)
            if record.result is not None:
                return record.result
            if submission.selected_option is not None and submission.selected_option >= len(record.question.options):
                raise InteractionManagerError(
                    InteractionErrorCode.INVALID_INPUT,
                    "selected_option does not identify a suggested option",
                )
            if (
                submission.selected_option is not None
                and submission.answer != record.question.options[submission.selected_option]
            ):
                raise InteractionManagerError(
                    InteractionErrorCode.INVALID_INPUT,
                    "selected_option must exactly match the submitted suggested answer",
                )
            result = InteractionResult(
                question_id=submission.question_id,
                status=InteractionResultStatus.ANSWERED,
                answer=submission.answer,
                selected_option=submission.selected_option,
            )
            self._resolve(record, result)
            return result

    async def cancel(self, owner: InteractionOwner, question_id: str) -> InteractionResult:
        """Atomically cancel one authorized interaction or replay its result."""
        try:
            identifier = QuestionId(question_id)
        except (TypeError, ValueError) as err:
            raise _not_found_error() from err
        async with self._lock:
            record = self._authorized_record(owner, identifier)
            if record.result is not None:
                return record.result
            result = InteractionResult(identifier, InteractionResultStatus.CANCELLED, None)
            self._resolve(record, result)
            return result

    async def cancel_owner(self, owner: InteractionOwner) -> None:
        """Resolve this owner's pending interaction as cancelled, if it has one."""
        async with self._lock:
            question_id = self._pending_question_ids.get(owner)
            if question_id is None:
                return
            record = self._records[question_id]
            self._resolve(record, InteractionResult(question_id, InteractionResultStatus.CANCELLED, None))

    async def release_owner(self, owner: InteractionOwner) -> None:
        """Cancel pending work and drop retained results for terminal owner cleanup."""
        async with self._lock:
            question_id = self._pending_question_ids.get(owner)
            if question_id is not None:
                record = self._records[question_id]
                self._resolve(record, InteractionResult(question_id, InteractionResultStatus.CANCELLED, None))
            for retained_question_id, record in tuple(self._records.items()):
                if (
                    record.owner == owner
                ):  # pragma: no cover - records are owner-scoped and only this owner is retained here.
                    del self._records[retained_question_id]

    async def _cancel_pending(self, question_id: QuestionId, owner: InteractionOwner) -> None:
        async with self._lock:
            record = self._records.get(question_id)
            if (
                record is not None and record.owner == owner and record.result is None
            ):  # pragma: no cover - cancellation cleanup only races terminal resolution.
                self._resolve(record, InteractionResult(question_id, InteractionResultStatus.CANCELLED, None))

    async def _remove_pending_record(self, question_id: QuestionId, owner: InteractionOwner) -> None:
        async with self._lock:
            record = self._records.get(question_id)
            if (
                record is not None and record.owner == owner and record.result is None
            ):  # pragma: no cover - publication cleanup only runs before any terminal resolution.
                del self._records[question_id]
                self._pending_question_ids.pop(owner, None)
                record.completion.cancel()

    def _authorized_record(self, owner: InteractionOwner, question_id: QuestionId) -> _InteractionRecord:
        record = self._records.get(question_id)
        if record is None or record.owner != owner:
            raise _not_found_error()
        return record

    def _resolve(self, record: _InteractionRecord, result: InteractionResult) -> None:
        record.state = (
            InteractionState.ANSWERED
            if result.status is InteractionResultStatus.ANSWERED
            else InteractionState.CANCELLED
        )
        record.result = result
        self._pending_question_ids.pop(record.owner, None)
        if (
            not record.completion.done()
        ):  # pragma: no cover - lock plus record.result make terminal completion single-assignment.
            record.completion.set_result(result)


def _not_found_error() -> InteractionManagerError:
    return InteractionManagerError(InteractionErrorCode.INTERACTION_NOT_FOUND, "interaction was not found")
