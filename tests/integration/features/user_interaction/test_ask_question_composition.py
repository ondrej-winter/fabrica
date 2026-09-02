"""Integration tests for opt-in live user-interaction composition."""

import asyncio
import json
from dataclasses import dataclass, field

import pytest

from fabrica.bootstrap import create_interactive_tool_loop_runtime, create_tool_loop_runtime
from fabrica.features.agent_runtime.application.dtos import (
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCancellationSignal,
    ToolDefinition,
    ToolTextContent,
)
from fabrica.features.user_interaction.application.dtos import (
    AnswerSubmission,
    InteractionErrorCode,
    InteractionPublication,
)
from fabrica.features.user_interaction.application.use_cases import InteractionManagerError


@dataclass
class _QuestionModel:
    calls: list[tuple[LocalAgentRunCommand, tuple[ToolDefinition, ...], tuple[ToolCallResult, ...]]] = field(
        default_factory=list
    )

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        del cancellation
        self.calls.append((command, available_tools, tool_results))
        if not tool_results:
            return ToolAwareModelResponse(
                tool_calls=(
                    ToolCallRequest(
                        call_id="question-1",
                        tool_name="ask_question",
                        arguments={"question": "Which database?", "options": ("PostgreSQL", "SQLite")},
                    ),
                )
            )
        return ToolAwareModelResponse(output_text="question answered")


@dataclass
class _FakeTransport:
    publications: list[InteractionPublication] = field(default_factory=list)
    published: asyncio.Event = field(default_factory=asyncio.Event)

    async def publish(self, publication: InteractionPublication) -> None:
        self.publications.append(publication)
        self.published.set()


def test_interactive_runtime_publishes_question_and_resumes_with_structured_answer() -> None:
    async def scenario() -> None:
        model = _QuestionModel()
        transport = _FakeTransport()
        runtime = create_interactive_tool_loop_runtime(model=model, transport=transport)
        run = runtime.start_run()

        task = asyncio.create_task(run.run(LocalAgentRunCommand(prompt="Choose a database")))
        await transport.published.wait()
        publication = transport.publications[0]
        answer = await run.submit_answer(AnswerSubmission(publication.question_id, "PostgreSQL", selected_option=0))
        result = await task

        assert answer.question_id == publication.question_id
        assert result.succeeded is True
        assert result.output_text == "question answered"
        assert tuple(tool.name for tool in runtime.available_tools) == ("ask_question",)
        content = model.calls[1][2][0].content
        assert len(content) == 1
        assert isinstance(content[0], ToolTextContent)
        payload = json.loads(content[0].text)
        assert payload == {
            "answer": "PostgreSQL",
            "question_id": publication.question_id.value,
            "selected_option": 0,
            "status": "answered",
        }

    asyncio.run(scenario())


def test_headless_tool_loop_does_not_implicitly_expose_ask_question() -> None:
    runtime = create_tool_loop_runtime(model=_QuestionModel())

    assert runtime.available_tools == ()


def test_cancelled_interactive_run_releases_pending_question_before_reraising() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        run = create_interactive_tool_loop_runtime(model=_QuestionModel(), transport=transport).start_run()
        task = asyncio.create_task(run.run(LocalAgentRunCommand(prompt="Choose a database")))
        await transport.published.wait()
        publication = transport.publications[0]

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        with pytest.raises(InteractionManagerError) as error:
            await run.submit_answer(AnswerSubmission(publication.question_id, "PostgreSQL", selected_option=0))

        assert error.value.code is InteractionErrorCode.INTERACTION_NOT_FOUND

    asyncio.run(scenario())


def test_external_cancellation_resolves_pending_question_as_structured_cancellation() -> None:
    async def scenario() -> None:
        model = _QuestionModel()
        transport = _FakeTransport()
        signal = _CancellationSignal()
        runtime = create_interactive_tool_loop_runtime(model=model, transport=transport)

        task = asyncio.create_task(runtime.run(LocalAgentRunCommand(prompt="Choose a database"), cancellation=signal))
        await transport.published.wait()
        signal.cancel()
        result = await task

        assert result.succeeded is True
        content = model.calls[1][2][0].content
        assert len(content) == 1
        assert isinstance(content[0], ToolTextContent)
        assert json.loads(content[0].text)["status"] == "cancelled"

    asyncio.run(scenario())


@dataclass
class _CancellationSignal:
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait_until_cancelled(self) -> None:
        await self._event.wait()
