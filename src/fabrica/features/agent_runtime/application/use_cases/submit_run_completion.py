"""Use case for atomically accepting a terminal agent-run completion."""

import asyncio
from dataclasses import dataclass, field

from fabrica.features.agent_runtime.application.dtos import (
    DEFAULT_COMPLETION_SUBMIT_TIMEOUT_SECONDS,
    CompletionCommitStatus,
    CompletionErrorCode,
    CompletionRecord,
    CompletionRunState,
    CompletionSubmissionStatus,
    SubmitRunCompletionCommand,
    SubmitRunCompletionResult,
    completion_submission_digest,
)
from fabrica.features.agent_runtime.application.dtos.tools import ToolCancellationSignal
from fabrica.features.agent_runtime.application.ports import (
    CompletionGuard,
    CompletionGuardRejectionError,
    CompletionStore,
)
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
    timeout_seconds: float = DEFAULT_COMPLETION_SUBMIT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        """Validate the bounded completion deadline at composition time."""
        if self.timeout_seconds <= 0:
            msg = "completion submit timeout must be positive"
            raise ValueError(msg)

    async def submit(
        self,
        command: SubmitRunCompletionCommand,
        *,
        cancellation: ToolCancellationSignal,
    ) -> SubmitRunCompletionResult:
        """Commit a terminal record only from ``RUNNING`` and return its accepted state."""
        current_state = self.run_state_machine.state_for(command.run_id)
        if current_state is not CompletionRunState.RUNNING and current_state is not CompletionRunState.COMPLETED:
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
        try:
            async with asyncio.timeout(self.timeout_seconds):
                _raise_if_cancelled(cancellation)
                if self.guard is not None:
                    await self.guard.evaluate(record)
                _raise_if_cancelled(cancellation)
                committed = await self.store.commit_completion(command.run_id, record, cancellation)
        except CompletionGuardRejectionError as err:
            raise SubmitRunCompletionError(err.code, str(err)) from err
        except SubmitRunCompletionError:
            raise
        except TimeoutError as err:
            raise SubmitRunCompletionError(
                CompletionErrorCode.SUBMIT_TIMEOUT, "completion submission timed out"
            ) from err
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
        _validate_replayed_record(current_state, record, accepted_record)
        self.run_state_machine.mark_completed(command.run_id)
        status = (
            CompletionSubmissionStatus.ACCEPTED
            if committed.status is CompletionCommitStatus.COMMITTED
            else CompletionSubmissionStatus.ALREADY_ACCEPTED
        )
        return SubmitRunCompletionResult(status=status, record=accepted_record)


def _raise_if_cancelled(cancellation: ToolCancellationSignal) -> None:
    if cancellation.is_cancelled:
        raise SubmitRunCompletionError(CompletionErrorCode.SUBMIT_CANCELLED, "run cancellation won before completion")


def _validate_replayed_record(
    current_state: CompletionRunState,
    proposed: CompletionRecord,
    accepted: CompletionRecord,
) -> None:
    if current_state is not CompletionRunState.COMPLETED:
        return
    if accepted.tool_call_id != proposed.tool_call_id:
        raise SubmitRunCompletionError(CompletionErrorCode.RUN_ALREADY_COMPLETED, "run is already completed")
    if accepted.payload_digest != proposed.payload_digest:
        raise SubmitRunCompletionError(
            CompletionErrorCode.IDEMPOTENCY_KEY_CONFLICT, "completion retry conflicts with prior payload"
        )


def _state_error(state: CompletionRunState) -> SubmitRunCompletionError:
    if state is CompletionRunState.COMPLETED:
        return SubmitRunCompletionError(CompletionErrorCode.RUN_ALREADY_COMPLETED, "run is already completed")
    return SubmitRunCompletionError(
        CompletionErrorCode.COMPLETION_NOT_ALLOWED,
        f"completion is only allowed from running; run is {state.value}",
    )


__all__ = ["InMemoryRunStateMachine", "SubmitRunCompletion", "SubmitRunCompletionError"]
