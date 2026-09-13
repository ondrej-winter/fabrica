"""Read-only and lifecycle CLI rendering for durable session records."""

from pathlib import Path
from typing import TextIO

from fabrica.adapters.inbound.cli.rendering import write_line
from fabrica.features.agent_session.application.ports import SessionRecordStore
from fabrica.features.coding_agent_session.adapters.inbound.cli.command_models import CliSessionRecordCommand

SESSION_RECORD_ERROR_EXIT_CODE = 3


def run_session_record_cli_command(
    command: CliSessionRecordCommand,
    *,
    store: SessionRecordStore,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Execute one non-resume durable session operation through the record port."""
    if command.operation == "list":
        for session_id in store.list_session_ids():
            write_line(stdout, session_id)
        return 0
    if command.operation == "inspect":
        return _inspect(command, store=store, stdout=stdout, stderr=stderr)
    if command.operation == "delete":
        store.delete_session(_required_session_id(command))
        write_line(stdout, f"Deleted session: {_required_session_id(command)}")
        return 0
    if command.operation == "export":
        destination = store.export_session(_required_session_id(command), _required_destination(command))
        write_line(stdout, f"Exported session to: {destination}")
        return 0
    msg = f"unsupported session operation: {command.operation}"
    raise ValueError(msg)


def _inspect(command: CliSessionRecordCommand, *, store: SessionRecordStore, stdout: TextIO, stderr: TextIO) -> int:
    session_id = _required_session_id(command)
    checkpoint = store.load_checkpoint(session_id)
    events = store.load_events(session_id)
    if checkpoint is None and not events:
        write_line(stderr, f"session not found: {session_id}")
        return SESSION_RECORD_ERROR_EXIT_CODE
    write_line(stdout, f"Session: {session_id}")
    write_line(stdout, f"Event count: {len(events)}")
    if checkpoint is None:
        write_line(stdout, "Checkpoint: unavailable")
    else:
        write_line(stdout, f"Checkpoint state: {checkpoint.state.value}")
        write_line(stdout, f"Checkpoint sequence: {checkpoint.sequence}")
        write_line(stdout, f"Completed summary: {checkpoint.completed_summary}")
    return 0


def _required_session_id(command: CliSessionRecordCommand) -> str:
    if command.session_id is None:
        msg = "session operation requires a session ID"
        raise ValueError(msg)
    return command.session_id


def _required_destination(command: CliSessionRecordCommand) -> Path:
    if command.export_destination is None:
        msg = "session export requires a destination"
        raise ValueError(msg)
    return command.export_destination
