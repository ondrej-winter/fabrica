"""Tests for durable agent-session boundary DTOs."""

from pathlib import Path

import pytest

from fabrica.features.agent_runtime.application.dtos import (
    ToolAwareModelResponse,
    ToolCallResult,
    ToolCallResultStatus,
    ToolLoopRunResult,
    ToolLoopRunStatus,
)
from fabrica.features.agent_session.application.dtos import (
    ResumeContext,
    SessionCheckpoint,
    SessionEvent,
    StaleContextAcknowledgement,
    WorkspaceFingerprint,
)
from fabrica.features.agent_session.application.use_cases import RecordSessionLifecycle, SessionRecordingError
from fabrica.features.agent_session.domain import SessionState


def test_checkpoint_rejects_pending_work_and_resume_context_requires_ordered_completed_events() -> None:
    """Never retain pending user or approval work in resumable context."""
    fingerprint = WorkspaceFingerprint(digest="sha256:" + "a" * 64)
    with pytest.raises(ValueError, match="pending"):
        SessionCheckpoint("session", 1, SessionState.WAITING_FOR_USER, fingerprint, "done")
    checkpoint = SessionCheckpoint("session", 1, SessionState.INTERRUPTED, fingerprint, "done")
    with pytest.raises(ValueError, match="ordered"):
        ResumeContext(checkpoint, (SessionEvent("session", 3, "later"), SessionEvent("session", 2, "earlier")))


def test_stale_context_acknowledgement_requires_a_plan_digest() -> None:
    """Keep refreshed-plan acknowledgement separate and digest-bound."""
    with pytest.raises(ValueError, match="plan digest"):
        StaleContextAcknowledgement(plan_digest="not-a-digest", acknowledged=True)


def test_lifecycle_recorder_writes_ordered_normalized_evidence_without_runtime_content() -> None:
    store = _Store()
    recorder = RecordSessionLifecycle("session", store, _FingerprintBuilder())

    recorder.start()
    recorder.record_model_response(ToolAwareModelResponse(output_text="completed"))
    recorder.record_tool_result(
        ToolCallResult(
            call_id="tool-1", tool_name="read_files", status=ToolCallResultStatus.SUCCESS, result_text="secret"
        )
    )
    recorder.finish(ToolLoopRunResult(status=ToolLoopRunStatus.SUCCESS, output_text="private prompt output"))

    assert [(event.sequence, event.kind, dict(event.payload)) for event in store.events] == [
        (0, "sensitivity_warning", {"message": "Session records are sensitive local artifacts."}),
        (1, "state_changed", {"state": "running"}),
        (2, "model_turn_completed", {"has_output": True, "tool_call_count": 0}),
        (3, "tool_call_completed", {"status": "success", "tool_name": "read_files"}),
        (4, "run_completed", {"status": "success"}),
        (5, "state_changed", {"state": "completed"}),
    ]
    assert store.checkpoints[-1].state is SessionState.COMPLETED
    assert "secret" not in repr(store.events)
    assert "private prompt output" not in repr(store.events)


def test_lifecycle_recorder_fails_closed_when_event_storage_fails() -> None:
    recorder = RecordSessionLifecycle("session", _Store(fail_writes=True), _FingerprintBuilder())

    with pytest.raises(SessionRecordingError, match="event recording failed"):
        recorder.start()


class _Store:
    def __init__(self, *, fail_writes: bool = False) -> None:
        self.events: list[SessionEvent] = []
        self.checkpoints: list[SessionCheckpoint] = []
        self.fail_writes = fail_writes

    def append_event(self, event: SessionEvent) -> None:
        if self.fail_writes:
            message = "full"
            raise OSError(message)
        self.events.append(event)

    def save_checkpoint(self, checkpoint: SessionCheckpoint) -> None:
        self.checkpoints.append(checkpoint)

    def load_events(self, session_id: str) -> tuple[SessionEvent, ...]:
        return tuple(event for event in self.events if event.session_id == session_id)

    def load_checkpoint(self, session_id: str) -> SessionCheckpoint | None:
        return next(
            (checkpoint for checkpoint in reversed(self.checkpoints) if checkpoint.session_id == session_id), None
        )

    def list_session_ids(self) -> tuple[str, ...]:
        return tuple(sorted({event.session_id for event in self.events}))

    def delete_session(self, session_id: str) -> None:
        self.events[:] = [event for event in self.events if event.session_id != session_id]
        self.checkpoints[:] = [checkpoint for checkpoint in self.checkpoints if checkpoint.session_id != session_id]

    def export_session(self, session_id: str, destination: Path) -> Path:
        del session_id
        return destination


class _FingerprintBuilder:
    def build(self) -> WorkspaceFingerprint:
        return WorkspaceFingerprint(digest="sha256:" + "b" * 64)
