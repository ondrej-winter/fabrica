"""Ports for durable session records and workspace comparison."""

from pathlib import Path
from typing import Protocol

from fabrica.features.agent_session.application.dtos import SessionCheckpoint, SessionEvent, WorkspaceFingerprint


class SessionRecordStore(Protocol):
    """Persist and retrieve complete session evidence for one workspace."""

    def append_event(self, event: SessionEvent) -> None:
        """Append one completed normalized event."""

    def save_checkpoint(self, checkpoint: SessionCheckpoint) -> None:
        """Atomically publish one completed durable checkpoint."""

    def load_events(self, session_id: str) -> tuple[SessionEvent, ...]:
        """Load recovered append-only evidence for one session."""

    def load_checkpoint(self, session_id: str) -> SessionCheckpoint | None:
        """Load the latest complete checkpoint, if one exists."""

    def list_session_ids(self) -> tuple[str, ...]:
        """List durable session identifiers in stable order."""

    def delete_session(self, session_id: str) -> None:
        """Delete evidence belonging only to one selected session."""

    def export_session(self, session_id: str, destination: Path) -> Path:
        """Write a deterministic user-managed export bundle."""


class WorkspaceFingerprintBuilder(Protocol):
    """Build a conservative fingerprint for a canonical workspace root."""

    def build(self) -> WorkspaceFingerprint:
        """Return an available snapshot or unavailable fail-closed evidence."""
