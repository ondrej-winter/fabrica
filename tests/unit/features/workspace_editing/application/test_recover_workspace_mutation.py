"""Tests for apply-patch startup recovery and mutation gating."""

from asyncio import run
from dataclasses import dataclass, field

import pytest

from fabrica.features.workspace_editing.application.dtos import (
    PatchAction,
    PatchError,
    PatchJournalRecord,
    PatchJournalState,
    PatchMutationGuarantee,
    PatchPlan,
    PatchRecoveryAction,
    PatchRecoveryDecision,
    PatchRecoveryStatus,
    PatchResult,
    PatchResultStatus,
)
from fabrica.features.workspace_editing.application.errors import patch_error
from fabrica.features.workspace_editing.application.text_snapshot import PatchTextSnapshot
from fabrica.features.workspace_editing.application.use_cases import PatchPlanningSnapshot, RecoverWorkspaceMutation

SHA256_A = "sha256:" + "a" * 64
SHA256_B = "sha256:" + "b" * 64
SHA256_C = "sha256:" + "c" * 64
EXPECTED_JOURNAL_STORE_READS = 2


def test_startup_gate_disables_mutation_when_capability_proof_fails() -> None:
    capability_error = patch_error("UNSUPPORTED_FILESYSTEM_GUARANTEE", message="capability unavailable")
    snapshot_reader = _SnapshotReader(_result(PatchResultStatus.REJECTED, capability_error))
    journal_store = _JournalStore()
    coordinator = _RecoveryCoordinator()

    gate = run(RecoverWorkspaceMutation(snapshot_reader, journal_store, coordinator).recover())

    assert not gate.mutation_enabled
    assert gate.error is capability_error
    assert journal_store.list_calls == 0
    assert coordinator.events == []


def test_startup_gate_recovers_incomplete_journals_in_digest_order_and_requires_terminal_evidence() -> None:
    first = _journal(SHA256_A, PatchJournalState.PREPARED)
    second = _journal(SHA256_B, PatchJournalState.PLANNED)
    journal_store = _JournalStore(incomplete=[second, first])
    coordinator = _RecoveryCoordinator()

    gate = run(RecoverWorkspaceMutation(_SnapshotReader(), journal_store, coordinator).recover())

    assert gate.mutation_enabled
    assert gate.recovered_journal_digests == (SHA256_A, SHA256_B)
    assert coordinator.events == [
        f"inspect:{SHA256_A}",
        f"recover:{SHA256_A}",
        f"inspect:{SHA256_B}",
        f"recover:{SHA256_B}",
    ]
    assert journal_store.list_calls == EXPECTED_JOURNAL_STORE_READS


def test_startup_gate_blocks_operator_required_recovery_without_attempting_forward_mutation() -> None:
    journal = _journal(SHA256_C, PatchJournalState.COMMITTING)
    journal_store = _JournalStore(incomplete=[journal])
    coordinator = _RecoveryCoordinator(required_journal_digests={SHA256_C})

    gate = run(RecoverWorkspaceMutation(_SnapshotReader(), journal_store, coordinator).recover())

    assert not gate.mutation_enabled
    assert gate.error is not None
    assert gate.error.code == "RECOVERY_REQUIRED"
    assert gate.error.metadata["journal_digest"] == SHA256_C
    assert gate.error.metadata["operator_guidance"]
    assert coordinator.events == [f"inspect:{SHA256_C}"]


def test_startup_gate_remains_disabled_when_safe_recovery_does_not_clear_durable_journal() -> None:
    journal = _journal(SHA256_A, PatchJournalState.PREPARED)
    journal_store = _JournalStore(incomplete=[journal], retain_after_recovery=True)
    coordinator = _RecoveryCoordinator()

    gate = run(RecoverWorkspaceMutation(_SnapshotReader(), journal_store, coordinator).recover())

    assert not gate.mutation_enabled
    assert gate.error is not None
    assert gate.error.code == "RECOVERY_REQUIRED"
    assert coordinator.events == [f"inspect:{SHA256_A}", f"recover:{SHA256_A}"]


def test_startup_gate_disables_mutation_when_recovery_does_not_prove_no_mutation() -> None:
    journal = _journal(SHA256_A, PatchJournalState.PREPARED)
    recovery_error = patch_error(
        "RECOVERY_REQUIRED",
        metadata={"journal_digest": SHA256_A},
    )
    coordinator = _RecoveryCoordinator(
        recovery_result=PatchResult(
            status=PatchResultStatus.RECOVERY_REQUIRED,
            mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
            plan_digest=journal.plan_digest,
            error=recovery_error,
        )
    )

    gate = run(RecoverWorkspaceMutation(_SnapshotReader(), _JournalStore(incomplete=[journal]), coordinator).recover())

    assert not gate.mutation_enabled
    assert gate.error is recovery_error
    assert coordinator.events == [f"inspect:{SHA256_A}", f"recover:{SHA256_A}"]


def test_startup_gate_rejects_recovery_adapter_outcome_without_error_evidence() -> None:
    journal = _journal(SHA256_A, PatchJournalState.PREPARED)
    coordinator = _RecoveryCoordinator(
        recovery_result=PatchResult(
            status=PatchResultStatus.COMMITTED,
            mutation_guarantee=PatchMutationGuarantee.COMMITTED,
        )
    )

    with pytest.raises(ValueError, match="must include patch error evidence"):
        run(RecoverWorkspaceMutation(_SnapshotReader(), _JournalStore(incomplete=[journal]), coordinator).recover())


def _journal(journal_digest: str, state: PatchJournalState) -> PatchJournalRecord:
    return PatchJournalRecord(journal_digest=journal_digest, plan_digest=SHA256_C, state=state)


def _result(status: PatchResultStatus, error: PatchError) -> PatchResult:
    return PatchResult(status=status, mutation_guarantee=PatchMutationGuarantee.NO_MUTATION, error=error)


@dataclass(slots=True)
class _SnapshotReader:
    result: PatchResult | None = None
    unexpected_calls: list[str] = field(default_factory=list)

    async def verify_workspace_capabilities(self) -> PatchResult | None:
        return self.result

    async def snapshot_plan_inputs(self, plan: PatchPlan) -> PatchResult | None:
        del plan
        return None

    async def snapshot_for_planning(self, actions: tuple[PatchAction, ...]) -> PatchPlanningSnapshot | PatchResult:
        del actions
        return PatchPlanningSnapshot()

    async def read_text_snapshot(self, path: str) -> PatchTextSnapshot | PatchResult:
        del path
        self.unexpected_calls.append("read_text_snapshot")
        return _result(PatchResultStatus.REJECTED, patch_error("IO_ERROR", message="unexpected read"))


@dataclass(slots=True)
class _JournalStore:
    incomplete: list[PatchJournalRecord] = field(default_factory=list)
    retain_after_recovery: bool = False
    list_calls: int = 0
    unexpected_calls: list[str] = field(default_factory=list)

    async def list_incomplete(self) -> tuple[PatchJournalRecord, ...]:
        self.list_calls += 1
        if self.list_calls > 1 and not self.retain_after_recovery:
            return ()
        return tuple(self.incomplete)

    async def create(self, plan: PatchPlan) -> PatchJournalRecord:
        del plan
        self.unexpected_calls.append("create")
        return _journal(SHA256_A, PatchJournalState.PLANNED)

    async def transition(self, record: PatchJournalRecord, destination: PatchJournalState) -> PatchJournalRecord:
        return PatchJournalRecord(
            journal_digest=record.journal_digest,
            plan_digest=record.plan_digest,
            state=destination,
        )


@dataclass(slots=True)
class _RecoveryCoordinator:
    required_journal_digests: set[str] = field(default_factory=set)
    events: list[str] = field(default_factory=list)
    recovery_result: PatchResult | None = None

    async def inspect(self, journal: PatchJournalRecord) -> PatchRecoveryDecision:
        self.events.append(f"inspect:{journal.journal_digest}")
        if journal.journal_digest in self.required_journal_digests:
            return PatchRecoveryDecision(
                action=PatchRecoveryAction.REQUIRE_OPERATOR_RECOVERY,
                status=PatchRecoveryStatus.RECOVERY_REQUIRED,
                mutation_guarantee=PatchMutationGuarantee.PARTIAL_OR_UNCERTAIN_MUTATION,
            )
        return PatchRecoveryDecision(
            action=PatchRecoveryAction.ROLL_BACK_PREPARATION,
            status=PatchRecoveryStatus.ROLLED_BACK,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
        )

    async def recover(self, journal: PatchJournalRecord) -> PatchResult:
        self.events.append(f"recover:{journal.journal_digest}")
        if self.recovery_result is not None:
            return self.recovery_result
        return PatchResult(
            status=PatchResultStatus.COMMIT_FAILED_ROLLED_BACK,
            mutation_guarantee=PatchMutationGuarantee.NO_MUTATION,
            plan_digest=journal.plan_digest,
            error=patch_error("COMMIT_FAILED_ROLLED_BACK", message="recovered"),
        )
