"""Terminal transport that captures explicit answers to model questions."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TextIO

from fabrica.features.coding_agent_session.adapters.inbound.terminal.rendering import write_question
from fabrica.features.user_interaction.application.dtos import AnswerSubmission, InteractionPublication, QuestionId

type AnswerSubmissionSink = Callable[[AnswerSubmission], Awaitable[object]]
type QuestionCancellationSink = Callable[[QuestionId], Awaitable[object]]


@dataclass(frozen=True, slots=True)
class TerminalQuestionTransport:
    """Render a question and submit only an explicit terminal answer to its host."""

    stdin: TextIO
    stdout: TextIO
    submit_answer: AnswerSubmissionSink
    cancel_question: QuestionCancellationSink

    async def publish(self, publication: InteractionPublication) -> None:
        """Render and capture one answer, cancelling the pending question when absent."""
        write_question(self.stdout, publication.question.question, publication.question.options)
        self.stdout.write("Answer (or option number): ")
        self.stdout.flush()
        try:
            answer = self.stdin.readline()
        except KeyboardInterrupt:
            await self.cancel_question(publication.question_id)
            return
        if not answer:
            await self.cancel_question(publication.question_id)
            return
        normalized_answer = answer.strip()
        if not normalized_answer:
            await self.cancel_question(publication.question_id)
            return
        selected_option = _selected_option(normalized_answer, publication.question.options)
        await self.submit_answer(
            AnswerSubmission(
                question_id=publication.question_id,
                answer=publication.question.options[selected_option]
                if selected_option is not None
                else normalized_answer,
                selected_option=selected_option,
            )
        )


def _selected_option(answer: str, options: tuple[str, ...]) -> int | None:
    if not answer.isdecimal():
        return None
    index = int(answer) - 1
    return index if 0 <= index < len(options) else None
