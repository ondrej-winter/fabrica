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
from fabrica.features.agent_session.application.use_cases import (
    AcknowledgeStaleContextPlan,
    PrepareSessionResume,
    RecordSessionLifecycle,
    ReplanSafetyGate,
    ReplanSafetyState,
    ResumeDisposition,
    SessionRecordingError,
)
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


def test_lifecycle_recorder_continues_monotonic_event_sequences_for_a_resumed_session() -> None:
    store = _Store()
    store.events.append(SessionEvent("session", 7, "completed"))
    recorder = RecordSessionLifecycle("session", store, _FingerprintBuilder())

    recorder.start()

    assert [(event.sequence, event.kind) for event in store.events] == [
        (7, "completed"),
        (8, "sensitivity_warning"),
        (9, "state_changed"),
    ]


def test_prepare_session_resume_returns_fresh_context_only_for_a_matching_available_workspace() -> None:
    store = _Store()
    fingerprint = WorkspaceFingerprint(digest="sha256:" + "a" * 64)
    store.checkpoints.append(SessionCheckpoint("session", 1, SessionState.INTERRUPTED, fingerprint, "safe checkpoint"))
    store.events.extend((SessionEvent("session", 0, "started"), SessionEvent("session", 2, "completed")))

    result = PrepareSessionResume(store, _FingerprintBuilder(fingerprint)).execute("session")

    assert result.disposition is ResumeDisposition.RESUME
    assert result.resume_context == ResumeContext(store.checkpoints[0], (store.events[1],))
    assert result.resume_context.continuation_instruction.startswith("Treat this history as context only")


@pytest.mark.parametrize(
    ("current_fingerprint", "expected_reason"),
    [
        (WorkspaceFingerprint(digest="sha256:" + "b" * 64), "workspace fingerprint changed"),
        (
            WorkspaceFingerprint(digest=None, unavailable_reason="scan failed"),
            "current workspace fingerprint is unavailable",
        ),
    ],
)
def test_prepare_session_resume_enters_stale_context_without_resuming_for_mismatch_or_scan_failure(
    current_fingerprint: WorkspaceFingerprint, expected_reason: str
) -> None:
    store = _Store()
    stored_fingerprint = WorkspaceFingerprint(digest="sha256:" + "a" * 64)
    store.checkpoints.append(
        SessionCheckpoint("session", 1, SessionState.INTERRUPTED, stored_fingerprint, "safe checkpoint")
    )

    result = PrepareSessionResume(store, _FingerprintBuilder(current_fingerprint)).execute("session")

    assert result.disposition is ResumeDisposition.STALE_CONTEXT
    assert result.resume_context is None
    assert result.stale_context_reason == expected_reason


def test_prepare_session_resume_rejects_a_checkpoint_with_pending_work_or_missing_evidence() -> None:
    store = _Store()

    result = PrepareSessionResume(store, _FingerprintBuilder()).execute("missing")

    assert result.disposition is ResumeDisposition.UNAVAILABLE
    assert result.stale_context_reason == "no completed checkpoint is available"


def test_prepare_session_resume_fails_closed_when_later_evidence_exceeds_the_context_bound() -> None:
    store = _Store()
    fingerprint = WorkspaceFingerprint(digest="sha256:" + "a" * 64)
    store.checkpoints.append(SessionCheckpoint("session", 0, SessionState.INTERRUPTED, fingerprint, "safe checkpoint"))
    store.events.extend(SessionEvent("session", sequence, "completed") for sequence in range(1, 202))

    result = PrepareSessionResume(store, _FingerprintBuilder(fingerprint)).execute("session")

    assert result.disposition is ResumeDisposition.UNAVAILABLE
    assert result.stale_context_reason == "later session evidence exceeds the resume bound"


def test_stale_context_acknowledgement_is_digest_bound_and_expires_when_plan_changes() -> None:
    store = _Store()
    acknowledgements = AcknowledgeStaleContextPlan(store, "session")
    first_plan_digest = "sha256:" + "c" * 64

    acknowledgement = acknowledgements.acknowledge(first_plan_digest, acknowledged=True)

    assert acknowledgement.acknowledged
    assert acknowledgements.is_acknowledged(first_plan_digest)
    assert not acknowledgements.is_acknowledged("sha256:" + "d" * 64)
    assert acknowledgements.acknowledge(first_plan_digest, acknowledged=False).acknowledged is False
    assert acknowledgements.is_acknowledged(first_plan_digest) is False
    assert [(event.kind, dict(event.payload)) for event in store.events] == [
        (
            "stale_context_plan_acknowledged",
            {"plan_digest": first_plan_digest, "acknowledged": True},
        ),
        (
            "stale_context_plan_acknowledged",
            {"plan_digest": first_plan_digest, "acknowledged": False},
        ),
    ]


def test_replan_safety_gate_requires_fresh_inspection_plan_display_and_matching_acknowledgement() -> None:
    store = _Store()
    gate = ReplanSafetyGate(AcknowledgeStaleContextPlan(store, "session"))
    plan_digest = "sha256:" + "e" * 64

    assert gate.state is ReplanSafetyState.INSPECTION_REQUIRED
    assert gate.side_effects_permitted is False
    assert gate.side_effect_block_reason() == "fresh workspace inspection is required before side effects"
    with pytest.raises(ValueError, match="inspection"):
        gate.display_refreshed_plan(plan_digest)

    gate.record_fresh_inspection()
    gate.display_refreshed_plan(plan_digest)

    assert gate.state is ReplanSafetyState.PLAN_ACKNOWLEDGEMENT_REQUIRED
    assert gate.side_effects_permitted is False
    gate.acknowledge_displayed_plan(acknowledged=True)

    assert gate.state is ReplanSafetyState.SIDE_EFFECTS_PERMITTED
    assert gate.side_effects_permitted is True
    assert gate.side_effect_block_reason() is None


def test_replan_safety_gate_expires_acknowledgement_when_the_displayed_plan_changes() -> None:
    store = _Store()
    gate = ReplanSafetyGate(AcknowledgeStaleContextPlan(store, "session"))
    first_plan_digest = "sha256:" + "e" * 64
    second_plan_digest = "sha256:" + "f" * 64
    gate.record_fresh_inspection()
    gate.display_refreshed_plan(first_plan_digest)
    gate.acknowledge_displayed_plan(acknowledged=True)

    gate.display_refreshed_plan(second_plan_digest)

    assert gate.state is ReplanSafetyState.PLAN_ACKNOWLEDGEMENT_REQUIRED
    assert gate.side_effects_permitted is False
    assert gate.side_effect_block_reason() == "displayed refreshed-plan acknowledgement is required before side effects"


def test_replan_safety_gate_rejects_acknowledgement_until_a_plan_is_displayed() -> None:
    gate = ReplanSafetyGate(AcknowledgeStaleContextPlan(_Store(), "session"))

    with pytest.raises(ValueError, match="displayed"):
        gate.acknowledge_displayed_plan(acknowledged=True)


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
    def __init__(self, fingerprint: WorkspaceFingerprint | None = None) -> None:
        self.fingerprint = fingerprint or WorkspaceFingerprint(digest="sha256:" + "b" * 64)

    def build(self) -> WorkspaceFingerprint:
        return self.fingerprint
