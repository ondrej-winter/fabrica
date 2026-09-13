"""Tests for durable session-record CLI operations."""

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from fabrica.features.agent_session.application.dtos import SessionCheckpoint, SessionEvent, WorkspaceFingerprint
from fabrica.features.agent_session.domain import SessionState
from fabrica.features.coding_agent_session.adapters.inbound.cli.command_models import CliSessionRecordCommand
from fabrica.features.coding_agent_session.adapters.inbound.cli.session_records import (
    SESSION_RECORD_ERROR_EXIT_CODE,
    run_session_record_cli_command,
)


def test_session_record_runner_lists_inspects_exports_and_deletes_selected_records(tmp_path: Path) -> None:
    store = _Store()
    store.events.append(SessionEvent("session-one", 0, "completed"))
    store.checkpoints.append(
        SessionCheckpoint(
            "session-one",
            0,
            SessionState.COMPLETED,
            WorkspaceFingerprint(digest="sha256:" + "a" * 64),
            "finished",
        )
    )
    stdout = StringIO()

    list_exit_code = run_session_record_cli_command(
        CliSessionRecordCommand(tmp_path, "list"), store=store, stdout=stdout, stderr=StringIO()
    )
    inspect_exit_code = run_session_record_cli_command(
        CliSessionRecordCommand(tmp_path, "inspect", session_id="session-one"),
        store=store,
        stdout=stdout,
        stderr=StringIO(),
    )
    export_exit_code = run_session_record_cli_command(
        CliSessionRecordCommand(tmp_path, "export", session_id="session-one", export_destination=tmp_path / "export"),
        store=store,
        stdout=stdout,
        stderr=StringIO(),
    )
    delete_exit_code = run_session_record_cli_command(
        CliSessionRecordCommand(tmp_path, "delete", session_id="session-one"),
        store=store,
        stdout=stdout,
        stderr=StringIO(),
    )

    assert (list_exit_code, inspect_exit_code, export_exit_code, delete_exit_code) == (0, 0, 0, 0)
    assert stdout.getvalue() == (
        "session-one\nSession: session-one\nEvent count: 1\nCheckpoint state: completed\n"
        "Checkpoint sequence: 0\nCompleted summary: finished\nExported session to: "
        f"{tmp_path / 'export'}\nDeleted session: session-one\n"
    )
    assert store.deleted_session_ids == ["session-one"]


def test_session_record_runner_reports_missing_inspection_without_mutation(tmp_path: Path) -> None:
    stderr = StringIO()

    exit_code = run_session_record_cli_command(
        CliSessionRecordCommand(tmp_path, "inspect", session_id="missing"),
        store=_Store(),
        stdout=StringIO(),
        stderr=stderr,
    )

    assert exit_code == SESSION_RECORD_ERROR_EXIT_CODE
    assert stderr.getvalue() == "session not found: missing\n"


@dataclass
class _Store:
    events: list[SessionEvent] = field(default_factory=list)
    checkpoints: list[SessionCheckpoint] = field(default_factory=list)
    deleted_session_ids: list[str] = field(default_factory=list)

    def append_event(self, event: SessionEvent) -> None:
        self.events.append(event)

    def save_checkpoint(self, checkpoint: SessionCheckpoint) -> None:
        self.checkpoints.append(checkpoint)

    def load_events(self, session_id: str) -> tuple[SessionEvent, ...]:
        return tuple(event for event in self.events if event.session_id == session_id)

    def load_checkpoint(self, session_id: str) -> SessionCheckpoint | None:
        return next((item for item in self.checkpoints if item.session_id == session_id), None)

    def list_session_ids(self) -> tuple[str, ...]:
        return tuple(sorted({event.session_id for event in self.events}))

    def delete_session(self, session_id: str) -> None:
        self.deleted_session_ids.append(session_id)

    def export_session(self, session_id: str, destination: Path) -> Path:
        assert session_id == "session-one"
        return destination
