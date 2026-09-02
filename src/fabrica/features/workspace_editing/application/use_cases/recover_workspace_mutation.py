"""Startup recovery gate for durable apply-patch workspace journals."""

from dataclasses import dataclass

from fabrica.features.workspace_editing.application.dtos import (
    PatchJournalRecord,
    PatchMutationGuarantee,
    PatchRecoveryStatus,
    PatchResult,
    PatchResultStatus,
    WorkspaceMutationStartupGate,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from fabrica.features.workspace_editing.application.ports import (
    PatchJournalStore,
    PatchRecoveryCoordinator,
    PatchWorkspaceSnapshotReader,
)


@dataclass(frozen=True, slots=True)
class RecoverWorkspaceMutation:
    """Recover interrupted patches before enabling workspace mutation at startup."""

    snapshot_reader: PatchWorkspaceSnapshotReader
    journal_store: PatchJournalStore
    recovery_coordinator: PatchRecoveryCoordinator

    async def recover(self) -> WorkspaceMutationStartupGate:
        """Return enabled only after capability proof and terminal journal evidence."""
        capability_result = await self.snapshot_reader.verify_workspace_capabilities()
        if capability_result is not None:
            return _disabled(capability_result)

        recovered_journal_digests: list[str] = []
        for journal in _ordered(await self.journal_store.list_incomplete()):
            decision = await self.recovery_coordinator.inspect(journal)
            if decision.status is PatchRecoveryStatus.RECOVERY_REQUIRED:
                return _recovery_required(journal, recovered_journal_digests)
            result = await self.recovery_coordinator.recover(journal)
            if not _was_safely_recovered(result):
                return _disabled(result, recovered_journal_digests)
            recovered_journal_digests.append(journal.journal_digest)

        unresolved = _ordered(await self.journal_store.list_incomplete())
        if unresolved:
            return _recovery_required(unresolved[0], recovered_journal_digests)
        return WorkspaceMutationStartupGate(
            mutation_enabled=True,
            recovered_journal_digests=tuple(recovered_journal_digests),
        )


def _ordered(journals: tuple[PatchJournalRecord, ...]) -> tuple[PatchJournalRecord, ...]:
    return tuple(sorted(journals, key=lambda journal: journal.journal_digest))


def _was_safely_recovered(result: PatchResult) -> bool:
    return (
        result.status is PatchResultStatus.COMMIT_FAILED_ROLLED_BACK
        and result.mutation_guarantee is PatchMutationGuarantee.NO_MUTATION
    )


def _disabled(result: PatchResult, recovered_journal_digests: list[str] | None = None) -> WorkspaceMutationStartupGate:
    if result.error is None:
        msg = "a startup mutation gate rejection must include patch error evidence"
        raise ValueError(msg)
    return WorkspaceMutationStartupGate(
        mutation_enabled=False,
        recovered_journal_digests=tuple(recovered_journal_digests or ()),
        error=result.error,
    )


def _recovery_required(
    journal: PatchJournalRecord,
    recovered_journal_digests: list[str],
) -> WorkspaceMutationStartupGate:
    error = patch_error(
        "RECOVERY_REQUIRED",
        message="workspace mutation remains disabled until interrupted patch recovery is resolved",
        metadata={
            "journal_digest": journal.journal_digest,
            "journal_state": journal.state.value,
            "operator_guidance": "inspect durable journal evidence and resolve retained or uncertain workspace effects",
        },
    )
    return WorkspaceMutationStartupGate(
        mutation_enabled=False,
        recovered_journal_digests=tuple(recovered_journal_digests),
        error=error,
    )


__all__ = ["RecoverWorkspaceMutation"]
