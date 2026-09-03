"""Tests for the model-facing submit-and-exit registered-tool adapter."""

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from fabrica.features.agent_runtime.adapters.inbound.registered_tool import SubmitAndExitRegisteredToolAdapter
from fabrica.features.agent_runtime.application.dtos import (
    RUN_ID_CONTEXT_KEY,
    CompletionCommitResult,
    CompletionCommitStatus,
    CompletionErrorCode,
    CompletionRecord,
    CompletionRunState,
    RegisteredToolOutcome,
    ToolArgumentValue,
    ToolExecutionContext,
    ToolExecutionRuntimeDisposition,
    ToolOutcomeStatus,
    ToolTextContent,
    canonical_tool_arguments_digest,
)
from fabrica.features.agent_runtime.application.use_cases import InMemoryRunStateMachine, SubmitRunCompletion


def test_submit_and_exit_maps_arguments_and_opaque_context_to_completion_submission() -> None:
    arguments = {
        "outcome": "completed",
        "summary": "Implemented the requested change and ran focused tests.",
        "verification": "verified",
    }
    store = _FakeCompletionStore()
    outcome = asyncio.run(
        SubmitAndExitRegisteredToolAdapter(SubmitRunCompletion(store, InMemoryRunStateMachine())).handle(
            arguments,
            _context(arguments),
        )
    )

    assert outcome.status is ToolOutcomeStatus.SUCCESS
    assert outcome.error_code is None
    assert outcome.runtime_disposition is ToolExecutionRuntimeDisposition.STOP_RUNTIME
    assert len(store.records) == 1
    record = store.records[0]
    assert record.run_id == "run_123"
    assert record.tool_call_id == "call_123"
    assert record.summary == arguments["summary"]
    assert _payload(outcome) == {"run_id": "run_123", "status": "accepted"}


def test_submit_and_exit_maps_application_errors_to_stable_tool_rejections() -> None:
    arguments = {"outcome": "completed", "summary": "Work is complete.", "verification": "verified"}
    states = InMemoryRunStateMachine()
    states.set_state("run_123", CompletionRunState.CANCELLED)

    outcome = asyncio.run(
        SubmitAndExitRegisteredToolAdapter(SubmitRunCompletion(_FakeCompletionStore(), states)).handle(
            arguments,
            _context(arguments),
        )
    )

    assert outcome.status is ToolOutcomeStatus.REJECTED
    assert outcome.error_code is CompletionErrorCode.COMPLETION_NOT_ALLOWED
    assert outcome.retryable is True


def test_submit_and_exit_rejects_invalid_arguments_and_missing_opaque_run_id_without_submitting() -> None:
    store = _FakeCompletionStore()
    adapter = SubmitAndExitRegisteredToolAdapter(SubmitRunCompletion(store, InMemoryRunStateMachine()))
    arguments = {"outcome": "completed", "summary": "Work is complete.", "verification": "verified"}

    invalid_arguments = asyncio.run(adapter.handle({"summary": "Missing fields"}, _context(arguments)))
    missing_run_id = asyncio.run(adapter.handle(arguments, _context(arguments, include_run_id=False)))

    assert invalid_arguments.error_code == "INVALID_ARGUMENTS"
    assert missing_run_id.error_code == "INVALID_ARGUMENTS"
    assert store.records == []


@dataclass(slots=True)
class _FakeCompletionStore:
    records: list[CompletionRecord] = field(default_factory=list)

    async def commit_completion(self, run_id: str, record: CompletionRecord) -> CompletionCommitResult:
        assert run_id == record.run_id
        self.records.append(record)
        return CompletionCommitResult(CompletionCommitStatus.COMMITTED, record)

    async def list_unpresented(self) -> tuple[CompletionRecord, ...]:
        return ()

    async def acknowledge_presented(self, run_id: str) -> bool:
        del run_id
        return False


@dataclass(frozen=True, slots=True)
class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        await asyncio.Event().wait()


def _context(
    arguments: Mapping[str, ToolArgumentValue],
    *,
    include_run_id: bool = True,
) -> ToolExecutionContext:
    opaque_values = {RUN_ID_CONTEXT_KEY: "run_123"} if include_run_id else {}
    return ToolExecutionContext(
        call_id="call_123",
        argument_digest=canonical_tool_arguments_digest(arguments),
        cancellation=_NeverCancelled(),
        opaque_values=opaque_values,
    )


def _payload(outcome: RegisteredToolOutcome) -> dict[str, object]:
    content = outcome.content
    assert len(content) == 1
    assert isinstance(content[0], ToolTextContent)
    return json.loads(content[0].text)
