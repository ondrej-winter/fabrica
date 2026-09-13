"""Tests for durable agent-session boundary DTOs."""

import pytest

from fabrica.features.agent_session.application.dtos import (
    ResumeContext,
    SessionCheckpoint,
    SessionEvent,
    StaleContextAcknowledgement,
    WorkspaceFingerprint,
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
