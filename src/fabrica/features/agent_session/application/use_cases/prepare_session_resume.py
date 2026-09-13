"""Safe-boundary resume classification from durable normalized session evidence."""

from dataclasses import dataclass
from enum import StrEnum

from fabrica.features.agent_session.application.dtos import MAX_RESUME_EVENTS, ResumeContext, SessionCheckpoint
from fabrica.features.agent_session.application.ports import SessionRecordStore, WorkspaceFingerprintBuilder
from fabrica.features.agent_session.domain import SessionState


class ResumeDisposition(StrEnum):
    """The safe next action after inspecting stored and current session context."""

    RESUME = "resume"
    STALE_CONTEXT = "stale_context"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SessionResumePreparation:
    """A fresh resume context or a fail-closed disposition requiring user action."""

    disposition: ResumeDisposition
    resume_context: ResumeContext | None = None
    stale_context_reason: str | None = None

    def __post_init__(self) -> None:
        """Keep resume and non-resume outcomes explicit and unambiguous."""
        if self.disposition is ResumeDisposition.RESUME and self.resume_context is None:
            msg = "a resume disposition requires fresh continuation context"
            raise ValueError(msg)
        if self.disposition is not ResumeDisposition.RESUME and self.stale_context_reason is None:
            msg = "a non-resume disposition requires a reason"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PrepareSessionResume:
    """Reconstruct only completed evidence for a provider-neutral fresh model turn."""

    store: SessionRecordStore
    fingerprint_builder: WorkspaceFingerprintBuilder

    def execute(self, session_id: str) -> SessionResumePreparation:
        """Compare current workspace state and return safe continuation context when valid."""
        checkpoint = self.store.load_checkpoint(session_id)
        if checkpoint is None:
            return SessionResumePreparation(
                ResumeDisposition.UNAVAILABLE,
                stale_context_reason="no completed checkpoint is available",
            )
        disposition, reason = self._checkpoint_disposition(checkpoint)
        if reason is not None:
            return SessionResumePreparation(disposition, stale_context_reason=reason)
        current_fingerprint = self.fingerprint_builder.build()
        if not current_fingerprint.available:
            return SessionResumePreparation(
                ResumeDisposition.STALE_CONTEXT,
                stale_context_reason="current workspace fingerprint is unavailable",
            )
        if checkpoint.workspace_fingerprint.digest != current_fingerprint.digest:
            return SessionResumePreparation(
                ResumeDisposition.STALE_CONTEXT,
                stale_context_reason="workspace fingerprint changed",
            )
        later_events = tuple(
            event for event in self.store.load_events(session_id) if event.sequence > checkpoint.sequence
        )
        if len(later_events) > MAX_RESUME_EVENTS:
            return SessionResumePreparation(
                ResumeDisposition.UNAVAILABLE,
                stale_context_reason="later session evidence exceeds the resume bound",
            )
        return SessionResumePreparation(
            ResumeDisposition.RESUME,
            resume_context=ResumeContext(checkpoint, later_events),
        )

    @staticmethod
    def _checkpoint_disposition(checkpoint: SessionCheckpoint) -> tuple[ResumeDisposition, str | None]:
        if checkpoint.state in {SessionState.WAITING_FOR_APPROVAL, SessionState.WAITING_FOR_USER}:
            return ResumeDisposition.UNAVAILABLE, "checkpoint contains pending work"
        if not checkpoint.workspace_fingerprint.available:
            return ResumeDisposition.STALE_CONTEXT, "stored workspace fingerprint is unavailable"
        return ResumeDisposition.RESUME, None
