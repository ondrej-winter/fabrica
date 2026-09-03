"""Integration tests for terminal completion runtime composition."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field

from fabrica.bootstrap.composition.completion_runtime import CompletionToolLoopRuntime
from fabrica.bootstrap.composition.tool_loop import ToolLoopRuntime
from fabrica.features.agent_runtime.adapters.inbound.registered_tool import create_submit_and_exit_registered_tool
from fabrica.features.agent_runtime.adapters.outbound.json_completion_store import JsonCompletionStore
from fabrica.features.agent_runtime.adapters.outbound.registered_tool import RegisteredToolExecutor
from fabrica.features.agent_runtime.application.dtos import (
    CompletionRecord,
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopRunStatus,
)
from fabrica.features.agent_runtime.application.use_cases import (
    InMemoryRunStateMachine,
    RunToolLoop,
    SubmitRunCompletion,
)
from fabrica.features.user_interaction.adapters.inbound.registered_tool import (
    INTERACTION_OWNER_CONTEXT_KEY,
    create_ask_question_registered_tool,
)
from fabrica.features.user_interaction.application.dtos import (
    AnswerSubmission,
    InteractionOwner,
    InteractionPublication,
)
from fabrica.features.user_interaction.application.use_cases import InMemoryInteractionManager

EXPECTED_MODEL_TURN_COUNT = 2


@dataclass
class _TerminalCompletionModel:
    calls: int = 0

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        del command, available_tools, tool_results, cancellation
        self.calls += 1
        if self.calls > 1:
            msg = "model must not be called after terminal completion"
            raise AssertionError(msg)
        return ToolAwareModelResponse(
            tool_calls=(
                ToolCallRequest(
                    call_id="completion-1",
                    tool_name="submit_and_exit",
                    arguments={
                        "outcome": "completed",
                        "summary": "Implemented the requested change and ran focused tests.",
                        "verification": "verified",
                    },
                ),
            )
        )


@dataclass
class _RecordingPresenter:
    records: list[CompletionRecord] = field(default_factory=list)

    async def present(self, record: CompletionRecord) -> None:
        self.records.append(record)


@dataclass
class _QuestionThenCompletionModel:
    calls: list[tuple[ToolCallResult, ...]] = field(default_factory=list)

    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        del command, available_tools, cancellation
        self.calls.append(tool_results)
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
        return ToolAwareModelResponse(
            tool_calls=(
                ToolCallRequest(
                    call_id="completion-1",
                    tool_name="submit_and_exit",
                    arguments={
                        "outcome": "completed",
                        "summary": "Selected PostgreSQL and completed the task.",
                        "verification": "not_applicable",
                    },
                ),
            )
        )


@dataclass
class _QuestionTransport:
    publications: list[InteractionPublication] = field(default_factory=list)
    published: asyncio.Event = field(default_factory=asyncio.Event)

    async def publish(self, publication: InteractionPublication) -> None:
        self.publications.append(publication)
        self.published.set()


def test_terminal_completion_commits_stops_and_presents_the_canonical_summary_once(tmp_path) -> None:
    model = _TerminalCompletionModel()
    presenter = _RecordingPresenter()
    store = JsonCompletionStore(tmp_path)
    executor = RegisteredToolExecutor(
        (create_submit_and_exit_registered_tool(SubmitRunCompletion(store, InMemoryRunStateMachine())),)
    )
    runtime = CompletionToolLoopRuntime(
        runtime=ToolLoopRuntime(
            runner=RunToolLoop(model=model, tool_executor=executor),
            available_tools=executor.tool_definitions,
        ),
        completion_store=store,
        completion_presenter=presenter,
    )

    run = runtime.start_run()
    result = asyncio.run(run.run(LocalAgentRunCommand(prompt="Complete the task")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert result.output_text is None
    assert model.calls == 1
    assert len(presenter.records) == 1
    assert presenter.records[0].run_id == run.run_id
    assert presenter.records[0].summary == "Implemented the requested change and ran focused tests."
    assert asyncio.run(JsonCompletionStore(tmp_path).list_unpresented()) == ()


def test_recovery_presents_a_completion_committed_before_host_presentation(tmp_path) -> None:
    model = _TerminalCompletionModel()
    store = JsonCompletionStore(tmp_path)
    executor = RegisteredToolExecutor(
        (create_submit_and_exit_registered_tool(SubmitRunCompletion(store, InMemoryRunStateMachine())),)
    )
    first_runtime = CompletionToolLoopRuntime(
        runtime=ToolLoopRuntime(
            runner=RunToolLoop(model=model, tool_executor=executor),
            available_tools=executor.tool_definitions,
        )
    )
    run = first_runtime.start_run()

    result = asyncio.run(run.run(LocalAgentRunCommand(prompt="Complete the task")))
    recovery_presenter = _RecordingPresenter()
    recovery_runtime = CompletionToolLoopRuntime(
        runtime=first_runtime.runtime,
        completion_store=JsonCompletionStore(tmp_path),
        completion_presenter=recovery_presenter,
    )

    recovered = asyncio.run(recovery_runtime.recover_unpresented_completions())
    recovered_again = asyncio.run(recovery_runtime.recover_unpresented_completions())

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert recovered == tuple(recovery_presenter.records)
    assert len(recovery_presenter.records) == 1
    assert recovery_presenter.records[0].run_id == run.run_id
    assert recovered_again == ()


def test_interactive_question_answer_then_terminal_completion_releases_the_owner(tmp_path) -> None:
    async def scenario() -> None:
        model = _QuestionThenCompletionModel()
        transport = _QuestionTransport()
        manager = InMemoryInteractionManager(transport)
        store = JsonCompletionStore(tmp_path)
        executor = RegisteredToolExecutor(
            (
                create_ask_question_registered_tool(manager),
                create_submit_and_exit_registered_tool(SubmitRunCompletion(store, InMemoryRunStateMachine())),
            )
        )

        async def release_interaction_owner(opaque_context: Mapping[str, object]) -> None:
            owner = opaque_context.get(INTERACTION_OWNER_CONTEXT_KEY)
            if isinstance(owner, InteractionOwner):
                await manager.release_owner(owner)

        owner = InteractionOwner("owner-1")
        runtime = ToolLoopRuntime(
            runner=RunToolLoop(
                model=model,
                tool_executor=executor,
                terminal_hooks=(release_interaction_owner,),
            ),
            available_tools=executor.tool_definitions,
        )
        task = asyncio.create_task(
            runtime.run(
                LocalAgentRunCommand(prompt="Choose a database and complete the task"),
                opaque_tool_context={"agent_runtime.run_id": "run-1", INTERACTION_OWNER_CONTEXT_KEY: owner},
            )
        )
        await transport.published.wait()
        publication = transport.publications[0]
        await manager.submit_answer(owner, AnswerSubmission(publication.question_id, "PostgreSQL", selected_option=0))
        result = await task

        assert result.status is ToolLoopRunStatus.SUCCESS
        assert len(model.calls) == EXPECTED_MODEL_TURN_COUNT
        assert len(model.calls[1]) == 1
        assert model.calls[1][0].tool_name == "ask_question"
        assert len(await store.list_unpresented()) == 1
        await manager.release_owner(owner)

    asyncio.run(scenario())
