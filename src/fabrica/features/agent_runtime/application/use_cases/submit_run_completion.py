"""Use case for atomically accepting a terminal agent-run completion."""

from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    CompletionCommitStatus,
    CompletionErrorCode,
    CompletionRecord,
    CompletionRunState,
    CompletionSubmissionStatus,
    SubmitRunCompletionCommand,
    SubmitRunCompletionResult,
    completion_submission_digest,
)
from fabrica.features.agent_runtime.application.ports import CompletionGuard, CompletionStore
from fabrica.features.agent_runtime.application.ports.run_state import RunStateMachine


class SubmitRunCompletionError(Exception):
    """Stable application error raised when terminal completion is not accepted."""

    def __init__(self, code: CompletionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class InMemoryRunStateMachine:
    """Track completion-aware run state for one in-process runtime composition."""

    _states: dict[str, CompletionRunState] = field(default_factory=dict, init=False, repr=False)

    def state_for(self, run_id: str) -> CompletionRunState:
        """Return ``RUNNING`` for new runs and their retained lifecycle state thereafter."""
        return self._states.get(run_id, CompletionRunState.RUNNING)

    def mark_completed(self, run_id: str) -> None:
        """Record the local mirror of a durable completion commit."""
        self._states[run_id] = CompletionRunState.COMPLETED

    def set_state(self, run_id: str, state: CompletionRunState) -> None:
        """Set a lifecycle state for runtime orchestration and focused tests."""
        self._states[run_id] = state


@dataclass(frozen=True, slots=True)
class SubmitRunCompletion:
    """Apply guard policy then durably commit one ``RUNNING → COMPLETED`` submission."""

    store: CompletionStore
    run_state_machine: RunStateMachine
    guard: CompletionGuard | None = None

    async def submit(self, command: SubmitRunCompletionCommand) -> SubmitRunCompletionResult:
        """Commit a terminal record only from ``RUNNING`` and return its accepted state."""
        current_state = self.run_state_machine.state_for(command.run_id)
        if current_state is not CompletionRunState.RUNNING:
            raise _state_error(current_state)

        record = CompletionRecord(
            run_id=command.run_id,
            tool_call_id=command.tool_call_id,
            payload_digest=completion_submission_digest(command.submission),
            outcome=command.submission.outcome,
            summary=command.submission.summary,
            verification=command.submission.verification,
            metadata=command.metadata,
        )
        if self.guard is not None:
            block_reason = await self.guard.evaluate(record)
            if block_reason is not None:
                raise SubmitRunCompletionError(CompletionErrorCode.COMPLETION_GUARD_FAILED, block_reason)

        try:
            committed = await self.store.commit_completion(command.run_id, record)
        except Exception as err:
            raise SubmitRunCompletionError(
                CompletionErrorCode.PERSISTENCE_ERROR,
                "completion could not be durably committed",
            ) from err

        if committed.status is CompletionCommitStatus.CANCELLED:
            raise SubmitRunCompletionError(
                CompletionErrorCode.SUBMIT_CANCELLED, "run cancellation won before completion"
            )

        accepted_record = committed.record
        if accepted_record is None:
            msg = "completion store returned an accepted status without a record"
            raise SubmitRunCompletionError(CompletionErrorCode.INTERNAL_COMPLETION_ERROR, msg)
        self.run_state_machine.mark_completed(command.run_id)
        status = (
            CompletionSubmissionStatus.ACCEPTED
            if committed.status is CompletionCommitStatus.COMMITTED
            else CompletionSubmissionStatus.ALREADY_ACCEPTED
        )
        return SubmitRunCompletionResult(status=status, record=accepted_record)


def _state_error(state: CompletionRunState) -> SubmitRunCompletionError:
    if state is CompletionRunState.COMPLETED:
        return SubmitRunCompletionError(CompletionErrorCode.RUN_ALREADY_COMPLETED, "run is already completed")
    return SubmitRunCompletionError(
        CompletionErrorCode.COMPLETION_NOT_ALLOWED,
        f"completion is only allowed from running; run is {state.value}",
    )


__all__ = ["InMemoryRunStateMachine", "SubmitRunCompletion", "SubmitRunCompletionError"]
