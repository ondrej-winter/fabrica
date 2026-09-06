"""Tests for submit-and-exit completion runtime boundary contracts."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field

from fabrica.bootstrap.composition.completion_runtime import CompletionToolLoopRuntime
from fabrica.bootstrap.composition.tool_loop import ToolLoopRuntime
from fabrica.features.agent_runtime.application.dtos import (
    CompletionCommitResult,
    CompletionCommitStatus,
    CompletionOutcome,
    CompletionRecord,
    CompletionVerification,
    LocalAgentRunCommand,
    ToolAwareModelResponse,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolCancellationSignal,
    ToolDefinition,
    ToolLoopLimits,
    ToolLoopRunStatus,
)
from fabrica.features.agent_runtime.application.use_cases import RunToolLoop


@dataclass
class _TextModel:
    async def run_turn(
        self,
        command: LocalAgentRunCommand,
        available_tools: tuple[ToolDefinition, ...],
        tool_results: tuple[ToolCallResult, ...] = (),
        cancellation: ToolCancellationSignal | None = None,
    ) -> ToolAwareModelResponse:
        del command, available_tools, cancellation
        if tool_results:
            return ToolAwareModelResponse(output_text="not a completion")
        return ToolAwareModelResponse(tool_calls=(ToolCallRequest(call_id="call-1", tool_name="no_op"),))


@dataclass
class _ContextCapturingExecutor:
    contexts: list[dict[str, object]] = field(default_factory=list)

    async def execute_tool(
        self,
        request: ToolCallRequest,
        limits: ToolLoopLimits,
        cancellation: ToolCancellationSignal,
        opaque_context: Mapping[str, object] | None = None,
    ) -> ToolCallResult:
        del limits, cancellation
        self.contexts.append(dict(opaque_context or {}))
        return ToolCallResult(call_id=request.call_id, tool_name=request.tool_name, status=ToolCallResultStatus.SUCCESS)


@dataclass
class _CompletionStore:
    records: tuple[CompletionRecord, ...] = ()
    acknowledged_run_ids: list[str] = field(default_factory=list)

    async def commit_completion(
        self,
        run_id: str,
        record: CompletionRecord,
        cancellation: ToolCancellationSignal,
    ) -> CompletionCommitResult:
        del run_id, cancellation
        return CompletionCommitResult(status=CompletionCommitStatus.COMMITTED, record=record)

    async def list_unpresented(self) -> tuple[CompletionRecord, ...]:
        return self.records

    async def acknowledge_presented(self, run_id: str) -> bool:
        self.acknowledged_run_ids.append(run_id)
        return True


@dataclass
class _CompletionPresenter:
    records: list[CompletionRecord] = field(default_factory=list)

    async def present(self, record: CompletionRecord) -> None:
        self.records.append(record)


def test_completion_record_is_immutable_and_carries_canonical_terminal_fields() -> None:
    record = CompletionRecord(
        run_id="run-1",
        tool_call_id="call-1",
        payload_digest="sha256:" + "1" * 64,
        outcome=CompletionOutcome.COMPLETED,
        summary="Implemented the requested change.",
        verification=CompletionVerification.VERIFIED,
    )

    assert record.summary == "Implemented the requested change."
    assert record.outcome is CompletionOutcome.COMPLETED


def test_completion_tool_loop_run_generates_and_propagates_opaque_run_id() -> None:
    executor = _ContextCapturingExecutor()
    runtime = CompletionToolLoopRuntime(
        runtime=ToolLoopRuntime(runner=RunToolLoop(model=_TextModel(), tool_executor=executor), available_tools=()),
    )

    run = runtime.start_run()
    result = asyncio.run(run.run(LocalAgentRunCommand(prompt="Finish")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert run.run_id.startswith("run_")
    assert executor.contexts == [{"agent_runtime.run_id": run.run_id}]


def test_completion_tool_loop_run_presents_only_its_matching_committed_completion() -> None:
    executor = _ContextCapturingExecutor()
    store = _CompletionStore()
    presenter = _CompletionPresenter()
    runtime = CompletionToolLoopRuntime(
        runtime=ToolLoopRuntime(runner=RunToolLoop(model=_TextModel(), tool_executor=executor), available_tools=()),
        completion_store=store,
        completion_presenter=presenter,
    )
    run = runtime.start_run()
    other_record = _record(run_id="run-other")
    matching_record = _record(run_id=run.run_id)
    store.records = (other_record, matching_record)

    result = asyncio.run(run.run(LocalAgentRunCommand(prompt="Finish")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert presenter.records == [matching_record]
    assert store.acknowledged_run_ids == [run.run_id]


def test_completion_tool_loop_run_skips_presentation_when_no_matching_completion_exists() -> None:
    executor = _ContextCapturingExecutor()
    store = _CompletionStore(records=(_record(run_id="run-other"),))
    presenter = _CompletionPresenter()
    runtime = CompletionToolLoopRuntime(
        runtime=ToolLoopRuntime(runner=RunToolLoop(model=_TextModel(), tool_executor=executor), available_tools=()),
        completion_store=store,
        completion_presenter=presenter,
    )

    result = asyncio.run(runtime.start_run().run(LocalAgentRunCommand(prompt="Finish")))

    assert result.status is ToolLoopRunStatus.SUCCESS
    assert presenter.records == []
    assert store.acknowledged_run_ids == []


def test_completion_runtime_recovery_returns_empty_when_presentation_dependencies_are_absent() -> None:
    runtime = CompletionToolLoopRuntime(
        runtime=ToolLoopRuntime(
            runner=RunToolLoop(model=_TextModel(), tool_executor=_ContextCapturingExecutor()), available_tools=()
        ),
    )

    assert asyncio.run(runtime.recover_unpresented_completions()) == ()


def test_completion_runtime_recovery_presents_and_acknowledges_all_unpresented_records_in_order() -> None:
    first_record = _record(run_id="run-first")
    second_record = _record(run_id="run-second")
    store = _CompletionStore(records=(first_record, second_record))
    presenter = _CompletionPresenter()
    runtime = CompletionToolLoopRuntime(
        runtime=ToolLoopRuntime(
            runner=RunToolLoop(model=_TextModel(), tool_executor=_ContextCapturingExecutor()), available_tools=()
        ),
        completion_store=store,
        completion_presenter=presenter,
    )

    recovered = asyncio.run(runtime.recover_unpresented_completions())

    assert recovered == (first_record, second_record)
    assert presenter.records == [first_record, second_record]
    assert store.acknowledged_run_ids == ["run-first", "run-second"]


def _record(*, run_id: str) -> CompletionRecord:
    return CompletionRecord(
        run_id=run_id,
        tool_call_id="call-1",
        payload_digest="sha256:" + "1" * 64,
        outcome=CompletionOutcome.COMPLETED,
        summary="Implemented the requested change.",
        verification=CompletionVerification.VERIFIED,
    )
