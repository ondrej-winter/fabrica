"""Integration tests for durable completion-store recovery boundaries."""

import asyncio

from fabrica.features.agent_runtime.adapters.outbound.json_completion_store import JsonCompletionStore
from fabrica.features.agent_runtime.application.dtos import (
    CompletionCommitStatus,
    CompletionOutcome,
    CompletionRecord,
    CompletionVerification,
)


class _NeverCancelled:
    @property
    def is_cancelled(self) -> bool:
        return False

    async def wait_until_cancelled(self) -> None:
        await asyncio.Event().wait()


def test_json_completion_store_reopens_committed_record_and_acknowledges_presentation_once(tmp_path) -> None:
    record = CompletionRecord(
        run_id="run-1",
        tool_call_id="call-1",
        payload_digest="sha256:" + "1" * 64,
        outcome=CompletionOutcome.COMPLETED,
        summary="Completed durable storage boundary.",
        verification=CompletionVerification.NOT_APPLICABLE,
    )
    store = JsonCompletionStore(tmp_path)

    committed = asyncio.run(store.commit_completion("run-1", record, _NeverCancelled()))
    reopened_store = JsonCompletionStore(tmp_path)

    assert committed.status is CompletionCommitStatus.COMMITTED
    assert asyncio.run(reopened_store.list_unpresented()) == (record,)
    assert asyncio.run(reopened_store.acknowledge_presented("run-1")) is True
    assert asyncio.run(reopened_store.acknowledge_presented("run-1")) is False
    assert asyncio.run(JsonCompletionStore(tmp_path).list_unpresented()) == ()


def test_json_completion_store_replays_the_committed_record_for_the_same_run(tmp_path) -> None:
    record = CompletionRecord(
        run_id="run-1",
        tool_call_id="call-1",
        payload_digest="sha256:" + "1" * 64,
        outcome=CompletionOutcome.PARTIAL,
        summary="Completed the safe portion of the work.",
        verification=CompletionVerification.NOT_VERIFIED,
    )
    store = JsonCompletionStore(tmp_path)

    asyncio.run(store.commit_completion("run-1", record, _NeverCancelled()))
    replay = asyncio.run(store.commit_completion("run-1", record, _NeverCancelled()))

    assert replay.status is CompletionCommitStatus.ALREADY_COMPLETED
    assert replay.record == record
