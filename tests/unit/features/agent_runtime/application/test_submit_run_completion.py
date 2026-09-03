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
)
from fabrica.features.agent_runtime.application.use_cases import (
    InMemoryRunStateMachine,
    SubmitRunCompletion,
    SubmitRunCompletionError,
)


@pytest.mark.parametrize("outcome", tuple(CompletionOutcome))
@pytest.mark.parametrize("verification", tuple(CompletionVerification))
def test_submit_commits_every_valid_outcome_and_verification_from_running(
    outcome: CompletionOutcome,
    verification: CompletionVerification,
) -> None:
    async def scenario() -> None:
        store = _FakeCompletionStore()
        states = InMemoryRunStateMachine()
        use_case = SubmitRunCompletion(store=store, run_state_machine=states, guard=_AllowingGuard())

        result = await use_case.submit(_command(outcome=outcome, verification=verification))

        assert result.status is CompletionSubmissionStatus.ACCEPTED
        assert result.record.outcome is outcome
        assert result.record.verification is verification
        assert states.state_for("run-1") is CompletionRunState.COMPLETED
        assert store.records == [result.record]

    asyncio.run(scenario())


def test_guard_or_persistence_failure_keeps_run_running_and_allows_a_later_submission() -> None:
    async def scenario() -> None:
        store = _FakeCompletionStore(fail_next_commit=True)
        states = InMemoryRunStateMachine()
        use_case = SubmitRunCompletion(store=store, run_state_machine=states, guard=_BlockingGuard())

        with pytest.raises(SubmitRunCompletionError) as blocked:
            await use_case.submit(_command())
        assert blocked.value.code is CompletionErrorCode.COMPLETION_GUARD_FAILED
        assert states.state_for("run-1") is CompletionRunState.RUNNING
        assert store.records == []

        use_case = SubmitRunCompletion(store=store, run_state_machine=states)
        with pytest.raises(SubmitRunCompletionError) as failed:
            await use_case.submit(_command())
        assert failed.value.code is CompletionErrorCode.PERSISTENCE_ERROR
        assert states.state_for("run-1") is CompletionRunState.RUNNING
        assert store.records == []

        accepted = await use_case.submit(_command())
        assert accepted.status is CompletionSubmissionStatus.ACCEPTED
        assert states.state_for("run-1") is CompletionRunState.COMPLETED

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [
        (CompletionRunState.WAITING_FOR_USER, CompletionErrorCode.COMPLETION_NOT_ALLOWED),
        (CompletionRunState.CANCELLED, CompletionErrorCode.COMPLETION_NOT_ALLOWED),
        (CompletionRunState.ERROR, CompletionErrorCode.COMPLETION_NOT_ALLOWED),
        (CompletionRunState.COMPLETED, CompletionErrorCode.RUN_ALREADY_COMPLETED),
    ],
)
def test_submit_rejects_runs_that_are_not_running(
    state: CompletionRunState, expected_code: CompletionErrorCode
) -> None:
    async def scenario() -> None:
        store = _FakeCompletionStore()
        states = InMemoryRunStateMachine()
        states.set_state("run-1", state)

        with pytest.raises(SubmitRunCompletionError) as error:
            await SubmitRunCompletion(store=store, run_state_machine=states).submit(_command())

        assert error.value.code is expected_code
        assert store.records == []
        assert states.state_for("run-1") is state

    asyncio.run(scenario())


@dataclass(slots=True)
class _FakeCompletionStore:
    fail_next_commit: bool = False
    records: list[CompletionRecord] = field(default_factory=list)

    async def commit_completion(self, run_id: str, record: CompletionRecord) -> CompletionCommitResult:
        assert run_id == record.run_id
        if self.fail_next_commit:
            self.fail_next_commit = False
            message = "durable store unavailable"
            raise OSError(message)
        self.records.append(record)
        return CompletionCommitResult(CompletionCommitStatus.COMMITTED, record)

    async def list_unpresented(self) -> tuple[CompletionRecord, ...]:
        return ()

    async def acknowledge_presented(self, run_id: str) -> bool:
        del run_id
        return False


@dataclass(frozen=True, slots=True)
class _AllowingGuard:
    async def evaluate(self, record: CompletionRecord) -> str | None:
        del record
        return None


@dataclass(frozen=True, slots=True)
class _BlockingGuard:
    async def evaluate(self, record: CompletionRecord) -> str | None:
        del record
        return "required verification has not completed"


def _command(
    *,
    outcome: CompletionOutcome = CompletionOutcome.COMPLETED,
    verification: CompletionVerification = CompletionVerification.VERIFIED,
) -> SubmitRunCompletionCommand:
    return SubmitRunCompletionCommand(
        run_id="run-1",
        tool_call_id="call-1",
        submission=CompletionSubmission(
            outcome=outcome, summary="Implemented the requested change.", verification=verification
        ),
        metadata={"source": "unit-test"},
    )
