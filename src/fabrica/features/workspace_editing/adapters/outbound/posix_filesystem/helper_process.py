"""Supervised helper-process ownership for POSIX apply-patch mutation phases."""

from __future__ import annotations

import asyncio
import multiprocessing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.commit import PosixPatchCommitAdapter
from fabrica.features.workspace_editing.adapters.outbound.posix_filesystem.journal import (
    PosixPatchJournalAndPreparationAdapter,
    load_durable_journal,
)
from fabrica.features.workspace_editing.application.dtos import (
    PatchJournalRecord,
    PatchJournalState,
    PatchMutationGuarantee,
    PatchPlan,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error

if TYPE_CHECKING:
    from collections.abc import Callable

_POLL_INTERVAL_SECONDS = 0.01


class PatchHelperOperation(StrEnum):
    """One bounded visible apply-patch lifecycle phase owned by a helper."""

    PREPARE_DIRECTORIES = "prepare_directories"
    PREPARE_FILES = "prepare_files"
    COMMIT = "commit"
    ROLL_BACK = "roll_back"


class PatchHelperConnection(Protocol):
    """One-result IPC endpoint owned by a helper process."""

    def send(self, result: PatchResult | None) -> None:
        """Send the operation outcome to the supervising parent."""
        ...

    def close(self) -> None:
        """Close the helper endpoint after sending its only result."""
        ...


class PatchHelperProcess(Protocol):
    """Minimal helper lifecycle surface required for termination proof."""

    def start(self) -> None:
        """Start the short-lived helper."""
        ...

    def is_alive(self) -> bool:
        """Return whether the helper can still mutate the workspace."""
        ...

    def terminate(self) -> None:
        """Terminate an unresponsive helper before parent return."""
        ...

    def join(self) -> None:
        """Wait until the helper can no longer mutate the workspace."""
        ...


class SupervisedPatchMutation(Protocol):
    """Port-shaped supervised mutation operations shared by local wrappers."""

    async def prepare_directories(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Prepare derived directories under helper ownership."""
        ...

    async def prepare_files(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Prepare file stage artifacts under helper ownership."""
        ...

    async def commit(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult:
        """Commit staged file effects under helper ownership."""
        ...

    async def roll_back(self, journal: PatchJournalRecord) -> PatchResult:
        """Roll back visible effects under helper ownership."""
        ...


@dataclass(frozen=True, slots=True)
class PosixSupervisedPatchMutationAdapter:
    """Run each POSIX mutation phase in a joined helper with durable evidence."""

    workspace_root: Path
    process_factory: Callable[..., PatchHelperProcess] = multiprocessing.Process

    async def prepare_directories(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Create derived directories under supervised helper ownership."""
        return await self._run(PatchHelperOperation.PREPARE_DIRECTORIES, plan, journal)

    async def prepare_files(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Create staged file artifacts under supervised helper ownership."""
        return await self._run(PatchHelperOperation.PREPARE_FILES, plan, journal)

    async def commit(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult:
        """Commit file effects only after proving the helper's terminal journal state."""
        result = await self._run(PatchHelperOperation.COMMIT, plan, journal)
        return result if result is not None else _indeterminate(journal, "helper returned no commit outcome")

    async def roll_back(self, journal: PatchJournalRecord) -> PatchResult:
        """Roll back visible effects under supervised helper ownership."""
        result = await self._run(PatchHelperOperation.ROLL_BACK, None, journal)
        return result if result is not None else _recovery_required(journal, "helper returned no rollback outcome")

    async def _run(
        self, operation: PatchHelperOperation, plan: PatchPlan | None, journal: PatchJournalRecord
    ) -> PatchResult | None:
        parent_connection, child_connection = multiprocessing.Pipe(duplex=False)
        process = self.process_factory(
            target=run_patch_operation_in_helper,
            args=(child_connection, str(self.workspace_root), operation, plan, journal),
            daemon=True,
        )
        process.start()
        child_connection.close()
        outcome: PatchResult | None = None
        received = False
        try:
            while process.is_alive() or parent_connection.poll():
                if parent_connection.poll():
                    received = True
                    candidate = parent_connection.recv()
                    if isinstance(candidate, PatchResult) or candidate is None:
                        outcome = candidate
                    else:
                        return _indeterminate(journal, "helper returned an invalid IPC outcome")
                    break
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            if not received:
                return _recovery_required(journal, "helper exited before reporting a durable terminal outcome")
            terminal_result = _validate_terminal_evidence(self.workspace_root, operation, journal, outcome)
            if terminal_result is not None:
                return terminal_result
        except EOFError, OSError:
            return _recovery_required(journal, "helper IPC closed before terminal outcome verification")
        else:
            return outcome
        finally:
            parent_connection.close()
            if process.is_alive():
                process.terminate()
            process.join()


@dataclass(frozen=True, slots=True)
class PosixSupervisedPatchPreparationAdapter:
    """Expose supervised derived-directory preparation through the patch stager port."""

    supervisor: SupervisedPatchMutation

    async def prepare(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Create derived directories in a short-lived supervised helper."""
        return await self.supervisor.prepare_directories(plan, journal)


@dataclass(frozen=True, slots=True)
class PosixSupervisedPatchCommitAdapter:
    """Expose supervised file staging, commit, and rollback through patch ports."""

    supervisor: SupervisedPatchMutation

    async def prepare(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult | None:
        """Stage file payloads in a short-lived supervised helper."""
        return await self.supervisor.prepare_files(plan, journal)

    async def commit(self, plan: PatchPlan, journal: PatchJournalRecord) -> PatchResult:
        """Commit file effects in a short-lived supervised helper."""
        return await self.supervisor.commit(plan, journal)

    async def roll_back(self, journal: PatchJournalRecord) -> PatchResult:
        """Roll back file and directory effects in a short-lived supervised helper."""
        return await self.supervisor.roll_back(journal)


def run_patch_operation_in_helper(
    connection: PatchHelperConnection,
    workspace_root: str,
    operation: PatchHelperOperation,
    plan: PatchPlan | None,
    journal: PatchJournalRecord,
) -> None:
    """Reopen durable journal state and execute exactly one POSIX mutation phase."""
    try:
        durable_journal = _load_durable_journal(Path(workspace_root), journal)
        if durable_journal is None:
            outcome: PatchResult | None = _recovery_required(journal, "durable journal binding could not be validated")
        elif operation is PatchHelperOperation.PREPARE_DIRECTORIES:
            outcome = asyncio.run(
                PosixPatchJournalAndPreparationAdapter(Path(workspace_root)).prepare(
                    _required_plan(plan), durable_journal
                )
            )
        elif operation is PatchHelperOperation.PREPARE_FILES:
            outcome = asyncio.run(
                PosixPatchCommitAdapter(Path(workspace_root)).prepare(_required_plan(plan), durable_journal)
            )
        elif operation is PatchHelperOperation.COMMIT:
            outcome = asyncio.run(
                PosixPatchCommitAdapter(Path(workspace_root)).commit(_required_plan(plan), durable_journal)
            )
        else:
            outcome = asyncio.run(PosixPatchCommitAdapter(Path(workspace_root)).roll_back(durable_journal))
        connection.send(outcome)
    except OSError, ValueError, RuntimeError:
        connection.send(_recovery_required(journal, "helper could not prove a safe terminal mutation outcome"))
    finally:
        connection.close()


def supervised_helper_ownership_available() -> bool:
    """Return whether this host exposes the process primitives required by the supervisor."""
    return hasattr(multiprocessing, "Pipe") and hasattr(multiprocessing, "Process")


def _load_durable_journal(workspace_root: Path, journal: PatchJournalRecord) -> PatchJournalRecord | None:
    durable = load_durable_journal(workspace_root, journal.journal_digest)
    if durable is None:
        return None
    if durable.journal_digest != journal.journal_digest or durable.plan_digest != journal.plan_digest:
        return None
    return durable


def _required_plan(plan: PatchPlan | None) -> PatchPlan:
    if plan is None:
        msg = "this helper operation requires an approved patch plan"
        raise ValueError(msg)
    return plan


def _validate_terminal_evidence(
    workspace_root: Path,
    operation: PatchHelperOperation,
    journal: PatchJournalRecord,
    outcome: PatchResult | None,
) -> PatchResult | None:
    if outcome is None:
        expected_state = PatchJournalState.PREPARED
    elif outcome.status is PatchResultStatus.COMMITTED:
        expected_state = PatchJournalState.COMMITTED
    elif outcome.status is PatchResultStatus.COMMIT_FAILED_ROLLED_BACK:
        expected_state = PatchJournalState.ROLLED_BACK
    else:
        return None
    durable = _load_durable_journal(workspace_root, journal)
    if durable is not None and durable.state is expected_state:
        return None
    message = f"helper {operation.value} outcome lacked matching durable terminal journal evidence"
    if operation is PatchHelperOperation.COMMIT:
        return _indeterminate(journal, message)
    return _recovery_required(journal, message)


def _indeterminate(journal: PatchJournalRecord, message: str) -> PatchResult:
    error = patch_error("INDETERMINATE_COMMIT_STATE", message=message, metadata={"plan_digest": journal.plan_digest})
    return PatchResult(
        status=PatchResultStatus.INDETERMINATE_COMMIT_STATE,
        mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
        plan_digest=journal.plan_digest,
        directory_outcomes=journal.created_directories,
        path_outcomes=journal.path_outcomes,
        error=error,
    )


def _recovery_required(journal: PatchJournalRecord, message: str) -> PatchResult:
    error = patch_error(
        "RECOVERY_REQUIRED",
        message=message,
        metadata={"journal_digest": journal.journal_digest, "journal_state": journal.state.value},
    )
    return PatchResult(
        status=PatchResultStatus.RECOVERY_REQUIRED,
        mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
        plan_digest=journal.plan_digest,
        directory_outcomes=journal.created_directories,
        path_outcomes=journal.path_outcomes,
        error=error,
    )


__all__ = [
    "PosixSupervisedPatchCommitAdapter",
    "PosixSupervisedPatchMutationAdapter",
    "PosixSupervisedPatchPreparationAdapter",
    "supervised_helper_ownership_available",
]
