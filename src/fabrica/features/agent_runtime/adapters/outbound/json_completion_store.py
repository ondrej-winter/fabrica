"""Durable JSON completion store for local host compositions."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fabrica.features.agent_runtime.application.dtos.completion import (
    CompletionCommitResult,
    CompletionCommitStatus,
    CompletionOutcome,
    CompletionRecord,
    CompletionVerification,
)


@dataclass(frozen=True, slots=True)
class JsonCompletionStore:
    """Persist one atomically committed completion record per opaque run identifier."""

    root: Path

    async def commit_completion(self, run_id: str, record: CompletionRecord) -> CompletionCommitResult:
        """Atomically write a completed run record or return its prior committed record."""
        if run_id != record.run_id:
            msg = "completion run id must match its record"
            raise ValueError(msg)
        path = self._record_path(run_id)
        committed = _write_json_if_absent(path, {"record": _record_payload(record), "state": "completed"})
        if committed:
            return CompletionCommitResult(status=CompletionCommitStatus.COMMITTED, record=record)
        return CompletionCommitResult(status=CompletionCommitStatus.ALREADY_COMPLETED, record=_read_record(path))

    async def list_unpresented(self) -> tuple[CompletionRecord, ...]:
        """Return committed records not acknowledged by the host presenter."""
        if not self.root.exists():
            return ()
        return tuple(
            _read_record(path)
            for path in sorted(self.root.glob("*.json"))
            if not self._acknowledgement_path(path.stem).exists()
        )

    async def acknowledge_presented(self, run_id: str) -> bool:
        """Write an idempotent durable presentation acknowledgement for one run."""
        record_path = self._record_path(run_id)
        acknowledgement_path = self._acknowledgement_path(run_id)
        if not record_path.exists() or acknowledgement_path.exists():
            return False
        return _write_json_if_absent(acknowledgement_path, {"run_id": run_id})

    def _record_path(self, run_id: str) -> Path:
        return self.root / f"{run_id}.json"

    def _acknowledgement_path(self, run_id: str) -> Path:
        return self.root / ".presented" / f"{run_id}.json"


def _record_payload(record: CompletionRecord) -> dict[str, object]:
    return {
        "committed_at": record.committed_at.isoformat(),
        "metadata": dict(record.metadata),
        "outcome": record.outcome.value,
        "payload_digest": record.payload_digest,
        "run_id": record.run_id,
        "summary": record.summary,
        "tool_call_id": record.tool_call_id,
        "verification": record.verification.value,
    }


def _read_record(path: Path) -> CompletionRecord:
    payload = json.loads(path.read_text(encoding="utf-8"))["record"]
    return CompletionRecord(
        run_id=payload["run_id"],
        tool_call_id=payload["tool_call_id"],
        payload_digest=payload["payload_digest"],
        outcome=CompletionOutcome(payload["outcome"]),
        summary=payload["summary"],
        verification=CompletionVerification(payload["verification"]),
        committed_at=datetime.fromisoformat(payload["committed_at"]),
        metadata=payload["metadata"],
    )


def _write_json_if_absent(path: Path, payload: dict[str, object]) -> bool:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    temporary_path = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    temporary_path.write_bytes(encoded)
    with temporary_path.open("rb") as file:
        os.fsync(file.fileno())
    try:
        os.link(temporary_path, path)
    except FileExistsError:
        return False
    finally:
        temporary_path.unlink(missing_ok=True)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return True


__all__ = ["JsonCompletionStore"]
