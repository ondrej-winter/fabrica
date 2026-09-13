"""Integration tests for workspace-local durable session records."""

import json
from pathlib import Path

import pytest

from fabrica.features.agent_session.adapters.outbound.posix_filesystem import (
    PosixSessionRecordStore,
    PosixWorkspaceFingerprintBuilder,
    SessionRecordError,
)
from fabrica.features.agent_session.application.dtos import SessionCheckpoint, SessionEvent, WorkspaceFingerprint
from fabrica.features.agent_session.domain import SessionState


def test_store_round_trips_tail_recovery_checkpoint_export_and_isolated_deletion(tmp_path: Path) -> None:
    """Persist one session independently and export stable user-managed evidence."""
    store = PosixSessionRecordStore(tmp_path)
    event = SessionEvent("one", 0, "prompt", {"text": "inspect"})
    store.append_event(event)
    store.append_event(SessionEvent("two", 0, "prompt", {"text": "other"}))
    events_path = tmp_path / ".fabrica" / "sessions" / "one" / "events.jsonl"
    with events_path.open("ab") as handle:
        handle.write(b"{bad")
    fingerprint = WorkspaceFingerprint(digest="sha256:" + "b" * 64)
    checkpoint = SessionCheckpoint("one", 0, SessionState.INTERRUPTED, fingerprint, "completed evidence")
    store.save_checkpoint(checkpoint)

    export = store.export_session("one", tmp_path / "export")

    assert store.load_events("one") == (event,)
    assert store.load_checkpoint("one") == checkpoint
    assert (export / "manifest.json").read_text(encoding="utf-8") == '{"schema_version":1,"session_id":"one"}'
    assert (export / "events.jsonl").read_text(encoding="utf-8").endswith("\n")
    store.delete_session("one")
    assert store.list_session_ids() == ("two",)


def test_store_fails_closed_for_corruption_before_tail(tmp_path: Path) -> None:
    """Reject an invalid record preceding additional journal evidence."""
    store = PosixSessionRecordStore(tmp_path)
    path = tmp_path / ".fabrica" / "sessions" / "one" / "events.jsonl"
    path.parent.mkdir(parents=True)
    valid_event = {
        "schema_version": 1,
        "session_id": "one",
        "sequence": 1,
        "kind": "event",
        "payload": {},
    }
    path.write_bytes(b"{bad\n" + json.dumps(valid_event).encode() + b"\n")

    with pytest.raises(SessionRecordError, match="corrupt"):
        store.load_events("one")


def test_fingerprint_is_deterministic_honors_exclusions_and_fails_closed_on_symlink(tmp_path: Path) -> None:
    """Exclude configured paths but reject symlinked workspace entries."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / ".fabrica").mkdir()
    (tmp_path / ".fabrica" / "ignored").write_text("ignore", encoding="utf-8")

    first = PosixWorkspaceFingerprintBuilder(tmp_path).build()
    (tmp_path / ".fabricaignore").write_text("src/a.txt\n", encoding="utf-8")
    excluded = PosixWorkspaceFingerprintBuilder(tmp_path).build()

    assert first.available
    assert excluded.available
    assert first.digest != excluded.digest
    (tmp_path / "link").symlink_to(tmp_path / "src" / "a.txt")
    assert not PosixWorkspaceFingerprintBuilder(tmp_path).build().available


def test_fingerprint_rejects_invalid_ignore_pattern(tmp_path: Path) -> None:
    """Fail closed instead of interpreting escaping user patterns ambiguously."""
    (tmp_path / ".fabricaignore").write_text("../outside\n", encoding="utf-8")

    fingerprint = PosixWorkspaceFingerprintBuilder(tmp_path).build()

    assert fingerprint.available is False
    assert fingerprint.unavailable_reason == "invalid .fabricaignore pattern"
