"""Tests for atomic terminal completion submission orchestration."""

import asyncio
from dataclasses import dataclass, field

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    CompletionCommitResult,
    CompletionCommitStatus,
    CompletionErrorCode,
    CompletionOutcome,
    CompletionRecord,
    CompletionRunState,
    CompletionSubmission,
    CompletionSubmissionStatus,
    CompletionVerification,
    SubmitRunCompletionCommand,
    ToolCancellationSignal,
)
from fabrica.features.agent_runtime.application.ports import CompletionGuardRejectionError
from fabrica.features.agent_runtime.application.use_cases import (
    InMemoryRunStateMachine,
    SubmitRunCompletion,
    SubmitRunCompletionError,
    submit_run_completion,
)


def test_submit_commits_valid_completion_from_running() -> None:
    async def scenario() -> None:
        store = _FakeCompletionStore()
        states = InMemoryRunStateMachine()

        result = await SubmitRunCompletion(store=store, run_state_machine=states).submit(
            _command(), cancellation=_Cancellation()
        )

        assert result.status is CompletionSubmissionStatus.ACCEPTED
        assert states.state_for("run-1") is CompletionRunState.COMPLETED
        assert store.records == [result.record]

    asyncio.run(scenario())


def test_submit_rejects_non_positive_timeout_and_completed_state_helper() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        SubmitRunCompletion(
            store=_FakeCompletionStore(), run_state_machine=InMemoryRunStateMachine(), timeout_seconds=0
        )

    error = submit_run_completion._state_error(CompletionRunState.COMPLETED)  # noqa: SLF001

    assert error.code is CompletionErrorCode.RUN_ALREADY_COMPLETED


@pytest.mark.parametrize(
    "expected_code",
    [
        CompletionErrorCode.COMPLETION_GUARD_FAILED,
        CompletionErrorCode.VERIFICATION_REQUIREMENT_NOT_MET,
    ],
)
def test_submit_keeps_running_and_returns_safe_guard_rejection(expected_code: CompletionErrorCode) -> None:
    async def scenario() -> None:
        store = _FakeCompletionStore()
        states = InMemoryRunStateMachine()
        guard = _RejectingGuard(expected_code)

        with pytest.raises(SubmitRunCompletionError) as error:
            await SubmitRunCompletion(store=store, run_state_machine=states, guard=guard).submit(
                _command(), cancellation=_Cancellation()
            )

        assert error.value.code is expected_code
        assert str(error.value) == "completion policy blocked submission"
        assert states.state_for("run-1") is CompletionRunState.RUNNING
        assert store.records == []

    asyncio.run(scenario())


def test_submit_replays_identical_call_once_and_rejects_conflicting_or_later_calls() -> None:
    async def scenario() -> None:
        store = _FakeCompletionStore()
        states = InMemoryRunStateMachine()
        use_case = SubmitRunCompletion(store=store, run_state_machine=states)
        cancellation = _Cancellation()

        accepted = await use_case.submit(_command(), cancellation=cancellation)
        replay = await use_case.submit(_command(), cancellation=cancellation)

        assert accepted.status is CompletionSubmissionStatus.ACCEPTED
        assert replay.status is CompletionSubmissionStatus.ALREADY_ACCEPTED
        assert replay.record == accepted.record
        assert store.records == [accepted.record]

        with pytest.raises(SubmitRunCompletionError) as conflict:
            await use_case.submit(_command(summary="Different summary."), cancellation=cancellation)
        assert conflict.value.code is CompletionErrorCode.IDEMPOTENCY_KEY_CONFLICT

        with pytest.raises(SubmitRunCompletionError) as later_call:
            await use_case.submit(_command(tool_call_id="call-2"), cancellation=cancellation)
        assert later_call.value.code is CompletionErrorCode.RUN_ALREADY_COMPLETED

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        ("persistence", CompletionErrorCode.PERSISTENCE_ERROR),
        ("internal", CompletionErrorCode.PERSISTENCE_ERROR),
        ("timeout", CompletionErrorCode.SUBMIT_TIMEOUT),
    ],
)
def test_submit_failure_does_not_retry_or_complete_run(
    failure: str,
    expected_code: CompletionErrorCode,
) -> None:
    async def scenario() -> None:
        states = InMemoryRunStateMachine()
        store = _store_for_failure(failure)
        timeout_seconds = 0.001 if failure == "timeout" else 1

        with pytest.raises(SubmitRunCompletionError) as error:
            await SubmitRunCompletion(store=store, run_state_machine=states, timeout_seconds=timeout_seconds).submit(
                _command(), cancellation=_Cancellation()
            )

        assert error.value.code is expected_code
        assert states.state_for("run-1") is CompletionRunState.RUNNING
        assert store.commit_calls == 1
        assert store.records == []

    asyncio.run(scenario())


def test_submit_rejects_invalid_accepted_store_result_without_completing_run() -> None:
    async def scenario() -> None:
        states = InMemoryRunStateMachine()
        store = _InvalidResultStore()

        with pytest.raises(SubmitRunCompletionError) as error:
            await SubmitRunCompletion(store=store, run_state_machine=states).submit(
                _command(), cancellation=_Cancellation()
            )

        assert error.value.code is CompletionErrorCode.INTERNAL_COMPLETION_ERROR
        assert states.state_for("run-1") is CompletionRunState.RUNNING
        assert store.records == []

    asyncio.run(scenario())


@pytest.mark.parametrize("cancellation_point", ["before_guard", "during_guard", "before_commit"])
def test_cancelled_submission_never_persists_or_completes(cancellation_point: str) -> None:
    async def scenario() -> None:
        cancellation = _Cancellation(cancelled=cancellation_point == "before_guard")
        guard = _CancellingGuard(cancellation) if cancellation_point == "during_guard" else None
        store = (
            _CancellingStore(cancellation=cancellation)
            if cancellation_point == "before_commit"
            else _FakeCompletionStore()
        )
        states = InMemoryRunStateMachine()

        with pytest.raises(SubmitRunCompletionError) as error:
            await SubmitRunCompletion(store=store, run_state_machine=states, guard=guard).submit(
                _command(), cancellation=cancellation
            )

        assert error.value.code is CompletionErrorCode.SUBMIT_CANCELLED
        assert states.state_for("run-1") is CompletionRunState.RUNNING
        assert store.records == []

    asyncio.run(scenario())


def test_atomic_store_completion_win_remains_completed_when_cancellation_arrives_after_commit() -> None:
    async def scenario() -> None:
        cancellation = _Cancellation()
        store = _FakeCompletionStore(cancel_after_commit=cancellation)
        states = InMemoryRunStateMachine()

        result = await SubmitRunCompletion(store=store, run_state_machine=states).submit(
            _command(), cancellation=cancellation
        )

        assert result.status is CompletionSubmissionStatus.ACCEPTED
        assert cancellation.is_cancelled is True
        assert states.state_for("run-1") is CompletionRunState.COMPLETED
        assert len(store.records) == 1

    asyncio.run(scenario())


@dataclass(slots=True)
class _Cancellation:
    cancelled: bool = False
    _event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled

    def cancel(self) -> None:
        self.cancelled = True
        self._event.set()

    async def wait_until_cancelled(self) -> None:
        await self._event.wait()


@dataclass(slots=True)
class _FakeCompletionStore:
    error: Exception | None = None
    cancel_after_commit: _Cancellation | None = None
    records: list[CompletionRecord] = field(default_factory=list)
    commit_calls: int = 0

    async def commit_completion(
        self,
        run_id: str,
        record: CompletionRecord,
        cancellation: ToolCancellationSignal,
    ) -> CompletionCommitResult:
        assert run_id == record.run_id
        self.commit_calls += 1
        if cancellation.is_cancelled:
            return CompletionCommitResult(CompletionCommitStatus.CANCELLED)
        if self.error is not None:
            raise self.error
        if self.records:
            return CompletionCommitResult(CompletionCommitStatus.ALREADY_COMPLETED, self.records[0])
        self.records.append(record)
        if self.cancel_after_commit is not None:
            self.cancel_after_commit.cancel()
        return CompletionCommitResult(CompletionCommitStatus.COMMITTED, record)

    async def list_unpresented(self) -> tuple[CompletionRecord, ...]:
        return ()

    async def acknowledge_presented(self, run_id: str) -> bool:
        del run_id
        return False


@dataclass(slots=True)
class _BlockingStore:
    records: list[CompletionRecord] = field(default_factory=list)
    commit_calls: int = 0

    async def commit_completion(
        self,
        run_id: str,
        record: CompletionRecord,
        cancellation: ToolCancellationSignal,
    ) -> CompletionCommitResult:
        del run_id, record, cancellation
        self.commit_calls += 1
        await asyncio.Event().wait()
        msg = "unreachable"
        raise AssertionError(msg)

    async def list_unpresented(self) -> tuple[CompletionRecord, ...]:
        return ()

    async def acknowledge_presented(self, run_id: str) -> bool:
        del run_id
        return False


@dataclass(slots=True)
class _InvalidResultStore:
    records: list[CompletionRecord] = field(default_factory=list)
    commit_calls: int = 0

    async def commit_completion(
        self,
        run_id: str,
        record: CompletionRecord,
        cancellation: ToolCancellationSignal,
    ) -> CompletionCommitResult:
        del run_id, record, cancellation
        self.commit_calls += 1
        result = object.__new__(CompletionCommitResult)
        object.__setattr__(result, "status", CompletionCommitStatus.COMMITTED)
        object.__setattr__(result, "record", None)
        return result

    async def list_unpresented(self) -> tuple[CompletionRecord, ...]:
        return ()

    async def acknowledge_presented(self, run_id: str) -> bool:
        del run_id
        return False


@dataclass(slots=True)
class _CancellingStore(_FakeCompletionStore):
    cancellation: _Cancellation = field(default_factory=_Cancellation)

    async def commit_completion(
        self,
        run_id: str,
        record: CompletionRecord,
        cancellation: ToolCancellationSignal,
    ) -> CompletionCommitResult:
        self.cancellation.cancel()
        return await super().commit_completion(run_id, record, cancellation)


@dataclass(frozen=True, slots=True)
class _RejectingGuard:
    code: CompletionErrorCode

    async def evaluate(self, record: CompletionRecord) -> None:
        del record
        raise CompletionGuardRejectionError(self.code, "completion policy blocked submission")


@dataclass(frozen=True, slots=True)
class _CancellingGuard:
    cancellation: _Cancellation

    async def evaluate(self, record: CompletionRecord) -> None:
        del record
        self.cancellation.cancel()


def _command(
    *,
    tool_call_id: str = "call-1",
    summary: str = "Implemented the requested change.",
) -> SubmitRunCompletionCommand:
    return SubmitRunCompletionCommand(
        run_id="run-1",
        tool_call_id=tool_call_id,
        submission=CompletionSubmission(
            outcome=CompletionOutcome.COMPLETED,
            summary=summary,
            verification=CompletionVerification.VERIFIED,
        ),
        metadata={"source": "unit-test"},
    )


def _store_for_failure(failure: str) -> _FakeCompletionStore | _BlockingStore:
    if failure == "persistence":
        return _FakeCompletionStore(error=OSError("private storage detail"))
    if failure == "internal":
        return _FakeCompletionStore(error=RuntimeError("private invariant detail"))
    return _BlockingStore()
