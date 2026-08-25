"""Durable POSIX journal and directory preparation adapter for apply-patch."""

import json
import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fabrica.features.workspace_editing.application.dtos import (
    PatchDirectoryOutcome,
    PatchDirectoryOutcomeState,
    PatchDirectoryPlannedEffect,
    PatchJournalRecord,
    PatchJournalState,
    PatchMutationGuarantee,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
    is_legal_patch_journal_transition,
)
from fabrica.features.workspace_editing.application.errors import patch_error


@dataclass(frozen=True, slots=True)
class PosixPatchJournalAndPreparationAdapter:
    """Record durable patch intent and manage reversible derived directories."""

    workspace_root: Path
    journal_root: Path | None = None

    async def list_incomplete(self) -> tuple[PatchJournalRecord, ...]:
        """List non-terminal journals persisted by this adapter."""
        root = self._journal_root()
        if not root.exists():
            return ()
        records: list[PatchJournalRecord] = []
        terminal_states = {
            PatchJournalState.COMMITTED,
            PatchJournalState.ROLLED_BACK,
            PatchJournalState.RECOVERY_REQUIRED,
        }
        for path in sorted(root.glob("*.json")):
            record = _read_record(path)
            if record.state not in terminal_states:
                records.append(record)
        return tuple(records)

    async def create(self, plan: PatchPlan) -> PatchJournalRecord:
        """Durably record recovery intent before visible preparation effects."""
        record = PatchJournalRecord(
            journal_digest=_journal_digest(plan.plan_digest),
            plan_digest=plan.plan_digest,
            state=PatchJournalState.PLANNED,
            created_directories=plan.created_directories,
        )
        _write_record(self._record_path(record), record)
        return record

    async def transition(self, record: PatchJournalRecord, destination: PatchJournalState) -> PatchJournalRecord:
        """Durably advance a journal through a legal lifecycle transition."""
        if not is_legal_patch_journal_transition(record.state, destination):
            msg = f"illegal patch journal transition: {record.state.value} -> {destination.value}"
            raise ValueError(msg)
        updated = PatchJournalRecord(
            journal_digest=record.journal_digest,
            plan_digest=record.plan_digest,
            state=destination,
            created_directories=record.created_directories,
            path_outcomes=record.path_outcomes,
            metadata=record.metadata,
        )
        _write_record(self._record_path(updated), updated)
        return updated

    async def prepare(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Create reversible destination parent directories before file commit."""
        preparing = await self.transition(journal, PatchJournalState.PREPARING)
        created: list[PatchDirectoryOutcome] = []
        for planned_directory in plan.created_directories:
            absolute = self._workspace_root() / planned_directory.path
            try:
                absolute.mkdir(mode=0o777, exist_ok=False)
                directory_stat = absolute.lstat()
            except FileExistsError:
                result = _rejected(
                    "DIRECTORY_CREATION_UNSAFE",
                    f"planned directory already exists: {planned_directory.path}",
                )
                await self._roll_back_preparation(preparing, created)
                return result
            except OSError as err:
                result = _rejected("IO_ERROR", f"could not create planned directory: {err.strerror}")
                await self._roll_back_preparation(preparing, created)
                return result
            if not stat.S_ISDIR(directory_stat.st_mode):
                result = _rejected(
                    "DIRECTORY_CREATION_UNSAFE",
                    f"created path is not a directory: {planned_directory.path}",
                )
                await self._roll_back_preparation(preparing, created)
                return result
            created.append(
                PatchDirectoryOutcome(
                    path=planned_directory.path,
                    planned_effect=planned_directory.planned_effect,
                    final_state=PatchDirectoryOutcomeState.CREATED,
                    reason=planned_directory.reason,
                    identity_digest=_identity_digest(directory_stat),
                )
            )
            preparing = _replace_record_directories(preparing, tuple(created))
            _write_record(self._record_path(preparing), preparing)

        await self.transition(preparing, PatchJournalState.PREPARED)
        return None

    async def _roll_back_preparation(
        self,
        record: PatchJournalRecord,
        created: list[PatchDirectoryOutcome],
    ) -> PatchResult:
        rolling_back = await self.transition(record, PatchJournalState.ROLLING_BACK)
        outcomes: list[PatchDirectoryOutcome] = []
        for directory in reversed(created):
            absolute = self._workspace_root() / directory.path
            try:
                current_stat = absolute.lstat()
                if _identity_digest(current_stat) != directory.identity_digest:
                    outcomes.append(_directory_with_state(directory, PatchDirectoryOutcomeState.REMOVAL_UNCERTAIN))
                    continue
                absolute.rmdir()
                outcomes.append(_directory_with_state(directory, PatchDirectoryOutcomeState.REMOVED))
            except OSError:
                outcomes.append(_directory_with_state(directory, PatchDirectoryOutcomeState.REMOVAL_UNCERTAIN))
        final_record = _replace_record_directories(rolling_back, tuple(reversed(outcomes)))
        terminal_state = PatchJournalState.ROLLED_BACK
        if any(item.final_state is PatchDirectoryOutcomeState.REMOVAL_UNCERTAIN for item in outcomes):
            terminal_state = PatchJournalState.RECOVERY_REQUIRED
        _write_record(self._record_path(final_record), final_record)
        await self.transition(final_record, terminal_state)
        if terminal_state is PatchJournalState.RECOVERY_REQUIRED:
            uncertain = next(
                item for item in outcomes if item.final_state is PatchDirectoryOutcomeState.REMOVAL_UNCERTAIN
            )
            return _fatal_directory_result("CREATED_DIRECTORY_REMOVAL_UNCERTAIN", uncertain, tuple(reversed(outcomes)))
        error = patch_error("IO_ERROR", message="preparation failed after rollback")
        return PatchResult(
            status=PatchResultStatus.REJECTED,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
            error=error,
        )

    def _workspace_root(self) -> Path:
        return self.workspace_root.resolve(strict=True)

    def _journal_root(self) -> Path:
        return self.journal_root or self._workspace_root() / ".fabrica" / "apply-patch" / "journal"

    def _record_path(self, record: PatchJournalRecord) -> Path:
        return self._journal_root() / f"{record.journal_digest.removeprefix('sha256:')}.json"


def _replace_record_directories(
    record: PatchJournalRecord, directories: tuple[PatchDirectoryOutcome, ...]
) -> PatchJournalRecord:
    return PatchJournalRecord(
        journal_digest=record.journal_digest,
        plan_digest=record.plan_digest,
        state=record.state,
        created_directories=directories,
        path_outcomes=record.path_outcomes,
        metadata=record.metadata,
    )


def _directory_with_state(directory: PatchDirectoryOutcome, state: PatchDirectoryOutcomeState) -> PatchDirectoryOutcome:
    return PatchDirectoryOutcome(
        path=directory.path,
        planned_effect=directory.planned_effect,
        final_state=state,
        reason=directory.reason,
        identity_digest=directory.identity_digest,
    )


def _write_record(path: Path, record: PatchJournalRecord) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "created_directories": [
            {
                "final_state": directory.final_state.value,
                "identity_digest": directory.identity_digest,
                "path": directory.path,
                "planned_effect": directory.planned_effect.value,
                "reason": directory.reason,
            }
            for directory in record.created_directories
        ],
        "journal_digest": record.journal_digest,
        "metadata": dict(record.metadata),
        "path_outcomes": [],
        "plan_digest": record.plan_digest,
        "state": record.state.value,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_bytes(encoded)
    _fsync_file(tmp_path)
    tmp_path.replace(path)
    _fsync_directory(path.parent)


def _read_record(path: Path) -> PatchJournalRecord:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PatchJournalRecord(
        journal_digest=payload["journal_digest"],
        plan_digest=payload["plan_digest"],
        state=PatchJournalState(payload["state"]),
        created_directories=tuple(
            PatchDirectoryOutcome(
                path=item["path"],
                planned_effect=PatchDirectoryPlannedEffect(item["planned_effect"]),
                final_state=PatchDirectoryOutcomeState(item["final_state"]),
                reason=item["reason"],
                identity_digest=item["identity_digest"],
            )
            for item in payload["created_directories"]
        ),
        metadata=payload["metadata"],
    )


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    directory_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _journal_digest(plan_digest: str) -> str:
    return "sha256:" + sha256(f"apply-patch-journal:{plan_digest}".encode()).hexdigest()


def _identity_digest(path_stat: os.stat_result) -> str:
    payload = f"{path_stat.st_dev}:{path_stat.st_ino}:{path_stat.st_mode}"
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


def _rejected(code: str, message: str) -> PatchResult:
    error = patch_error(code, message=message)
    return PatchResult(
        status=PatchResultStatus.REJECTED,
        mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        error=error,
    )


def _fatal_directory_result(
    code: str, directory: PatchDirectoryOutcome, outcomes: tuple[PatchDirectoryOutcome, ...]
) -> PatchResult:
    error = patch_error(code, metadata={"path": directory.path, "final_state": directory.final_state.value})
    return PatchResult(
        status=PatchResultStatus.RECOVERY_REQUIRED,
        mutation_guarantee=error.mutation_guarantee,
        directory_outcomes=outcomes,
        error=error,
    )


__all__ = ["PosixPatchJournalAndPreparationAdapter"]
