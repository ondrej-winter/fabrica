"""Workspace-local durable session journal and checkpoint adapter."""

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from fabrica.features.agent_session.application.dtos import (
    SESSION_RECORD_SCHEMA_VERSION,
    SessionCheckpoint,
    SessionEvent,
    WorkspaceFingerprint,
)
from fabrica.features.agent_session.domain import SessionState


class SessionRecordError(RuntimeError):
    """Raised when persisted session evidence cannot be read safely."""


@dataclass(frozen=True, slots=True)
class PosixSessionRecordStore:
    """Store one JSONL journal and atomically replaced checkpoint per session."""

    workspace_root: Path

    def append_event(self, event: SessionEvent) -> None:
        """Append and flush completed event evidence synchronously."""
        path = self._session_path(event.session_id) / "events.jsonl"
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        encoded = (json.dumps(_event_payload(event), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        with path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)

    def save_checkpoint(self, checkpoint: SessionCheckpoint) -> None:
        """Atomically publish a fully written checkpoint for readers."""
        _atomic_write_json(
            self._session_path(checkpoint.session_id) / "checkpoint.json", _checkpoint_payload(checkpoint)
        )

    def load_events(self, session_id: str) -> tuple[SessionEvent, ...]:
        """Read a journal, ignoring only a malformed final non-empty record."""
        path = self._session_path(session_id) / "events.jsonl"
        if not path.exists():
            return ()
        lines = path.read_bytes().splitlines()
        events: list[SessionEvent] = []
        for index, line in enumerate(lines):
            if not line:
                continue
            try:
                event = _event_from_payload(json.loads(line))
            except (TypeError, ValueError, json.JSONDecodeError) as err:
                if index == len(lines) - 1:
                    break
                msg = "session journal is corrupt before its final record"
                raise SessionRecordError(msg) from err
            if event.session_id != session_id or (events and event.sequence <= events[-1].sequence):
                msg = "session journal identity or sequence is invalid"
                raise SessionRecordError(msg)
            events.append(event)
        return tuple(events)

    def load_checkpoint(self, session_id: str) -> SessionCheckpoint | None:
        """Load a complete checkpoint or fail closed on malformed durable data."""
        path = self._session_path(session_id) / "checkpoint.json"
        if not path.exists():
            return None
        try:
            return _checkpoint_from_payload(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as err:
            msg = "session checkpoint is unreadable"
            raise SessionRecordError(msg) from err

    def list_session_ids(self) -> tuple[str, ...]:
        """List direct session directories in deterministic order."""
        root = self._sessions_root()
        if not root.exists():
            return ()
        return tuple(path.name for path in sorted(root.iterdir()) if path.is_dir() and _valid_session_id(path.name))

    def delete_session(self, session_id: str) -> None:
        """Delete exactly one selected session record directory."""
        path = self._session_path(session_id)
        if path.exists():
            shutil.rmtree(path)
            _fsync_directory(path.parent)

    def export_session(self, session_id: str, destination: Path) -> Path:
        """Create deterministic user-managed export files outside managed storage."""
        events = self.load_events(session_id)
        checkpoint = self.load_checkpoint(session_id)
        target = Path(destination)
        target.mkdir(mode=0o700, parents=True, exist_ok=False)
        _atomic_write_json(
            target / "manifest.json", {"schema_version": SESSION_RECORD_SCHEMA_VERSION, "session_id": session_id}
        )
        encoded_events = "".join(
            json.dumps(_event_payload(event), sort_keys=True, separators=(",", ":")) + "\n" for event in events
        )
        (target / "events.jsonl").write_text(encoded_events, encoding="utf-8")
        if checkpoint is None:
            checkpoint_payload: dict[str, object] = {
                "schema_version": SESSION_RECORD_SCHEMA_VERSION,
                "session_id": session_id,
                "checkpoint": None,
            }
        else:
            checkpoint_payload = _checkpoint_payload(checkpoint)
        _atomic_write_json(target / "checkpoint.json", checkpoint_payload)
        _fsync_directory(target)
        return target

    def _sessions_root(self) -> Path:
        return self.workspace_root.resolve(strict=True) / ".fabrica" / "sessions"

    def _session_path(self, session_id: str) -> Path:
        if not _valid_session_id(session_id):
            msg = "session id must be a safe non-empty identifier"
            raise ValueError(msg)
        return self._sessions_root() / session_id


def _valid_session_id(session_id: str) -> bool:
    return bool(session_id) and "/" not in session_id and "\\" not in session_id and session_id not in {".", ".."}


def _event_payload(event: SessionEvent) -> dict[str, object]:
    return {
        "schema_version": SESSION_RECORD_SCHEMA_VERSION,
        "session_id": event.session_id,
        "sequence": event.sequence,
        "kind": event.kind,
        "payload": dict(event.payload),
    }


def _event_from_payload(payload: object) -> SessionEvent:
    if not isinstance(payload, dict) or payload.get("schema_version") != SESSION_RECORD_SCHEMA_VERSION:
        msg = "unsupported event schema"
        raise ValueError(msg)
    event_payload = payload.get("payload")
    if not isinstance(event_payload, dict):
        msg = "event payload must be an object"
        raise TypeError(msg)
    return SessionEvent(
        session_id=str(payload["session_id"]),
        sequence=int(payload["sequence"]),
        kind=str(payload["kind"]),
        payload=event_payload,
    )


def _checkpoint_payload(checkpoint: SessionCheckpoint) -> dict[str, object]:
    fingerprint = checkpoint.workspace_fingerprint
    return {
        "schema_version": SESSION_RECORD_SCHEMA_VERSION,
        "session_id": checkpoint.session_id,
        "sequence": checkpoint.sequence,
        "state": checkpoint.state.value,
        "completed_summary": checkpoint.completed_summary,
        "workspace_fingerprint": {
            "digest": fingerprint.digest,
            "manifest": list(fingerprint.manifest),
            "unavailable_reason": fingerprint.unavailable_reason,
        },
    }


def _checkpoint_from_payload(payload: object) -> SessionCheckpoint:
    if not isinstance(payload, dict) or payload.get("schema_version") != SESSION_RECORD_SCHEMA_VERSION:
        msg = "unsupported checkpoint schema"
        raise ValueError(msg)
    fingerprint_payload = payload.get("workspace_fingerprint")
    if not isinstance(fingerprint_payload, dict):
        msg = "checkpoint requires a workspace fingerprint"
        raise TypeError(msg)
    manifest = fingerprint_payload.get("manifest", ())
    if not isinstance(manifest, list) or not all(isinstance(entry, str) for entry in manifest):
        msg = "fingerprint manifest must be a string list"
        raise TypeError(msg)
    return SessionCheckpoint(
        session_id=str(payload["session_id"]),
        sequence=int(payload["sequence"]),
        state=SessionState(str(payload["state"])),
        completed_summary=str(payload["completed_summary"]),
        workspace_fingerprint=WorkspaceFingerprint(
            digest=fingerprint_payload.get("digest"),
            manifest=tuple(manifest),
            unavailable_reason=fingerprint_payload.get("unavailable_reason"),
        ),
    )


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
